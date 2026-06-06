from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from statistics import mean
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import get_settings


BRANCH_KEYS = ("gru", "hybrid", "semantic", "posture", "detector")


@dataclass
class ReplaySummary:
    label: str
    source: str
    profile: str
    threshold: float | None
    process_every: int | None
    alert_rules: str | None
    injury_rules: str | None
    event_count: int
    event_type_counts: dict[str, int]
    state_counts: dict[str, int]
    confirmed_count: int
    suspected_count: int
    post_fall_count: int
    unique_track_count: int
    snapshot_count: int
    max_fall_score: float
    avg_fall_score: float
    dominant_branch_counts: dict[str, int]
    confirmed_branch_counts: dict[str, int]
    output_dir: str
    event_log: str


@dataclass(frozen=True)
class ReplayConfig:
    profile: str
    threshold: float | None
    process_every: int | None
    alert_rules: str | None
    injury_rules: str | None

    @property
    def slug(self) -> str:
        parts = [self.profile]
        parts.append(f"thr-{self._fmt_float(self.threshold)}" if self.threshold is not None else "thr-profile")
        parts.append(f"stride-{self.process_every}" if self.process_every is not None else "stride-profile")
        if self.alert_rules:
            parts.append(f"alert-{Path(self.alert_rules).stem}")
        if self.injury_rules:
            parts.append(f"injury-{Path(self.injury_rules).stem}")
        return "__".join(parts)

    @staticmethod
    def _fmt_float(value: float | None) -> str:
        if value is None:
            return "auto"
        return f"{value:.3f}".rstrip("0").rstrip(".").replace(".", "p")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay local videos through the external fall-detection model and summarize outputs."
    )
    parser.add_argument(
        "--source",
        action="append",
        required=True,
        help="Replay source in the form label=path or just path.",
    )
    parser.add_argument(
        "--benchmark-dir",
        default="data/fall_replay_benchmark",
        help="Directory to store run outputs.",
    )
    parser.add_argument(
        "--profile",
        action="append",
        default=[],
        help="Fall-detection profile. Repeat to compare multiple profiles.",
    )
    parser.add_argument(
        "--threshold",
        action="append",
        type=float,
        default=[],
        help="Override model confirm threshold. Repeat to compare multiple thresholds.",
    )
    parser.add_argument(
        "--process-every",
        action="append",
        type=int,
        default=[],
        help="Override model process-every setting. Repeat to compare multiple strides.",
    )
    parser.add_argument(
        "--keep-snapshots",
        action="store_true",
        help="Keep alert snapshots. By default only the event logs and summaries are preserved.",
    )
    parser.add_argument(
        "--status-log-interval",
        type=float,
        default=2.0,
        help="Pass-through interval for status events emitted by the external monitor.",
    )
    parser.add_argument(
        "--alert-rules",
        action="append",
        default=[],
        help="Optional alert-rules YAML override. Repeat to compare multiple rule files.",
    )
    parser.add_argument(
        "--injury-rules",
        action="append",
        default=[],
        help="Optional injury-rules YAML override. Repeat to compare multiple rule files.",
    )
    return parser.parse_args()


def parse_named_source(value: str) -> tuple[str, Path]:
    if "=" in value:
        label, raw_path = value.split("=", 1)
    else:
        raw_path = value
        label = Path(raw_path).stem
    normalized_label = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in label).strip("-_")
    normalized_label = normalized_label or "replay"
    path = Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Replay source not found: {path}")
    return normalized_label, path


def dominant_branch(event: dict[str, Any]) -> str | None:
    scores = event.get("scores")
    if not isinstance(scores, dict):
        return None
    best_key = None
    best_value = 0.0
    for key in BRANCH_KEYS:
        try:
            value = float(scores.get(key) or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        if value > best_value:
            best_key = key
            best_value = value
    return best_key if best_value > 0 else None


def load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.is_file():
        return events
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


def summarize_events(
    *,
    label: str,
    source: Path,
    output_dir: Path,
    event_log: Path,
    config: ReplayConfig,
) -> ReplaySummary:
    events = load_events(event_log)
    event_type_counts = Counter(str(event.get("event_type") or "") for event in events)
    state_counts = Counter(str(event.get("state") or "") for event in events)
    dominant_counts = Counter()
    confirmed_branch_counts = Counter()
    tracks = set()
    scores: list[float] = []
    snapshots = 0
    confirmed_count = 0
    suspected_count = 0
    post_fall_count = 0

    for event in events:
        track = str(event.get("track_id") or "").strip()
        if track:
            tracks.add(track)
        score = event.get("fall_score")
        try:
            scores.append(float(score))
        except (TypeError, ValueError):
            pass
        snapshot_path = str(event.get("snapshot_path") or "").strip()
        if snapshot_path:
            snapshots += 1

        branch = dominant_branch(event)
        if branch:
            dominant_counts[branch] += 1

        event_type = str(event.get("event_type") or "")
        state = str(event.get("state") or "")
        if event_type == "fall_confirmed" or state == "confirmed_fall":
            confirmed_count += 1
            if branch:
                confirmed_branch_counts[branch] += 1
        if state == "suspected_fall":
            suspected_count += 1
        if state == "post_fall_monitoring":
            post_fall_count += 1

    return ReplaySummary(
        label=label,
        source=str(source),
        profile=config.profile,
        threshold=config.threshold,
        process_every=config.process_every,
        alert_rules=config.alert_rules,
        injury_rules=config.injury_rules,
        event_count=len(events),
        event_type_counts=dict(event_type_counts),
        state_counts=dict(state_counts),
        confirmed_count=confirmed_count,
        suspected_count=suspected_count,
        post_fall_count=post_fall_count,
        unique_track_count=len(tracks),
        snapshot_count=snapshots,
        max_fall_score=max(scores) if scores else 0.0,
        avg_fall_score=mean(scores) if scores else 0.0,
        dominant_branch_counts=dict(dominant_counts),
        confirmed_branch_counts=dict(confirmed_branch_counts),
        output_dir=str(output_dir),
        event_log=str(event_log),
    )


def render_markdown(run_dir: Path, summaries: list[ReplaySummary]) -> str:
    lines = [
        "# Fall Detection Replay Benchmark",
        "",
        f"Generated at: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Summary",
        "",
        "| Label | Profile | Threshold | Stride | Confirmed | Suspected | Post-fall | Events | Unique tracks | Max score | Avg score |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in summaries:
        lines.append(
            f"| {item.label} | {item.profile} | {item.threshold if item.threshold is not None else 'profile'} | "
            f"{item.process_every if item.process_every is not None else 'profile'} | "
            f"{item.confirmed_count} | {item.suspected_count} | {item.post_fall_count} | "
            f"{item.event_count} | {item.unique_track_count} | {item.max_fall_score:.3f} | {item.avg_fall_score:.3f} |"
        )

    lines.append("")
    lines.append("## Details")
    lines.append("")
    for item in summaries:
        lines.append(f"### {item.label}")
        lines.append("")
        lines.append(f"- Source: `{item.source}`")
        lines.append(f"- Profile: `{item.profile}`")
        lines.append(f"- Threshold: `{item.threshold if item.threshold is not None else 'profile default'}`")
        lines.append(f"- Process every: `{item.process_every if item.process_every is not None else 'profile default'}`")
        lines.append(f"- Alert rules: `{item.alert_rules or 'profile default'}`")
        lines.append(f"- Injury rules: `{item.injury_rules or 'profile default'}`")
        lines.append(f"- Event log: `{item.event_log}`")
        lines.append(f"- Output dir: `{item.output_dir}`")
        lines.append(f"- Event types: `{json.dumps(item.event_type_counts, ensure_ascii=False)}`")
        lines.append(f"- States: `{json.dumps(item.state_counts, ensure_ascii=False)}`")
        lines.append(f"- Dominant branches: `{json.dumps(item.dominant_branch_counts, ensure_ascii=False)}`")
        lines.append(f"- Confirmed branches: `{json.dumps(item.confirmed_branch_counts, ensure_ascii=False)}`")
        lines.append("")

    report_path = run_dir / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return str(report_path)


def run_replay(
    *,
    label: str,
    source: Path,
    output_dir: Path,
    config: ReplayConfig,
    status_log_interval: float,
    keep_snapshots: bool,
) -> ReplaySummary:
    settings = get_settings()
    model_root = Path(settings.fall_detection_model_root).resolve()
    python = Path(settings.fall_detection_python).resolve()
    script = model_root / "scripts" / "realtime_fall_monitor.py"
    if not python.is_file():
        raise FileNotFoundError(f"Fall-detection Python not found: {python}")
    if not script.is_file():
        raise FileNotFoundError(f"Replay script not found: {script}")

    output_dir.mkdir(parents=True, exist_ok=True)
    event_log = output_dir / "events.jsonl"
    snapshot_dir = output_dir / "snapshots"
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    event_log.write_text("", encoding="utf-8")

    command = [
        str(python),
        str(script),
        "--source",
        str(source),
        "--profile",
        config.profile,
        "--event-log",
        str(event_log),
        "--snapshot-dir",
        str(snapshot_dir),
        "--status-log-interval",
        str(status_log_interval),
        "--no-display",
    ]
    if config.threshold is not None and config.threshold > 0:
        command.extend(["--threshold", str(config.threshold)])
    if config.process_every is not None and config.process_every > 0:
        command.extend(["--process-every", str(config.process_every)])
    if config.alert_rules:
        command.extend(["--alert-rules", config.alert_rules])
    if config.injury_rules:
        command.extend(["--injury-rules", config.injury_rules])

    print(f"[replay] Running {label}: {source}")
    completed = subprocess.run(
        command,
        cwd=str(model_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    (output_dir / "stdout.log").write_text(completed.stdout or "", encoding="utf-8")
    (output_dir / "stderr.log").write_text(completed.stderr or "", encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"Replay failed for {label} with rc={completed.returncode}. "
            f"See {(output_dir / 'stderr.log')}"
        )

    if not keep_snapshots and snapshot_dir.exists():
        for child in snapshot_dir.iterdir():
            if child.is_file():
                child.unlink()

    return summarize_events(label=label, source=source, output_dir=output_dir, event_log=event_log, config=config)


def _resolve_optional_paths(items: list[str]) -> list[str | None]:
    if not items:
        return [None]
    resolved: list[str | None] = []
    for item in items:
        value = str(item).strip()
        if not value:
            resolved.append(None)
            continue
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Override rules file not found: {path}")
        resolved.append(str(path))
    return resolved


def build_replay_configs(args: argparse.Namespace, settings_profile: str) -> list[ReplayConfig]:
    profiles = args.profile or [settings_profile]
    thresholds = list(dict.fromkeys(args.threshold)) if args.threshold else [None]
    process_values = list(dict.fromkeys(args.process_every)) if args.process_every else [None]
    alert_rules = _resolve_optional_paths(args.alert_rules)
    injury_rules = _resolve_optional_paths(args.injury_rules)
    return [
        ReplayConfig(
            profile=profile,
            threshold=threshold,
            process_every=process_every,
            alert_rules=alert_rule,
            injury_rules=injury_rule,
        )
        for profile, threshold, process_every, alert_rule, injury_rule in product(
            profiles,
            thresholds,
            process_values,
            alert_rules,
            injury_rules,
        )
    ]


def main() -> int:
    args = parse_args()
    settings = get_settings()
    run_root = Path(args.benchmark_dir).resolve() / datetime.now().strftime("%Y%m%d_%H%M%S")
    run_root.mkdir(parents=True, exist_ok=True)

    sources = [parse_named_source(item) for item in args.source]
    configs = build_replay_configs(args, settings.fall_detection_profile)
    summaries: list[ReplaySummary] = []
    for label, path in sources:
        for config in configs:
            run_label = f"{label}__{config.slug}"
            summary = run_replay(
                label=run_label,
                source=path,
                output_dir=run_root / run_label,
                config=config,
                status_log_interval=args.status_log_interval,
                keep_snapshots=args.keep_snapshots,
            )
            summaries.append(summary)

    report_path = render_markdown(run_root, summaries)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_root),
        "profiles": [config.profile for config in configs],
        "thresholds": sorted({config.threshold for config in configs if config.threshold is not None}),
        "process_every_values": sorted({config.process_every for config in configs if config.process_every is not None}),
        "config_count": len(configs),
        "summaries": [asdict(item) for item in summaries],
        "report_path": report_path,
    }
    json_path = run_root / "summary.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[replay] Markdown report written to {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

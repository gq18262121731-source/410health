from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".m4v"}
PRIORITY_KEYWORDS = (
    "fall",
    "跌倒",
    "camera",
    "record",
    "screen",
    "clip",
    "video",
    "test",
    "demo",
)


@dataclass
class VideoCandidate:
    path: str
    size_mb: float
    modified_at: str
    keyword_score: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find local video files that may be useful for fall replay benchmarking.")
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        help="Root directory to scan. Repeat to scan multiple roots.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=80,
        help="Maximum number of candidates to keep in the output report.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/fall_replay_benchmark/inputs",
        help="Directory where the inventory report will be written.",
    )
    return parser.parse_args()


def keyword_score(path: Path) -> int:
    haystack = path.as_posix().lower()
    return sum(1 for keyword in PRIORITY_KEYWORDS if keyword in haystack)


def iter_video_files(root: Path) -> list[VideoCandidate]:
    candidates: list[VideoCandidate] = []
    if not root.exists():
        return candidates
    for current_root, _, filenames in os.walk(root, topdown=True, onerror=lambda _: None):
        for filename in filenames:
            path = Path(current_root) / filename
            if path.suffix.lower() not in VIDEO_SUFFIXES:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            candidates.append(
                VideoCandidate(
                    path=str(path),
                    size_mb=round(stat.st_size / (1024 * 1024), 2),
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    keyword_score=keyword_score(path),
                )
            )
    return candidates


def main() -> int:
    args = parse_args()
    roots = [Path(item).expanduser().resolve() for item in args.root] or [
        Path(r"D:\health1"),
        Path(r"D:\Program\model\fall_detection"),
        Path.home() / "Videos",
        Path.home() / "Downloads",
        Path.home() / "Desktop",
    ]

    all_candidates: list[VideoCandidate] = []
    scanned_roots: list[str] = []
    for root in roots:
        scanned_roots.append(str(root))
        all_candidates.extend(iter_video_files(root))

    all_candidates.sort(
        key=lambda item: (
            -item.keyword_score,
            -item.size_mb,
            item.path.lower(),
        )
    )
    top_candidates = all_candidates[: max(1, args.limit)]

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"video_inventory_{stamp}.json"
    md_path = output_dir / f"video_inventory_{stamp}.md"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scanned_roots": scanned_roots,
        "candidate_count": len(all_candidates),
        "candidates": [asdict(item) for item in top_candidates],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Local Video Inventory",
        "",
        f"Generated at: `{payload['generated_at']}`",
        "",
        "## Roots",
        "",
    ]
    lines.extend([f"- `{root}`" for root in scanned_roots])
    lines.extend(
        [
            "",
            f"## Candidates ({len(top_candidates)} / {len(all_candidates)})",
            "",
            "| Path | Size MB | Modified At | Keyword Score |",
            "| --- | ---: | --- | ---: |",
        ]
    )
    for item in top_candidates:
        lines.append(f"| `{item.path}` | {item.size_mb:.2f} | `{item.modified_at}` | {item.keyword_score} |")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"json_path": str(json_path), "markdown_path": str(md_path), **payload}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

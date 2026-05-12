from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate that a joint calibration manifest points to existing local files."
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to the joint calibration manifest JSON.",
    )
    return parser.parse_args()


def resolve_path(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def main() -> int:
    args = parse_args()
    manifest_path = resolve_path(args.manifest)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Manifest not found: {manifest_path}") from exc

    samples = manifest.get("samples") or []
    if not isinstance(samples, list) or not samples:
        raise SystemExit("Manifest has no samples")

    missing: list[dict[str, str]] = []
    existing: list[dict[str, object]] = []

    for sample in samples:
        sample_id = str(sample.get("id") or "").strip() or "unknown"
        raw_path = str(sample.get("path") or "").strip()
        expected_label = str(sample.get("expected_label") or "").strip()
        if not raw_path:
            missing.append({"id": sample_id, "reason": "missing_path"})
            continue
        resolved = resolve_path(raw_path)
        if not resolved.is_file():
            missing.append({"id": sample_id, "reason": "file_not_found", "path": str(resolved)})
            continue
        existing.append(
            {
                "id": sample_id,
                "expected_label": expected_label,
                "path": str(resolved),
                "bytes": resolved.stat().st_size,
            }
        )

    result = {
        "manifest": str(manifest_path),
        "sample_count": len(samples),
        "existing_count": len(existing),
        "missing_count": len(missing),
        "existing": existing,
        "missing": missing,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())

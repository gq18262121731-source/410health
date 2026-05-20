from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download a small public fall-benchmark asset pack from a manifest file."
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to the dataset manifest JSON.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/fall_replay_benchmark/public",
        help="Directory that will receive downloaded assets.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-download files even if they already exist.",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Manifest is not valid JSON: {path}: {exc}") from exc


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response, destination.open("wb") as target:
        shutil.copyfileobj(response, target)


def main() -> int:
    args = parse_args()
    manifest_path = (PROJECT_ROOT / args.manifest).resolve() if not Path(args.manifest).is_absolute() else Path(args.manifest)
    manifest = load_manifest(manifest_path)

    dataset_name = str(manifest.get("name") or manifest_path.stem).strip() or manifest_path.stem
    download_root = str(manifest.get("download_root") or "").rstrip("/")
    samples = manifest.get("samples") or []
    if not download_root:
        raise SystemExit("Manifest missing download_root")
    if not isinstance(samples, list) or not samples:
        raise SystemExit("Manifest missing samples")

    output_dir = (PROJECT_ROOT / args.output_dir / dataset_name).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded: list[dict[str, str]] = []
    for sample in samples:
        filename = str(sample.get("filename") or "").strip()
        sample_id = str(sample.get("id") or filename).strip() or filename
        if not filename:
            raise SystemExit(f"Sample missing filename: {sample}")
        url = f"{download_root}/{filename}"
        target = output_dir / filename
        if target.exists() and not args.overwrite:
            print(f"[skip] {filename}")
        else:
            print(f"[download] {url}")
            download(url, target)
        downloaded.append(
            {
                "id": sample_id,
                "expected_label": str(sample.get("expected_label") or ""),
                "scenario": str(sample.get("scenario") or ""),
                "path": str(target),
            }
        )

    index_path = output_dir / "download_index.json"
    index_path.write_text(
        json.dumps(
            {
                "dataset": dataset_name,
                "source": manifest.get("source"),
                "source_url": manifest.get("source_url"),
                "license": manifest.get("license"),
                "files": downloaded,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(output_dir), "index": str(index_path), "count": len(downloaded)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

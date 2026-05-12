from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from urllib.request import Request, urlopen


DATASETS = [
    {
        "id": "sumitkumarjethani_personal_raw_train",
        "name": "Personal fall/nofall raw frame dataset",
        "source": "sumitkumarjethani/fall-detection GitHub release v0.1",
        "source_url": "https://github.com/sumitkumarjethani/fall-detection/releases/tag/v0.1",
        "url": "https://github.com/sumitkumarjethani/fall-detection/releases/download/v0.1/personal-dataset-raw-train.zip",
        "filename": "personal-dataset-raw-train.zip",
        "size_bytes": 765257567,
        "license_note": "Check the upstream repository before redistribution or commercial use.",
    }
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download public fall-detection datasets used by the local training pipeline.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(r"D:\Program\410health_new\health1\data\fall_eval\downloads"),
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=120) as response, destination.open("wb") as target:
        shutil.copyfileobj(response, target)


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for dataset in DATASETS:
        target = args.output_dir / str(dataset["filename"])
        if target.exists() and not args.overwrite:
            print(f"[skip] {target}")
        else:
            print(f"[download] {dataset['url']}")
            download(str(dataset["url"]), target)
        items.append({**dataset, "path": str(target.resolve()), "downloaded_bytes": target.stat().st_size})
    index = args.output_dir / "public_fall_datasets_index.json"
    index.write_text(json.dumps({"datasets": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"count": len(items), "index": str(index)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

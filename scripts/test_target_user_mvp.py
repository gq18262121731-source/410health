from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.target_user_service import TargetUserService


def main() -> int:
    root = Path(r"D:\Program\410health_new\health1\data")
    model_root = Path(r"D:\Program\model\fall_detection")
    service = TargetUserService(data_root=root, model_root=model_root)

    sample_path = Path(r"D:\Program\410health_new\health1\tmp_normal_frame.jpg")
    if not sample_path.exists():
        raise FileNotFoundError(sample_path)

    created = service.create_user(
        display_name="demo_target_user",
        group="demo",
        note="MVP smoke test target",
        image_blobs=[sample_path.read_bytes()],
    )
    matched = service.match_target_from_image(sample_path.read_bytes())

    print(json.dumps({
        "created_user": created.user.model_dump(mode="json"),
        "warnings": created.warnings,
        "match_result": matched.model_dump(mode="json"),
        "registry_count": len(service.list_users()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

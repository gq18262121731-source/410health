# MMPose pose-visualization reference

This folder intentionally keeps only the license and integration notes from a
temporary sparse checkout of `open-mmlab/mmpose`. The runtime does not import
MMPose and does not vendor MMPose source code.

Reference inspected:

- `mmpose/visualization/fast_visualizer.py`
- `mmpose/visualization/local_visualizer.py`
- COCO top-down pose configs under `configs/body_2d_keypoint/topdown_heatmap/coco`

Ideas integrated into this project:

- Keypoint confidence gating before drawing a limb.
- Separate skeleton-link colors by body part.
- Adaptive visual emphasis: thicker target torso/limbs, point halo, and
  confidence-dependent opacity.
- Target-first top-down flow: detect/lock target ROI first, then estimate and
  render pose only inside that ROI.

Implementation lives in:

- `backend/services/target_pose_service.py`
- `backend/services/target_user_fall_service.py`
- `tools/target-user-console/index.html`

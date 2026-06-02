# Behavior Classifier PoC Report

## Scope

This PoC keeps the current YOLO-Pose pipeline and builds a side-channel behavior
classifier from pose geometry and short motion windows. It does not replace
`app/behavior/rules.py`, does not change Temporal/FallStateMachine, does not
modify detection/pose/tracking services, and does not enter alert logic.

## Recommended Route

Use YOLO-Pose plus a lightweight tabular classifier first.

Recommended first model: `RandomForestClassifier`

Reasons:

- Works well with small-to-medium datasets and mixed missing keypoints.
- Gives stable baselines without GPU training.
- Handles nonlinear geometry such as torso angle, bbox aspect ratio, knee angle,
  and body-height ratios.
- Produces feature importance for debugging bad labels or weak features.
- Lower integration risk than MMAction2/PYSKL/ST-GCN while the dataset is still
  small.

Secondary model for comparison: small `MLPClassifier`

Use GRU/ST-GCN later only after collecting enough labeled temporal clips and
confirming that frame-level geometry is the limiting factor.

## Feature Set

The current PoC extracts these families of features:

- Relative vertical geometry: shoulder, hip, knee, ankle y positions.
- Body proportions: torso height/body height, lower body/body height.
- Shape: bbox aspect ratio.
- Pose angle: torso angle, lower-leg angles, knee angles.
- Relative limb geometry: shoulder/hip/knee/ankle widths and horizontal offsets.
- Motion over recent frames: center dx/dy, normalized speed, vertical speed, and
  motion window span.

Feature names live in `app/behavior/model_classifier.py` and are shared by
collection, training, evaluation, and side-channel inference.

## Dataset Size

Minimum useful PoC target:

- 300-500 usable samples per class.
- 7 classes: standing, walking, sitting, bending, lying, squatting, unknown.
- Total: about 2,100-3,500 labeled person samples.

Better replacement-grade target:

- 1,000-2,000 usable samples per class.
- Total: about 7,000-14,000 samples.
- At least 5-10 people, 3+ camera angles, mixed clothing, lighting, distance,
  and backgrounds.

Temporal model target:

- 300-500 labeled clips per class, not just individual frames.
- Each clip should cover 1-3 seconds with stable track ids.

Important collection notes:

- Balance classes. A model that sees mostly standing people will look accurate
  but fail the states that matter.
- Include hard negatives in `unknown`: partial bodies, occlusion, bad pose,
  crouched non-squatting motion, furniture/person overlap.
- Keep separate validation videos by scene/person. Do not evaluate only on
  frames from the same clips used for training.

## Scripts

Collect labeled pose samples:

```powershell
python scripts\debug_collect_behavior_samples.py --source path\to\clip.mp4 --label standing --frame-stride 5 --limit-samples 500
```

RTSP example:

```powershell
python scripts\debug_collect_behavior_samples.py --source rtsp://user:pass@host/stream --label walking --frame-stride 8 --preview
```

Train:

```powershell
python scripts\train_behavior_classifier.py --dataset datasets\behavior_samples\samples.jsonl --model-type random_forest
```

Evaluate:

```powershell
python scripts\eval_behavior_classifier.py --dataset datasets\behavior_samples\samples.jsonl --model datasets\behavior_samples\behavior_classifier.joblib
```

## Expected Outputs

The collector appends:

- `datasets/behavior_samples/samples.jsonl`
- `datasets/behavior_samples/features.csv`

The trainer writes:

- `datasets/behavior_samples/behavior_classifier.joblib`
- `datasets/behavior_samples/behavior_classifier.train_report.json`

The evaluator writes:

- `datasets/behavior_samples/behavior_classifier.eval_report.json`

Evaluation includes:

- overall accuracy
- confusion matrix
- per-class accuracy
- full sklearn classification report

## Replacement Recommendation

Do not replace `rules.py` yet.

Recommended gate before replacing:

- At least 500 real samples per class for an initial demo comparison.
- Held-out scene/person validation accuracy >= 85%.
- Lying/sitting/squatting/bending confusion inspected manually.
- Walking recall stable across at least two camera angles.
- Unknown false positives acceptable for the demo setting.
- A runtime fallback remains available when pose is missing or model confidence
  is low.

Near-term best use:

- Run `BehaviorModelClassifier` as a side-channel comparator.
- Log model predictions beside current rule decisions.
- Use disagreement cases to guide more sample collection.

Once model confidence is proven, integrate as:

- model-first when pose confidence and classifier confidence are high
- rules fallback when keypoints are missing, model artifact is unavailable, or
  confidence is low

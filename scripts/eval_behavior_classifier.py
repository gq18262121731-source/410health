from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.behavior.model_classifier import BEHAVIOR_LABELS, FEATURE_NAMES
from scripts.train_behavior_classifier import load_dataset

DEFAULT_DATASET = ROOT / "datasets" / "behavior_samples" / "samples.jsonl"
DEFAULT_MODEL = ROOT / "datasets" / "behavior_samples" / "behavior_classifier.joblib"
DEFAULT_REPORT = ROOT / "datasets" / "behavior_samples" / "behavior_classifier.eval_report.json"


def evaluate(args: argparse.Namespace) -> dict:
    import joblib
    import numpy as np
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

    artifact = joblib.load(args.model)
    model = artifact["model"] if isinstance(artifact, dict) else artifact
    feature_names = list(artifact.get("feature_names") or FEATURE_NAMES) if isinstance(artifact, dict) else FEATURE_NAMES

    rows, labels = load_dataset(Path(args.dataset))
    if not rows:
        raise RuntimeError("dataset is empty")

    x = np.array([[row.get(name, float("nan")) for name in feature_names] for row in rows], dtype=float)
    y_true = np.array(labels)
    y_pred = model.predict(x)
    present_labels = [label for label in BEHAVIOR_LABELS if label in set(y_true) or label in set(y_pred)]

    per_class_accuracy = {}
    by_label = defaultdict(lambda: {"correct": 0, "total": 0})
    for expected, predicted in zip(y_true, y_pred):
        by_label[str(expected)]["total"] += 1
        if expected == predicted:
            by_label[str(expected)]["correct"] += 1
    for label, stats in by_label.items():
        per_class_accuracy[label] = round(stats["correct"] / max(1, stats["total"]), 4)

    report = {
        "dataset": str(Path(args.dataset).resolve()),
        "model": str(Path(args.model).resolve()),
        "sample_count": int(len(y_true)),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "labels": present_labels,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=present_labels).tolist(),
        "per_class_accuracy": per_class_accuracy,
        "classification_report": classification_report(
            y_true,
            y_pred,
            labels=present_labels,
            zero_division=0,
            output_dict=True,
        ),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a side-channel behavior classifier.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(args)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

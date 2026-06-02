from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.behavior.model_classifier import BEHAVIOR_LABELS, FEATURE_NAMES, PoseFeatureBuilder

DEFAULT_DATASET = ROOT / "datasets" / "behavior_samples" / "samples.jsonl"
DEFAULT_MODEL = ROOT / "datasets" / "behavior_samples" / "behavior_classifier.joblib"


def load_dataset(path: Path) -> tuple[list[dict[str, float]], list[str]]:
    if path.suffix.lower() == ".jsonl":
        return load_jsonl_dataset(path)
    if path.suffix.lower() == ".csv":
        return load_csv_dataset(path)
    raise ValueError(f"unsupported dataset type: {path}")


def load_jsonl_dataset(path: Path) -> tuple[list[dict[str, float]], list[str]]:
    builder = PoseFeatureBuilder()
    rows: list[dict[str, float]] = []
    labels: list[str] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            label = str(record.get("label") or "")
            if label not in BEHAVIOR_LABELS:
                raise ValueError(f"invalid label at line {line_number}: {label!r}")
            rows.append(builder.extract(record))
            labels.append(label)
    return rows, labels


def load_csv_dataset(path: Path) -> tuple[list[dict[str, float]], list[str]]:
    rows: list[dict[str, float]] = []
    labels: list[str] = []
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        missing = [name for name in ["label", *FEATURE_NAMES] if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"csv is missing columns: {missing}")
        for row in reader:
            label = str(row.get("label") or "")
            if label not in BEHAVIOR_LABELS:
                raise ValueError(f"invalid label in csv: {label!r}")
            rows.append({name: float(row[name]) if row[name] not in {"", "nan", "None"} else float("nan") for name in FEATURE_NAMES})
            labels.append(label)
    return rows, labels


def build_model(model_type: str, random_state: int) -> Any:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    if model_type == "random_forest":
        classifier = RandomForestClassifier(
            n_estimators=260,
            min_samples_leaf=3,
            class_weight="balanced",
            random_state=random_state,
            n_jobs=-1,
        )
        return Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("classifier", classifier),
        ])
    if model_type == "mlp":
        return Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("classifier", MLPClassifier(
                hidden_layer_sizes=(64, 32),
                alpha=0.001,
                max_iter=800,
                random_state=random_state,
            )),
        ])
    raise ValueError(f"unsupported model type: {model_type}")


def train(args: argparse.Namespace) -> dict[str, Any]:
    import joblib
    import numpy as np
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
    from sklearn.model_selection import train_test_split

    rows, labels = load_dataset(Path(args.dataset))
    if not rows:
        raise RuntimeError("dataset is empty")
    label_counts = Counter(labels)
    stratify = labels if min(label_counts.values()) >= 2 and len(label_counts) > 1 else None

    x = np.array([[row.get(name, float("nan")) for name in FEATURE_NAMES] for row in rows], dtype=float)
    y = np.array(labels)
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=stratify,
    )
    model = build_model(args.model_type, args.random_state)
    model.fit(x_train, y_train)
    y_pred = model.predict(x_test)
    present_labels = [label for label in BEHAVIOR_LABELS if label in set(y)]
    report = {
        "dataset": str(Path(args.dataset).resolve()),
        "model_type": args.model_type,
        "sample_count": int(len(y)),
        "train_count": int(len(y_train)),
        "test_count": int(len(y_test)),
        "labels": present_labels,
        "label_counts": dict(label_counts),
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "confusion_matrix": confusion_matrix(y_test, y_pred, labels=present_labels).tolist(),
        "classification_report": classification_report(
            y_test,
            y_pred,
            labels=present_labels,
            zero_division=0,
            output_dict=True,
        ),
    }

    artifact = {
        "model": model,
        "feature_names": FEATURE_NAMES,
        "labels": BEHAVIOR_LABELS,
        "report": report,
    }
    model_path = Path(args.output)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_path)

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return {**report, "model_path": str(model_path)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a side-channel pose behavior classifier.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="JSONL raw samples or generated features CSV.")
    parser.add_argument("--output", default=str(DEFAULT_MODEL))
    parser.add_argument("--report", default=str(DEFAULT_MODEL.with_suffix(".train_report.json")))
    parser.add_argument("--model-type", choices=["random_forest", "mlp"], default="random_forest")
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = train(args)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

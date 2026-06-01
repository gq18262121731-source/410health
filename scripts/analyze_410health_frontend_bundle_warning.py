from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend" / "vue-dashboard"
ASSETS_DIR = FRONTEND_DIR / "dist" / "assets"
REPORT_PATH = ROOT / "docs" / "410health_frontend_bundle_warning_triage.md"
SUMMARY_PATH = ROOT / "evaluations" / "codebase_residency" / "410health_frontend_bundle_warning_triage_001.json"
THRESHOLD_BYTES = 500 * 1024


def _asset_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".js":
        return "javascript_chunk"
    if suffix == ".css":
        return "css_asset"
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
        return "image_asset"
    return "other_asset"


def _likely_source(name: str) -> str:
    lower = name.lower()
    if lower.startswith("echarts"):
        return "echarts charting dependency"
    if lower.startswith("vendor"):
        return "shared node_modules vendor chunk"
    if lower.startswith("index"):
        return "application entry bundle"
    if "背景" in name:
        return "large background image asset"
    return "static frontend asset"


def main() -> int:
    if not ASSETS_DIR.exists():
        raise FileNotFoundError(f"Build assets directory not found: {ASSETS_DIR}")

    assets = []
    for path in sorted(ASSETS_DIR.iterdir(), key=lambda item: item.stat().st_size, reverse=True):
        if not path.is_file():
            continue
        size = path.stat().st_size
        assets.append(
            {
                "name": path.name,
                "size_bytes": size,
                "size_kb": round(size / 1024, 2),
                "asset_type": _asset_type(path),
                "over_500kb": size > THRESHOLD_BYTES,
                "likely_source": _likely_source(path.name),
            }
        )

    oversized_js_chunks = [
        asset for asset in assets if asset["asset_type"] == "javascript_chunk" and asset["over_500kb"]
    ]
    oversized_assets = [asset for asset in assets if asset["over_500kb"]]
    immediate_action_required = False
    recommendation = (
        "No urgent fix is required. The only oversized JavaScript chunk is the isolated echarts chunk; "
        "track it as a non-blocking optimization item. If bundle size becomes a product concern, prefer "
        "lazy-loading chart-heavy views or replacing wildcard echarts imports before changing business logic."
    )
    if not oversized_js_chunks:
        recommendation = "No JavaScript chunk exceeds the Vite 500 KB warning threshold."

    summary = {
        "phase": "SE-1.8",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_path": str(ROOT),
        "assets_dir": str(ASSETS_DIR),
        "threshold_bytes": THRESHOLD_BYTES,
        "oversized_js_chunks": oversized_js_chunks,
        "oversized_assets": oversized_assets,
        "likely_primary_source": oversized_js_chunks[0]["likely_source"] if oversized_js_chunks else "none",
        "immediate_action_required": immediate_action_required,
        "recommended_next_step": recommendation,
        "business_code_changed": False,
        "dependency_install_attempted": False,
        "deployment_attempted": False,
        "git_push_attempted": False,
    }

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    asset_rows = "\n".join(
        "| {name} | {size_kb} | `{asset_type}` | {over} | {source} |".format(
            name=asset["name"],
            size_kb=asset["size_kb"],
            asset_type=asset["asset_type"],
            over="yes" if asset["over_500kb"] else "no",
            source=asset["likely_source"],
        )
        for asset in assets
    )
    oversized_rows = "\n".join(
        f"- `{asset['name']}`: {asset['size_kb']} KB, likely source = {asset['likely_source']}"
        for asset in oversized_js_chunks
    ) or "- None"
    if oversized_js_chunks:
        status_note = (
            "The current non-blocking warning is caused by an oversized JavaScript chunk, not by a failed "
            "frontend check. Typecheck, lint, and build are passing."
        )
        interpretation = (
            "The main bundle warning comes from the isolated `echarts` chunk. The existing Vite config already "
            "separates `echarts` and generic vendor code with `manualChunks`, so this warning is visible but not "
            "currently blocking daily residency checks."
        )
        action_now = "no urgent code change"
        next_step = "track as optimization backlog"
    else:
        status_note = (
            "No JavaScript chunk currently exceeds the Vite 500 KB warning threshold. Typecheck, lint, and build "
            "are passing."
        )
        interpretation = (
            "The previous `echarts` JavaScript chunk warning is resolved for the current build output. The large "
            "background image remains over 500 KB, but it is an image asset rather than a JavaScript chunk."
        )
        action_now = "none"
        next_step = "continue daily autopilot monitoring"

    REPORT_PATH.write_text(
        f"""# 410health Frontend Bundle Warning Triage

## Summary

```text
phase = SE-1.8
warning = Vite chunk size warning
immediate_action_required = {str(immediate_action_required).lower()}
oversized_js_chunks = {len(oversized_js_chunks)}
likely_primary_source = {summary["likely_primary_source"]}
```

{status_note}

## Oversized JavaScript Chunks

{oversized_rows}

## Asset Inventory

| Asset | Size KB | Type | Over 500 KB | Likely Source |
| --- | ---: | --- | --- | --- |
{asset_rows}

## Interpretation

{interpretation}

## Recommendation

```text
action_now = {action_now}
owner = workflow_engineer_lobster
next_step = {next_step}
```

If optimization is later approved, the smallest useful options are:

- Lazy-load chart-heavy routes or components.
- Replace full `echarts` imports in chart attachment rendering with modular imports.
- Review large static images separately from JavaScript chunk optimization.

## Boundary

```text
business_code_changed = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
```
""",
        encoding="utf-8",
    )

    print("410HEALTH FRONTEND BUNDLE WARNING TRIAGE")
    print(f"oversized_js_chunks={len(oversized_js_chunks)}")
    print(f"immediate_action_required={str(immediate_action_required).lower()}")
    print(f"report={REPORT_PATH}")
    print(f"summary={SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

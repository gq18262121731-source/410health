# 410health Frontend Bundle Warning Triage

## Summary

```text
phase = SE-1.8
warning = Vite chunk size warning
immediate_action_required = false
oversized_js_chunks = 1
likely_primary_source = echarts charting dependency
```

The current non-blocking warning is caused by an oversized JavaScript chunk, not by a failed frontend check. Typecheck, lint, and build are passing.

## Oversized JavaScript Chunks

- `echarts-uvSR9kx1.js`: 803.9 KB, likely source = echarts charting dependency

## Asset Inventory

| Asset | Size KB | Type | Over 500 KB | Likely Source |
| --- | ---: | --- | --- | --- |
| echarts-uvSR9kx1.js | 803.9 | `javascript_chunk` | yes | echarts charting dependency |
| 背景-BST42LBB.jpg | 586.57 | `image_asset` | yes | large background image asset |
| vendor-C6rcS8xd.js | 394.07 | `javascript_chunk` | no | shared node_modules vendor chunk |
| index-CnSZujhV.js | 190.73 | `javascript_chunk` | no | application entry bundle |
| 家人-PiVEYYcF.png | 183.11 | `image_asset` | no | static frontend asset |
| 社区-DZuva8oZ.png | 161.49 | `image_asset` | no | static frontend asset |
| index-CWabLZDF.css | 145.67 | `css_asset` | no | application entry bundle |
| 老人-BELZloj1.png | 115.25 | `image_asset` | no | static frontend asset |

## Interpretation

The main bundle warning comes from the isolated `echarts` chunk. The existing Vite config already separates `echarts` and generic vendor code with `manualChunks`, so this warning is visible but not currently blocking daily residency checks.

The large background image is also over 500 KB, but the Vite warning shown during build is primarily about JavaScript chunk size after minification.

## Recommendation

```text
action_now = no urgent code change
owner = workflow_engineer_lobster
next_step = track as optimization backlog
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

# 410health Daily Residency Check Report

## Summary

```text
project = D:\Program\410health
created_at = 2026-05-28T07:52:24.961883+00:00
overall_status = passed
business_code_changed = false
frontend_failure_reason = none
```

## Checks

| Check | Command | Status | Exit Code |
| --- | --- | --- | --- |
| Git status | `git status --short` | passed | 0 |
| Backend pytest | `conda run -n helth pytest` | passed | 0 |
| Frontend check | `npm run check` | passed | 0 |

## Git Status

```text
?? scripts/run_410health_daily_ops_chain.py
```

## Backend Pytest Tail

```text



tests\test_alarm_service.py ........                                     [  8%]

tests\test_chat_agent_api.py .....                                       [ 13%]

tests\test_demo_overlay.py .........                                     [ 23%]

tests\test_device_registration_flow.py ..................                [ 42%]

tests\test_display_sample_resolution.py ......                           [ 48%]

tests\test_health_api.py .......                                         [ 55%]

tests\test_inference.py ...                                              [ 58%]

tests\test_langchain_rag_service.py .....                                [ 64%]

tests\test_omni_logic.py .....                                           [ 69%]

tests\test_rag_health.py .                                               [ 70%]

tests\test_rag_incremental.py .                                          [ 71%]

tests\test_rule_engine.py ....                                           [ 75%]

tests\test_runtime_bootstrap.py .......                                  [ 83%]

tests\test_runtime_tasks.py .                                            [ 84%]

tests\test_serial_parser.py ........                                     [ 92%]

tests\test_serial_reader.py .......                                      [100%]



======================= 95 passed in 102.27s (0:01:42) ========================


```

## Frontend Check Tail

```text

> ai-health-iot-dashboard@0.1.0 check
> npm run typecheck && npm run lint && npm run build


> ai-health-iot-dashboard@0.1.0 typecheck
> vue-tsc --noEmit


> ai-health-iot-dashboard@0.1.0 lint
> eslint src --ext .ts,.vue


> ai-health-iot-dashboard@0.1.0 build
> vite build

[36mvite v6.4.2 [32mbuilding for production...[36m[39m
transforming...
[32m✓[39m 2483 modules transformed.
rendering chunks...
computing gzip size...
[2mdist/[22m[32mindex.html                  [39m[1m[2m  1.00 kB[22m[1m[22m[2m │ gzip:   0.58 kB[22m
[2mdist/[22m[32massets/老人-BELZloj1.png      [39m[1m[2m118.01 kB[22m[1m[22m
[2mdist/[22m[32massets/社区-DZuva8oZ.png      [39m[1m[2m165.37 kB[22m[1m[22m
[2mdist/[22m[32massets/家人-PiVEYYcF.png      [39m[1m[2m187.50 kB[22m[1m[22m
[2mdist/[22m[32massets/背景-BST42LBB.jpg      [39m[1m[2m600.65 kB[22m[1m[22m
[2mdist/[22m[35massets/index-CWabLZDF.css   [39m[1m[2m149.17 kB[22m[1m[22m[2m │ gzip:  26.12 kB[22m
[2mdist/[22m[36massets/index-CnSZujhV.js    [39m[1m[2m195.31 kB[22m[1m[22m[2m │ gzip:  61.60 kB[22m
[2mdist/[22m[36massets/vendor-C6rcS8xd.js   [39m[1m[2m403.52 kB[22m[1m[22m[2m │ gzip: 150.88 kB[22m
[2mdist/[22m[36massets/echarts-uvSR9kx1.js  [39m[1m[33m823.19 kB[39m[22m[2m │ gzip: 270.32 kB[22m
[32m✓ built in 9.58s[39m
```

## Notes

Backend and frontend checks passed.

This runner is the minimal Software Open Claw daily residency check. It only observes repository state and runs existing verification commands. It does not install dependencies, deploy, push, or modify business code.

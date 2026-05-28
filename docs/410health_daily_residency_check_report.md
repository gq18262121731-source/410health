# 410health Daily Residency Check Report

## Summary

```text
project = D:\Program\410health
created_at = 2026-05-28T02:26:51.197689+00:00
overall_status = failed
business_code_changed = false
frontend_failure_reason = npm_run_check_failed
```

## Checks

| Check | Command | Status | Exit Code |
| --- | --- | --- | --- |
| Git status | `git status --short` | passed | 0 |
| Backend pytest | `conda run -n helth pytest` | passed | 0 |
| Frontend check | `npm run check` | failed | 1 |

## Git Status

```text
 M docs/410health_daily_residency_check_report.md
 M scripts/run_410health_daily_residency_check.py
?? evaluations/codebase_residency/410health_daily_residency_check_002.json
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



======================= 95 passed in 102.51s (0:01:42) ========================


```

## Frontend Check Tail

```text

> ai-health-iot-dashboard@0.1.0 check
> npm run typecheck && npm run lint && npm run build


> ai-health-iot-dashboard@0.1.0 typecheck
> vue-tsc --noEmit


> ai-health-iot-dashboard@0.1.0 lint
> eslint src --ext .ts,.vue


D:\Program\410health\frontend\vue-dashboard\src\components\SOSSimulator.vue
  2:15  error  'computed' is defined but never used        @typescript-eslint/no-unused-vars
  5:7   error  'props' is assigned a value but never used  @typescript-eslint/no-unused-vars

D:\Program\410health\frontend\vue-dashboard\src\composables\useDeviceTrend.ts
  7:10  error  'parseBloodPressure' is defined but never used  @typescript-eslint/no-unused-vars

D:\Program\410health\frontend\vue-dashboard\src\views\auth\AuthLoginPage.vue
  3:8  error  'heartImage' is defined but never used  @typescript-eslint/no-unused-vars

✖ 4 problems (4 errors, 0 warnings)

```

## Notes

Backend checks passed. Frontend tooling is available and `npm run check` was executed, but the frontend check failed. The runner records the failure without installing dependencies or modifying frontend code.

This runner is the minimal Software Open Claw daily residency check. It only observes repository state and runs existing verification commands. It does not install dependencies, deploy, push, or modify business code.

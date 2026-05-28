# 410health Daily Residency Check Report

## Summary

```text
project = D:\Program\410health
created_at = 2026-05-28T01:52:38.272501+00:00
overall_status = failed
business_code_changed = false
```

## Checks

| Check | Command | Status | Exit Code |
| --- | --- | --- | --- |
| Git status | `git status --short` | passed | 0 |
| Backend pytest | `conda run -n helth pytest` | passed | 0 |
| Frontend check | `npm run check` | failed | None |

## Git Status

```text
?? docs/410health_daily_residency_check_report.md
?? evaluations/codebase_residency/410health_daily_residency_check_001.json
?? scripts/run_410health_daily_residency_check.py
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



======================= 95 passed in 101.64s (0:01:41) ========================


```

## Frontend Check Tail

```text
command not found: npm
```

## Notes

This runner is the minimal Software Open Claw daily residency check. It only observes repository state and runs existing verification commands. It does not install dependencies, deploy, push, or modify business code.

# 410health Autopilot Failure Drill Report

## Summary

```text
phase = SE-2.4
drill_status = passed
case_count = 4
cases_passed = 4
business_code_changed = false
```

This drill uses synthetic daily check JSON files. It does not modify business code or force real failures in the project.

## Drill Cases

| Case | Expected Owner | Expected Task | Result |
| --- | --- | --- | --- |
| backend_failed | qa_reviewer_lobster | `triage_backend_pytest_failure` | passed |
| frontend_failed | qa_reviewer_lobster | `triage_frontend_check_failure` | passed |
| git_dirty | safety_officer_lobster | `inspect_dirty_workspace` | passed |
| warning_only | workflow_engineer_lobster | `track_vite_chunk_size_warning` | passed |

## Interpretation

```text
backend fail -> qa_reviewer_lobster
frontend fail -> qa_reviewer_lobster
git dirty -> safety_officer_lobster
warning only -> workflow_engineer_lobster
```

The current autopilot can route both healthy and unhealthy daily states to the correct employee owner.

## Boundary

```text
business_code_changed = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
```

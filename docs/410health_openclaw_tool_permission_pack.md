# SE-4.4: OpenClaw Tool Permission Pack

## Summary

```text
phase = SE-4.4
result = passed
project = 410health
default_mode = observe_and_report
```

The 410health Software Open Claw tool permission pack is registered locally at:

```text
D:\Program\software_open_claw_local_config\410health_tool_permission_pack.json
```

## Auto-Allowed Tools

```text
python scripts/run_410health_daily_autopilot.py
python scripts/build_410health_daily_ops_summary.py
python scripts/build_410health_residency_history_index.py
python scripts/route_410health_daily_tasks.py
python scripts/build_410health_autopilot_triage_note.py
```

These tools are observe/report tools. They do not edit business code, install dependencies, deploy, push, or merge.

## Approval Required

```text
git commit
git push
git merge
dependency install
deployment
file delete
business code edit
frontend code edit
backend code edit
remote branch delete
gateway service repair
daemon install
```

## Prohibited By Default

```text
git reset --hard
git clean
force push
delete project files
modify secrets
modify production configuration
expose OpenClaw Gateway beyond loopback
```

## Validation

```text
tool_registry_loaded = true
dangerous_action_blocked = true
daily_autopilot_tool_allowed = true
```

## Boundary

```text
business_code_changed = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
```

# Software Open Claw Handoff - 2026-05-28

## 1. Original Goal

The original goal was:

```text
Learn, collect, and extract different skills.
Use tools to turn yourself or other people into reusable skills.
Connect those skills to Open Claw.
Let different lobster employees use different skills and thinking styles.
Eventually make them become the leader's employees.
```

The current interpretation of Open Claw has been corrected:

```text
Open Claw at this stage = Software Open Claw
Software Open Claw = digital employee tool-calling and workflow execution substrate
```

It does not currently mean physical robot hardware. Physical Open Claw can remain a future branch, but the active mainline is software engineering residency: digital employees can read a project, run tools, inspect status, repair code with approval, generate reports, route tasks, and maintain the project safely.

## 2. Current Project

```text
project_path = D:\Program\410health
project_type = FastAPI backend + Vue/Vite frontend + IoT serial/MQTT + AI/Agent/RAG
git_branch = master
current_status = clean
backend_pytest = 95 passed
frontend_check = typecheck / lint / build passed
daily_autopilot = passed
blocking_task_count = 0
recommended_next_owner = workflow_engineer_lobster
```

The current non-blocking watch item is:

```text
watch_item = Vite chunk-size warning
primary_source = echarts charting dependency
severity = non_blocking
action_now = no urgent code change
```

## 3. What Has Been Completed

### 3.1 Simulation-first Digital Employee Factory

The broader factory work has already established:

```text
21 skills
13 lobster agents
4 team compositions
4 learning tracks
simulation tasks
simulation records
reviews
scores
runner
failure drill
history reports
leadership reports
```

This proved that digital employees can be represented as role-based agents with skills, team workflows, and auditable task results.

### 3.2 410health Real-code Residency Validation

410health became the first real-code Software Open Claw validation target.

Initial backend test state:

```text
81 passed, 14 failed
```

Final backend test state:

```text
95 passed, 0 failed
```

The digital employee repair loop completed these real fixes:

| Trial | Result | Type |
| --- | --- | --- |
| Trial 001 | RAG incremental test isolation | test stability |
| Trial 002 | Demo overlay persona expectation alignment | test expectation |
| Trial 003 | Health free_chat search trigger | production logic |
| Trial 004 | Omni elder safety system prompt | production logic |
| Trial 005 | LangChain RAG manifest assertion alignment | test expectation |
| Trial 006 | Active SOS dedupe by event time | production logic |
| SE-1.0A | Active serial target semantics | production logic |
| SE-1.0B | Demo directory variable name alignment | test expectation |
| SE-1.0C | `unbind_device_self` care service seam | production seam |
| SE-1.4 | Frontend unused-vars cleanup | frontend lint |

All fixes followed the residency SOP:

```text
branch
  -> minimal fix
  -> targeted test
  -> full test
  -> report
  -> leader approval
  -> controlled merge
  -> audit
```

No unapproved push, deploy, dependency install, or destructive command was performed.

### 3.3 Daily Operation System

Software Open Claw now has a working daily operation chain:

```text
daily check
  -> daily ops summary
  -> lobster team room
  -> history trend
  -> task routing
  -> triage note
```

The non-technical operator shortcut is:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_410health_daily_autopilot.ps1
```

Equivalent Python command:

```powershell
python scripts/run_410health_daily_autopilot.py
```

Expected healthy output:

```text
daily_ops_chain = passed
task_routing = passed
blocking_task_count = 0
recommended_next_owner = workflow_engineer_lobster
autopilot_status = passed
```

## 4. Key Files And Commands

### 4.1 Primary Commands

Run the full daily autopilot:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_410health_daily_autopilot.ps1
```

Run the Python equivalent:

```powershell
python scripts/run_410health_daily_autopilot.py
```

Run the underlying daily ops chain:

```powershell
python scripts/run_410health_daily_ops_chain.py
```

Run only the project check:

```powershell
python scripts/run_410health_daily_residency_check.py
```

Run backend tests directly:

```powershell
conda run -n helth pytest
```

Run frontend check directly:

```powershell
npm run check --prefix frontend/vue-dashboard
```

### 4.2 Tool Registry And Protocol

```text
docs/software_open_claw_tool_registry.md
evaluations/codebase_residency/software_open_claw_tool_registry.json
docs/software_open_claw_employee_operating_protocol.md
evaluations/codebase_residency/software_open_claw_employee_operating_protocol.json
```

### 4.3 Daily Operation Outputs

```text
docs/410health_daily_autopilot_report.md
docs/410health_daily_ops_summary.md
docs/410health_lobster_team_room.md
docs/410health_residency_history_summary.md
docs/410health_daily_task_routing.md
docs/410health_autopilot_triage_note.md
evaluations/codebase_residency/410health_daily_autopilot_001.json
evaluations/codebase_residency/410health_daily_ops_chain_001.json
evaluations/codebase_residency/410health_daily_task_routing_001.json
evaluations/codebase_residency/410health_autopilot_triage_note_001.json
```

### 4.4 Diagnostic Outputs

```text
docs/410health_frontend_bundle_warning_triage.md
evaluations/codebase_residency/410health_frontend_bundle_warning_triage_001.json
docs/410health_autopilot_failure_drill_report.md
evaluations/codebase_residency/410health_autopilot_failure_drill_001.json
```

## 5. Current Employee Roles

```text
workflow_engineer_lobster
  Runs daily ops chain.
  Maintains check -> report -> history -> routing flow.
  Owns current non-blocking Vite warning backlog.

product_manager_lobster
  Reads daily summary.
  Converts status into leader-facing priority and release posture.

qa_reviewer_lobster
  Reviews failed backend/frontend checks.
  Classifies evidence before any repair branch.

safety_officer_lobster
  Checks approval boundary.
  Blocks deploy, push, dependency install, destructive commands, and unapproved merge.
```

## 6. Safety Boundary

Allowed without leader approval:

```text
observe
run existing tests
run daily autopilot
generate reports
summarize history
diagnose non-blocking warnings
```

Requires leader approval:

```text
business code change
frontend code change
dependency install
deployment
git push
branch merge
destructive filesystem operation
production configuration change
```

Never do casually:

```text
git reset --hard
git clean
delete files
push to remote
deploy
install unknown dependencies
auto-merge a repair
modify production code while system is running
```

## 7. What To Do After The Two-day Rest

### Step 1: Resume With A Health Check

From `D:\Program\410health`:

```powershell
git status
powershell -ExecutionPolicy Bypass -File .\scripts\run_410health_daily_autopilot.ps1
```

Expected:

```text
git_status_clean = true
autopilot_status = passed
blocking_task_count = 0
```

If this passes, continue observation.

If this fails, do not immediately edit code. Read:

```text
docs/410health_daily_task_routing.md
docs/410health_autopilot_triage_note.md
```

Then assign according to the router:

```text
backend fail -> qa_reviewer_lobster
frontend fail -> qa_reviewer_lobster
git dirty -> safety_officer_lobster
warning only -> workflow_engineer_lobster
```

### Step 2: Recommended Next Feature

The next logical module is:

```text
SE-2.6: Autopilot Triage Note Integration Into Daily Autopilot
```

Purpose:

```text
Make run_410health_daily_autopilot.py also call build_410health_autopilot_triage_note.py.
```

Current state:

```text
autopilot runs daily ops chain + task routing
triage note is a separate command
```

Desired state:

```text
autopilot runs daily ops chain + task routing + triage note
```

Minimal change:

```text
Update scripts/run_410health_daily_autopilot.py
Add third step:
  python scripts/build_410health_autopilot_triage_note.py
Refresh docs/410health_daily_autopilot_report.md
Refresh evaluations/codebase_residency/410health_daily_autopilot_001.json
```

Validation:

```powershell
python scripts/run_410health_daily_autopilot.py
```

Expected:

```text
daily_ops_chain = passed
task_routing = passed
triage_note = passed
autopilot_status = passed
blocking_task_count = 0
```

### Step 3: Optional Later Improvements

Do only after SE-2.6:

```text
SE-2.7: Add timestamped output files instead of overwriting *_001 / *_003
SE-2.8: Add lightweight Yuque/team-room export adapter
SE-2.9: Add issue/backlog file for non-blocking warnings
SE-3.0: Controlled branch creation helper for approved repairs
```

Do not jump into dependency installation, deployment, remote push, or automatic code repair without leader approval.

## 8. Current Known Watch Items

### Vite Chunk-size Warning

```text
status = non_blocking
source = echarts charting dependency
size = about 803.9 KB
owner = workflow_engineer_lobster
action = track in optimization backlog
```

Do not optimize immediately unless leader asks. It does not block:

```text
typecheck
lint
build
daily autopilot
```

### README Encoding

The existing README contains historical mojibake text. Do not rewrite it wholesale unless explicitly asked. A clean Software Open Claw Daily Autopilot section has been added near the top.

## 9. Current Git Anchors

Recent important commits:

```text
b7ed4cb tool: build autopilot triage note
ede652f test: add autopilot failure routing drill
3077651 docs: refresh daily autopilot shortcut output
ada77d7 docs: add daily autopilot shortcut
e26a404 docs: refresh 410health daily autopilot pass
b4bee52 tool: add 410health daily autopilot
dda9fa8 tool: route 410health daily tasks
6160f1d docs: define software open claw employee protocol
2143b44 docs: register software open claw tools
```

Before doing new work, run:

```powershell
git status
git log --oneline -n 5
```

## 10. One-line Memory

```text
We started with the goal of turning skills into digital lobster employees. The current working implementation is Software Open Claw for 410health: a real project residency system that repaired backend tests to 95 passed, made frontend checks pass, and now runs daily autopilot with reporting, routing, history, and triage notes under strict approval boundaries.
```

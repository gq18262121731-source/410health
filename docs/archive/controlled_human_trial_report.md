# Controlled Human Trial Report

Generated at: 2026-05-25T12:05:08.399927+00:00

## Scope

This report is for Phase 5.21 controlled human trial logging. It does not train models, does not modify Temporal/FallStateMachine, and does not call alert POST/snapshot paths.

## Trial Setup

- Label: `human_trial_001`
- Camera ID: `camera_01`
- Duration: `1801.66` seconds
- Status samples: `1783`
- WebSocket result samples: `0`
- Manual markers: `0`

## Runtime Summary

- Service states: `{'unknown': 1783}`
- Diagnostics true counts: `{}`
- Status failures: `0`
- Main max frame age: `None` ms
- Analysis max frame age: `None` ms
- Main restart delta: `35`
- Analysis restart delta: `35`
- Watchdog restart delta: `None`
- Watchdog suppressed seen: `False`

## Pipeline Summary

- Analysis capture FPS avg: `0.0`
- Detection worker FPS avg: `0.0`
- Tracking worker FPS avg: `10.71`
- Result publish FPS avg: `0.0`
- Pose FPS avg: `0.0`
- Pose skipped_due_to_busy delta: `0`
- Pose circuit open seen: `False`

## Fall Preview Summary

- Fall states seen: `[]`
- Max fall probability: `None`
- Confirmed count: `0`

## Action Windows

| Action | Start(s) | End(s) | Samples | States Seen | Max Prob | Confirmed | First State Change(ms) |
| --- | ---: | ---: | ---: | --- | ---: | --- | ---: |
| _No manual action windows recorded_ | | | | | | | |

## Frontend Observation Checklist

- Main video is clear and live: TODO
- BBox aligns with person: TODO
- Skeleton aligns with person: TODO
- Fast motion only shows minor overlay delay: TODO
- Browser console has no errors: TODO
- False positive observed: TODO
- Missed high-risk transition observed: TODO

## Safety Notes

- Do not ask real elderly users to perform dangerous falls.
- Safe fall simulation should use soft padding and slow controlled motion only.
- Confirmed fall remains preview-only in Phase 5; no official alert POST is triggered.

## Raw Logs

- JSON summary: `D:\vision_service\logs\human_trial\20260525_193506_human_trial_001_summary.json`
- Status samples JSONL: `D:\vision_service\logs\human_trial\20260525_193506_human_trial_001_status.jsonl`
- WebSocket result samples JSONL: `D:\vision_service\logs\human_trial\20260525_193506_human_trial_001_results.jsonl`
- Markers JSONL: `D:\vision_service\logs\human_trial\20260525_193506_human_trial_001_markers.jsonl`

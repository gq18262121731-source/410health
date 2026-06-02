# Docs Index

## Current Delivery Docs

These documents stay in the `docs/` root because they describe the current project baseline, operating method, and execution rules.

- [video_stream_stability_playbook.md](D:\vision_service\docs\video_stream_stability_playbook.md)
  - Current engineering execution playbook for video stability, latency, synchronization, and staged optimization.
- [run_phase5_demo.md](D:\vision_service\docs\run_phase5_demo.md)
  - Current runtime/demo startup notes.
- [phase5_final_acceptance_record.md](D:\vision_service\docs\phase5_final_acceptance_record.md)
  - Current Phase 5 final acceptance-style summary.

## Archive

Historical phase reports, experiments, benchmarks, and intermediate acceptance notes have been moved to:

- [archive/](D:\vision_service\docs\archive)

These files are kept for traceability, but they are not the primary source for current execution decisions.

## Cleanup Rule

Use this convention going forward:

- Keep only current delivery / operating / policy documents in `docs/`
- Move phase reports, experiments, smoke results, and temporary validation notes into `docs/archive/`
- Use the playbook as the current execution standard, not historical reports

## Single Source Guidance

For future engineering work:

- Current execution standard: `video_stream_stability_playbook.md`
- Current run/start reference: `run_phase5_demo.md`
- Historical traceability: `docs/archive/`

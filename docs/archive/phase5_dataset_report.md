# Phase 5 Dataset Evaluation Report

This report evaluates the current rule-based Temporal Decision Layer.
It does not train models, does not use GRU/LSTM, and does not modify runtime rules.

## Summary

- Tested videos: 18
- Normal videos: 11
- Fall videos: 7
- False positive confirmed: 0
- False positive candidate: 0
- Fall detected: 5
- Fall missed: 2
- ADL unstable rate: 0/11 (0.00%)
- ADL candidate FP: 0
- ADL confirmed FP: 0
- Fall falling recall: 5/7 (71.43%)
- Fall candidate recall: 0/7 (0.00%)
- Fall confirmed recall: 0/7 (0.00%)

## Phase 5.8 Tuning Notes

Phase 5.8 focused on suppressing low-level ADL false positives without relaxing
`fallen_candidate` or `fallen_confirmed`.

- `adl-12.mp4` previously reached `falling` because a controlled ADL transition
  produced a medium bbox descent (`max_delta_y=37.9`) and the previous rules were
  still too sensitive to velocity-like evidence. It now remains `normal`.
- `adl-13.mp4` briefly became the new false-positive candidate during tuning
  because it had a larger but still controlled bbox descent (`max_delta_y=49.4`)
  without low-posture confirmation. The final rule requires stronger falling
  evidence before moving out of `normal`, so it now remains `normal`.
- `fall-09.mp4` previously only reached `unstable`; after tuning, the strong bbox
  descent (`max_delta_y=62.1`) is sufficient to enter `falling`.
- The offline runner can inflate velocity values because frames are processed
  faster than real time. The current rules therefore rely more on bbox displacement
  and posture evidence than raw velocity.

Current decision: keep GRU postponed. The preview layer has better ADL stability,
but the sample size is still small and `candidate/confirmed` recall is intentionally
not optimized yet.

## Per Video

- `ur_fall/adl-01.mp4` label=adl frames=150 sampled=30 max_prob=0.23 states=['normal'] confirmed=False risk_peak=low max_vy=9930000.0 max_dy=14.5 max_ratio=0.61 pose_frames=23
- `ur_fall/adl-02.mp4` label=adl frames=180 sampled=36 max_prob=0.15 states=['normal'] confirmed=False risk_peak=low max_vy=15230000.0 max_dy=21.3 max_ratio=0.58 pose_frames=21
- `ur_fall/adl-03.mp4` label=adl frames=180 sampled=36 max_prob=0.11 states=['normal'] confirmed=False risk_peak=low max_vy=625000.0 max_dy=13.2 max_ratio=0.58 pose_frames=30
- `ur_fall/adl-04.mp4` label=adl frames=150 sampled=30 max_prob=0.23 states=['normal'] confirmed=False risk_peak=low max_vy=9940000.0 max_dy=13.3 max_ratio=0.57 pose_frames=22
- `ur_fall/adl-05.mp4` label=adl frames=180 sampled=36 max_prob=0.23 states=['normal'] confirmed=False risk_peak=low max_vy=9790000.0 max_dy=17.8 max_ratio=0.60 pose_frames=32
- `ur_fall/adl-06.mp4` label=adl frames=230 sampled=46 max_prob=0.23 states=['normal'] confirmed=False risk_peak=low max_vy=6740000.0 max_dy=10.5 max_ratio=0.52 pose_frames=36
- `ur_fall/adl-10.mp4` label=adl frames=300 sampled=60 max_prob=0.33 states=['normal'] confirmed=False risk_peak=low max_vy=586.0 max_dy=36.9 max_ratio=0.96 pose_frames=47
- `ur_fall/adl-12.mp4` label=adl frames=250 sampled=50 max_prob=0.39 states=['normal'] confirmed=False risk_peak=low max_vy=806.3 max_dy=37.9 max_ratio=0.48 pose_frames=32
- `ur_fall/adl-13.mp4` label=adl frames=265 sampled=53 max_prob=0.67 states=['normal'] confirmed=False risk_peak=low max_vy=784.2 max_dy=49.4 max_ratio=0.54 pose_frames=27
- `ur_fall/adl-14.mp4` label=adl frames=235 sampled=47 max_prob=0.23 states=['normal'] confirmed=False risk_peak=low max_vy=28945000.0 max_dy=28.9 max_ratio=0.49 pose_frames=23
- `ur_fall/adl-15.mp4` label=adl frames=275 sampled=55 max_prob=0.11 states=['normal'] confirmed=False risk_peak=low max_vy=12340000.0 max_dy=20.3 max_ratio=0.49 pose_frames=26
- `ur_fall/fall-01.mp4` label=fall frames=160 sampled=32 max_prob=0.91 states=['normal', 'falling'] confirmed=False risk_peak=high max_vy=1530000.0 max_dy=67.4 max_ratio=0.74 pose_frames=19
- `ur_fall/fall-02.mp4` label=fall frames=110 sampled=22 max_prob=0.61 states=['normal'] confirmed=False risk_peak=low max_vy=12530000.0 max_dy=44.4 max_ratio=0.62 pose_frames=10
- `ur_fall/fall-03.mp4` label=fall frames=215 sampled=43 max_prob=0.33 states=['normal'] confirmed=False risk_peak=low max_vy=37470000.0 max_dy=37.5 max_ratio=1.99 pose_frames=37
- `ur_fall/fall-04.mp4` label=fall frames=96 sampled=20 max_prob=0.85 states=['normal', 'falling'] confirmed=False risk_peak=high max_vy=17970000.0 max_dy=46.7 max_ratio=1.07 pose_frames=7
- `ur_fall/fall-05.mp4` label=fall frames=151 sampled=31 max_prob=0.67 states=['normal', 'falling'] confirmed=False risk_peak=high max_vy=4425000.0 max_dy=53.8 max_ratio=0.50 pose_frames=18
- `ur_fall/fall-09.mp4` label=fall frames=185 sampled=37 max_prob=0.73 states=['normal', 'falling'] confirmed=False risk_peak=high max_vy=4505000.0 max_dy=62.1 max_ratio=0.44 pose_frames=25
- `ur_fall/fall-10.mp4` label=fall frames=130 sampled=26 max_prob=0.91 states=['normal', 'falling', 'unstable'] confirmed=False risk_peak=high max_vy=12145000.0 max_dy=59.3 max_ratio=1.62 pose_frames=10

## Suggestions

- Some fall videos were missed: lower rapid descent thresholds or add bbox center-y trend features.
- Editable files for next tuning: app/temporal/mock_sequence_model.py and app/temporal/fall_state_machine.py.

## Artifacts

- `D:\vision_service\logs\phase5_dataset_eval\summary.json`
- `D:\vision_service\logs\phase5_dataset_eval\per_video.jsonl`

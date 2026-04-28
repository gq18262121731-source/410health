# 私有场景适配工作流

## 1. 采集视频

把真实摄像头或监控视频放到：

`data_private/camera_scene/raw_videos`

或直接录制：

```powershell
python .\scripts\capture_scene_video.py --source 0
```

## 2. 事件级标注

```powershell
python .\scripts\annotate_fall_events.py --video D:\path\to\your_video.mp4
```

建议标注：

- `fall`
- `fallen`
- `lie_down`
- `sit_down`
- `bending`
- `walking`
- `other`
- `recovery`

## 3. 生成私有 manifest

```powershell
python .\scripts\build_private_manifest.py
```

## 4. 合并公私有清单

```powershell
python .\scripts\merge_video_manifests.py
```

## 5. 提取新视频的 pose / posture risk 缓存

```powershell
python .\scripts\extract_pose_cache.py --manifest D:\Program\model\fall_detection\data_processed\video_manifest_adapted.csv --datasets private_scene
```

```powershell
python .\scripts\extract_posture_risk_cache.py --manifest D:\Program\model\fall_detection\data_processed\video_manifest_adapted.csv
```

## 6. 定向再训练

```powershell
python .\scripts\train_temporal_tcn_transformer.py --manifest D:\Program\model\fall_detection\data_processed\video_manifest_adapted.csv --run-name hybrid_tcn_transformer_private_v1
```

```powershell
python .\scripts\train_temporal_semantic_mix.py --video-manifest D:\Program\model\fall_detection\data_processed\video_manifest_adapted.csv --run-name semantic_mix_falldb_private_v1
```

## 7. 重新搜索融合权重

```powershell
python .\scripts\search_fusion_weights.py --manifest D:\Program\model\fall_detection\data_processed\video_manifest_adapted.csv --hybrid-weights D:\Program\model\fall_detection\weights\hybrid_tcn_transformer_private_v1.pt --semantic-weights D:\Program\model\fall_detection\weights\semantic_mix_falldb_private_v1.pt
```

# 410health 跌倒检测模型说明文档

## 1. 文档目的

本文件用于向 `410health` 项目成员说明当前跌倒检测模型的：

- 技术路线
- 训练方法
- 使用的数据来源
- 调优过程
- 当前优势与局限
- 实际部署与运行方式
- 后续继续优化的方法

本交付包**不包含训练数据集**，只包含可运行模型核心、权重、必要脚本与说明文档，方便项目团队直接复用。

---

## 2. 模型定位

当前模型不是一个“单一 YOLO 分类器”，而是一套**多分支融合的事件级跌倒检测系统**，重点面向：

- 固定摄像头监控
- 室内养老/看护场景
- 单人或少量多人画面
- 本地 GPU 推理

它的目标不是只判断“这一帧像不像跌倒”，而是尽量回答：

- 当前是否发生了跌倒事件
- 当前是否处于倒地后的高风险状态
- 如何降低“坐下、躺下、弯腰”等误报

---

## 3. 核心技术路线

当前系统采用四层思路：

### 3.1 感知层

使用 `YOLO pose` 前端提取人体关键点和人体框。

当前使用：

- `yolo11n-pose.pt`

作用：

- 找到人
- 输出人体关键点
- 为后续时序模型提供姿态变化信息

### 3.2 时序层一：GRU 分支

这是第一条时间序列判断分支：

- 输入：人体关键点序列 + 边界框动态特征
- 模型：`GRU`
- 特点：相对稳定，误报控制较好

当前权重：

- `gru_pose_fall_v1.pt`

### 3.3 时序层二：TCN + Transformer 分支

这是第二条时间序列判断分支：

- 输入：关键点动态 + 姿态风险缓存
- 模型：`TCN + Transformer Encoder`
- 特点：更容易捕捉短时跌倒过程，召回更高

当前主权重：

- `hybrid_tcn_transformer_v2_matchgru.pt`

### 3.4 时序层三：语义时序混合分支

这是第三条时序分支，用于增强跨域语义理解：

- 输入一：RGB 视频中提取的统一语义时序特征
- 输入二：`FallDatabase` 的骨架序列语义特征
- 模型：`SemanticTemporalNet`
- 目的：让模型不仅记住 RGB staged 数据，还能学习骨架域的跌倒语义

当前权重：

- `semantic_mix_falldb_v1.pt`

### 3.5 姿态辅助分支

这是静态风险辅助分支：

- 输入：人体裁剪图
- 模型：`YOLO11s-cls`
- 标签：`risk / safe`

当前权重：

- `posture_person_binary_best.pt`

这条分支不单独负责报警，而是提供“当前姿态是否低位高风险”的先验信息。

### 3.6 融合决策层

最终不是某一条分支单独说了算，而是多分支加权融合：

- `GRU` 分支：偏稳
- `Hybrid` 分支：偏高召回
- `Semantic` 分支：偏跨域语义
- `Posture` 分支：偏静态风险先验

然后再经过：

- 分数阈值
- 连续多帧确认
- 轨迹级去抖动

来决定是否真正输出跌倒报警。

---

## 4. 我们使用了哪些数据

### 4.1 公共 RGB 视频数据

#### UR Fall Detection Dataset (URFD)

- 70 个视频
- 包含跌倒与日常动作
- 官方页：<https://fenix.ur.edu.pl/~mkepski/ds/uf.html>

作用：

- 快速建立可运行的 RGB 跌倒事件基线

#### GMDCSA24

- 150 个 RGB 视频
- 官方记录：<https://zenodo.org/records/11216408>

作用：

- 提供更多演员、视角、动作过渡样本

### 4.2 公共姿态/姿势数据

#### Fall Pose Dataset

- 21 个已下载姿态序列
- 主要包含：
  - standing
  - sitting
  - lying
  - bending
  - crawling
  - other
- 来源：<https://falldataset.com/>

作用：

- 训练姿态辅助模型
- 强化对 hard negative 的区分能力

### 4.3 公共骨架/深度数据

#### FallDatabase

- 72 个骨架序列
- 组成：40 个跌倒 + 32 个日常动作
- 原始说明来自随包 `readme.pdf`
- 数据包来源：<https://zenodo.org/records/3886586>

作用：

- 不直接用于 RGB 分类
- 用于训练跨域语义时序分支
- 增强模型对跌倒动态的抽象理解

### 4.4 标签统一与辅助基准

#### OmniFall / WanFall

- 用于统一标签体系和切分定义
- 参考：
  - <https://huggingface.co/datasets/simplexsigil2/omnifall>
  - <https://huggingface.co/datasets/simplexsigil2/wanfall>

作用：

- 降低不同数据集标签口径不一致的问题

---

## 5. 我们是如何训练的

### 5.1 第一阶段：建立基础可用模型

先用：

- `YOLO pose + GRU`

建立第一版跌倒检测模型，目标是：

- 跑通数据
- 跑通本地 GPU
- 跑通视频推理链路

### 5.2 第二阶段：加入姿态辅助分支

利用 `Fall Pose Dataset` 做两种辅助模型：

- 全图姿态分类
- 人体裁剪 `risk/safe` 二分类

最终保留的是：

- 人体裁剪 `risk/safe` 二分类分支

因为它更符合真实推理时的输入分布。

### 5.3 第三阶段：加入更强时序分支

新增：

- `TCN + Transformer` 混合时序模型

目的：

- 提升对“正在跌倒”的捕获能力
- 与 GRU 形成互补

### 5.4 第四阶段：接入 FallDatabase

我们没有把 `FallDatabase` 粗暴当成另一个 RGB 数据集，而是做了更合理的处理：

- 只提取 `skeleton.txt`
- 转成统一的语义时序特征
- 与 RGB pose 时序共同训练语义混合分支

这样做的好处是：

- 保留了骨架数据的动态语义
- 避免强行把 depth 图塞进现有 RGB 流程

### 5.5 第五阶段：做融合权重搜索

不是拍脑袋设置融合权重，而是对多分支分数进行扫描搜索，比较：

- `accuracy`
- `precision`
- `recall`
- `f1`

并根据 held-out 测试结果挑出更合理的默认配置。

---

## 6. 当前模型效果如何

### 6.1 单分支结果

#### GRU 分支

- accuracy 约 `0.8011`
- precision 约 `0.3918`
- recall 约 `0.7170`

特点：

- 更稳
- 对“已经倒地”的识别较好
- 但误报仍偏高

#### Hybrid TCN + Transformer 分支

- 更偏高召回
- 单独使用时更激进
- 适合作为补充分支，而不是独立最终报警器

#### Semantic Mix + FallDatabase 分支

- accuracy 约 `0.7977`
- precision 约 `0.5642`
- recall 约 `0.7254`
- f1 约 `0.6348`

特点：

- 跨域语义能力更好
- 单分支表现比预期稳定
- 更适合做增强分支，而不是直接替代主分支

#### 姿态风险分支

- 测试总体准确率约 `0.8187`
- risk recall 约 `0.7756`
- safe recall 约 `0.8355`

特点：

- 对“低位高风险姿态”识别有效
- 能帮助抑制部分误报

### 6.2 多分支融合结果

在公开测试窗口上，已有结果显示：

- `GRU only` 最优 `F1 ≈ 0.5102`
- `GRU + posture` 最优 `F1 ≈ 0.5382`
- `GRU + hybrid + posture` 最优 `F1 ≈ 0.5694`

这说明系统不是靠某一个模型硬撑，而是通过多分支融合得到更好的综合效果。

---

## 7. 和真实研究方向相比，我们模型的优势在哪里

这里必须实话实说：

- 我们当前模型**不是学术 benchmark 上最前沿的单模型 SOTA**
- 但它在**工程可落地性**和**监控场景适配性**上有明显优势

### 7.1 优势一：不是单一姿态分类器，而是事件级系统

很多普通跌倒检测实现，本质上只是：

- 单帧 YOLO
- 单窗口分类

我们的系统已经具备：

- 姿态感知
- 多分支时序理解
- 轨迹级决策
- 事件级报警逻辑

这比“看一眼像不像躺着”更接近实际项目需求。

### 7.2 优势二：融合了 RGB、骨架语义和静态风险先验

当前系统同时使用：

- RGB 视频时序
- pose 动态
- posture risk
- `FallDatabase` 骨架语义

这使得模型更有自己的结构特点，不只是“把 YOLO 换大一点”。

### 7.3 优势三：已经具备私有场景适配工具链

相比很多只会训练公开数据集的模型，我们现在已经有：

- 本地录制脚本
- 事件级标注脚本
- 私有 manifest 生成
- 公私有清单合并
- 定向再训练
- 融合权重搜索

这意味着一旦有你自己的摄像头视频，团队可以快速完成二次适配。

### 7.4 优势四：可以在本地 Windows + RTX 5060 上稳定运行

这一点很实际：

- 我们已经在本机上完成训练与推理
- 模型、脚本、缓存和权重都已经能跑通

很多更前沿的工具链虽然论文更强，但在你的当前环境上并不一定更容易落地。

---

## 8. 当前局限在哪里

项目成员也必须清楚当前限制：

1. 公开数据集和真实摄像头场景仍有域差
2. 真实场景里的 hard negative 仍可能触发误报
3. 当前最强配置仍然需要你自己的监控视频做最后定向校准
4. 目前没有把真正私有场景最终权重训完，因为机器上还没有你的真实监控视频素材

换句话说：

当前模型适合：

- 内测
- 联调
- 方案展示
- 小规模验证

如果要做真正的稳定上线，还必须再走一轮私有场景标注与重训。

---

## 9. 运行环境如何配置

### 9.1 推荐环境

当前模型是在如下环境中训练和验证的：

- Windows
- Python `3.10`
- CUDA `12.8`
- PyTorch `2.11.0+cu128`
- Ultralytics `8.3.107`

### 9.2 推荐依赖

见本包中的：

- `requirements-fall-detection.txt`

### 9.3 推荐方式

优先方式：

- 使用单独的 Python 环境运行本包

如果团队已有统一环境，也可手动安装以下核心依赖：

- `torch`
- `torchvision`
- `torchaudio`
- `ultralytics`
- `opencv-python`
- `numpy`
- `pandas`
- `pypdf`
- `py7zr`

---

## 10. 这个包里有哪些核心文件

### 10.1 关键权重

- `weights/gru_pose_fall_v1.pt`
- `weights/hybrid_tcn_transformer_v2_matchgru.pt`
- `weights/semantic_mix_falldb_v1.pt`
- `weights/posture_person_binary_best.pt`
- `weights/yolo11n-pose.pt`

### 10.2 关键运行脚本

- `scripts/realtime_fall_monitor.py`
- `scripts/run_fall_monitor_bundle.py`

### 10.3 关键训练/适配脚本

- `scripts/annotate_fall_events.py`
- `scripts/build_private_manifest.py`
- `scripts/merge_video_manifests.py`
- `scripts/extract_pose_cache.py`
- `scripts/extract_posture_risk_cache.py`
- `scripts/train_temporal_tcn_transformer.py`
- `scripts/train_temporal_semantic_mix.py`
- `scripts/search_fusion_weights.py`

---

## 11. 项目人员如何使用这个模型

### 11.1 最简单的推理方式

在包根目录执行：

```powershell
python .\scripts\run_fall_monitor_bundle.py --source 0
```

如果要跑视频：

```powershell
python .\scripts\run_fall_monitor_bundle.py --source D:\path\to\video.mp4 --save-path D:\path\to\out.mp4 --no-display
```

### 11.2 如果要替换成自己的监控视频

把视频放到：

- `data_private/camera_scene/raw_videos`

然后用：

```powershell
python .\scripts\annotate_fall_events.py --video D:\...\your_video.mp4
```

完成事件级标注。

### 11.3 如果要做定向再训练

流程如下：

1. 生成私有清单
2. 合并公私有 manifest
3. 重新提取 pose / posture risk cache
4. 重训 `hybrid`
5. 重训 `semantic_mix`
6. 重新搜索融合权重

具体命令见：

- `docs/private_scene_workflow.md`

---

## 12. 当前默认配置建议

### 12.1 面向当前公开/通用测试的默认建议

优先使用：

- `GRU + Hybrid + Posture`

推荐默认值：

- `gru_weight = 0.30`
- `hybrid_weight = 0.45`
- `semantic_weight = 0.00`
- `posture_weight = 0.25`
- `threshold = 0.45`

### 12.2 面向私有场景适配流程的模板建议

在 dry-run 验证中，搜索到的一个可用模板是：

- `gru_weight = 0.15`
- `hybrid_weight = 0.25`
- `semantic_weight = 0.30`
- `posture_weight = 0.30`
- `threshold = 0.40`

注意：

这只是**私有场景适配流程已打通**的证明，不是你真实摄像头场景的最终最优值。

---

## 13. 如果以后继续优化，最值得做什么

优先级建议如下：

1. 收集你自己的真实摄像头视频
2. 做事件级标注，而不是只看单帧/单窗口
3. 增加 hard negative
4. 用私有数据做定向再训练
5. 重新搜索融合权重
6. 再考虑迁移到 `RTMPose / RTMO`

---

## 14. 外部真实资料与参考

### 数据与任务相关

- URFD 官方页  
  <https://fenix.ur.edu.pl/~mkepski/ds/uf.html>

- GMDCSA24  
  <https://zenodo.org/records/11216408>

- FallDatabase  
  <https://zenodo.org/records/3886586>

- OmniFall  
  <https://huggingface.co/datasets/simplexsigil2/omnifall>

### 技术路线参考

- OmniFall: From Staged Through Synthetic to Wild  
  <https://arxiv.org/abs/2505.19889>

- TCN + Transformer fall detection paper  
  <https://www.sciencedirect.com/science/article/pii/S1574119225000057>

- RTMO (CVPR 2024)  
  <https://openaccess.thecvf.com/content/CVPR2024/papers/Lu_RTMO_Towards_High-Performance_One-Stage_Real-Time_Multi-Person_Pose_Estimation_CVPR_2024_paper.pdf>

- FACT (CVPR 2024)  
  <https://openaccess.thecvf.com/content/CVPR2024/papers/Lu_FACT_Frame-Action_Cross-Attention_Temporal_Modeling_for_Efficient_Action_Segmentation_CVPR_2024_paper.pdf>

- TE-TAD (CVPR 2024)  
  <https://openaccess.thecvf.com/content/CVPR2024/papers/Kim_TE-TAD_Towards_Full_End-to-End_Temporal_Action_Detection_via_Time-Aligned_Coordinate_CVPR_2024_paper.pdf>

---

## 15. 最终结论

这套模型当前最大的价值，不在于“某个单指标绝对最高”，而在于它已经形成了一套**可训练、可推理、可适配、可继续进化**的跌倒检测系统：

- 能跑
- 能训
- 能适配私有场景
- 能在本地 GPU 上工作
- 能输出明确的后续优化路径

对于 `410health` 项目来说，这比一个只能在公开数据集上好看的单模型更有实际价值。

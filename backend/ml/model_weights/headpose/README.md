# 姿态检测模型文件

后端默认从本目录读取三个文件：

| 文件 | 大小 | 仓库状态 |
| --- | --- | --- |
| `deploy.prototxt` | 28,104 字节 | 已包含，OpenCV DNN 人脸检测网络定义 |
| `pose-estimator.h5` | 81,841,920 字节 | 完整数据保存在 10 个分片中，运行脚本还原 |
| `res10_300x300_ssd_iter_140000.caffemodel` | 10,666,211 字节 | 已包含，人脸检测权重 |

## 还原姿态模型

因上传接口的单次传输大小限制，姿态模型保存为 `pose-estimator.h5.part01` 至 `pose-estimator.h5.part10`。在项目根目录执行：

```powershell
python backend/ml/model_weights/headpose/restore_weights.py
```

脚本仅使用 Python 标准库，不依赖 TensorFlow。它按 `weights-manifest.json` 的顺序读取分片，核对各分片大小与 SHA-256，再验证完整文件并生成同目录的 `pose-estimator.h5`。

完整文件 SHA-256：

```text
9fdfad7e55a6bedf77544151ae8591b36f5fa954865a2622b02e9311ec29af97
```

已有且校验正确的模型会跳过；已有文件不匹配时会报错并保留原文件。缺少分片或校验失败时不会生成不完整模型。还原后的 `.h5` 已被 `.gitignore` 排除，避免重复提交原文件与分片。

## 推理环境

当前姿态模型按 Python 3.7 + TensorFlow 1.15 集成。`pose-estimator.h5` 输出 Tilt / Pan；Roll 由 OpenCV 双眼连线估计，不是该权重的直接输出。`backend/ml/train_model.py` 是另一套评估分类训练脚本，不能用于直接生成上述姿态权重。

后端启动后，可调用 `GET /api/assessment/pose/status` 查看文件是否齐备；成功加载和实际推理仍需在兼容环境下验证。

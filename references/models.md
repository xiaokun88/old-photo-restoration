# 开源项目的角色与使用边界

以下是按任务选择的候选工具，并非安装清单。运行前查看上游最新文档、模型权重来源和许可；本 Skill 不附带第三方代码或模型文件。

| 项目 | 适用情况 | 需要注意 | 来源与许可 |
| --- | --- | --- | --- |
| [GFPGAN](https://github.com/TencentARC/GFPGAN) | 人脸模糊、低清；可输出整图中的修复人脸 | 生成式修复可能改变身份特征。先比较原图与保真版，必要时弃用 | [README](https://github.com/TencentARC/GFPGAN#readme)、[Apache-2.0 许可](https://github.com/TencentARC/GFPGAN/blob/master/LICENSE) |
| [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) | 整图或背景放大、常见压缩退化 | 放大后像素变多不等于找回真实细节；避免多轮反复放大 | [README](https://github.com/xinntao/Real-ESRGAN#readme)、[BSD-3-Clause 许可](https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE) |
| [Bringing Old Photos Back to Life](https://github.com/microsoft/Bringing-Old-Photos-Back-to-Life) | 明显划痕与整体老化；用户有这类照片时再启用 | 上游说明其主要面向研究，任意分辨率效果不稳定 | [README](https://github.com/microsoft/Bringing-Old-Photos-Back-to-Life#readme)、[MIT 许可](https://github.com/microsoft/Bringing-Old-Photos-Back-to-Life/blob/master/LICENSE) |
| [CodeFormer](https://github.com/sczhou/CodeFormer) | 作为 GFPGAN 之外的人脸修复候选；可调保真权重 | 保真权重提高通常更接近输入，但结果仍需核查；其 NTU S-Lab License 1.0 不是通用宽松许可证 | [README](https://github.com/sczhou/CodeFormer#readme)、[许可](https://github.com/sczhou/CodeFormer/blob/master/LICENSE) |

## 选择顺序

1. 先检查照片；没有人脸时不要启动人脸模型。有多张脸时逐一核对，不仅看中央人物。
2. 保真版优先使用可解释的轻度处理。增强版可先做单次适度放大；GFPGAN 只在用户希望增强人脸且环境可用时运行。
3. 出现眼睛、嘴形、面部轮廓或年龄特征变化时，尝试降低增强强度或换模型；保留原图、保真版与未采用的结果供比较。
4. 大面积缺损与黑白上色存在多种合理结果，应单独征询用户偏好，并显著标注为推测。

## 已有 GFPGAN 环境的调用

上游推理入口为 `inference_gfpgan.py`。本 Skill 的脚本只使用已存在的仓库和主权重，并传入 `--bg_upsampler none`，避免背景模型自动下载；上游人脸检测仍可能需要辅助权重，所以运行 GFPGAN 还要求 `--allow-upstream-downloads`。若要额外使用 Real-ESRGAN，请按其上游文档准备模型，并在完成后对照原图检查整体纹理。不要从不明镜像下载模型，也不要将私人人像上传未获授权的在线演示站。

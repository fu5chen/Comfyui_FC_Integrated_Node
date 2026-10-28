# ComfyUI FC Integrated Node

ComfyUI 自定义节点：模型与多 LoRA 一体加载、图片缩放与模型超分、文件夹顺序读图、保存图片和滑动对比。所有节点均支持中文搜索。

## 安装

在 ComfyUI 的 `custom_nodes` 目录打开终端：

```bash
git clone https://github.com/fu5chen/Comfyui_FC_Integrated_Node.git
```

重启 ComfyUI，并在浏览器按 **Ctrl+F5** 刷新。也可以通过 GitHub 的 **Code → Download ZIP** 下载，把解压后的文件夹放入 `ComfyUI/custom_nodes/`。

已有旧版 `comfyui_image_folder_nodes` 的用户请用本仓库替换旧插件，避免同时安装两份导致同名节点冲突。已有工作流的内部节点 ID 保持不变。

## 节点

| 节点 | 功能 | 中文搜索词示例 |
| --- | --- | --- |
| FC Load model | 扩散模型、单文本编码器和多 LoRA 一体加载，输出 MODEL / CLIP | 模型加载、加载模型、多LoRA |
| FC_image_Zoom | 按比例缩放或使用超分模型放大，输出图片与宽高 | 图片放大、图片缩放、模型放大、超分 |
| FC Load Image | 按文件名自然排序或修改时间，顺序读取文件夹图片 | 读取图片、文件夹图片、批量读图 |
| FC Save Image | 保存到指定路径，自动递增文件名 | 保存图片、导出图片 |
| FC Image Compare | 鼠标移动进行 A/B 对比，滚轮缩放整个画布 | 图片对比、图像对比、滑动对比 |

## 模型与多 LoRA

1. `model_name`：选择扩散模型，来自 ComfyUI 的 `models/diffusion_models` 路径。
2. `clip_name`：选择匹配的文本编码器，来自 `models/text_encoders`。
3. `clip_type`：选择原工作流对应的类型，默认 `krea2`，列表与当前 ComfyUI 原生 CLIPLoader 同步。例如使用 MOSS 时，需安装支持该类型的 ComfyUI，并选择对应的 `moss_image` 类型与文本编码器。
4. 每项 LoRA 只占一行：**LoRA 文件 | M 模型强度 | C CLIP 强度**。选中文件后自动应用，选择 `None` 不应用。C 仅对包含文本编码器权重的 LoRA 有效。
5. 底部 **− / +** 按钮栏用于减少最后一项或新增一项，最多 64 项，按从上到下顺序应用。列表和强度会随工作流保存。

`weight_dtype` 建议保留 `default`；`clip_device=cpu` 可降低文本编码的显存需求，但可能更慢。调整 LoRA 时复用基础模型和文本编码器，避免重复读盘；每次从基础模型重新应用 LoRA，避免强度累积。

**VAE 单独加载。** 本节点复用原生 UNETLoader 和单 CLIPLoader，不涵盖 GGUF 专用加载器或双/多文本编码器加载流程；类型列表中的条目不表示可以共用同一个编码器。原工作流所需的采样设置与模型处理节点仍需保留。

## 图片缩放与模型超分

- **按比例缩放**：插值调整尺寸，不加载超分模型。
- **模型放大**：使用原生超分后端分块处理，再调整到目标倍率。
- `scale_by` 始终表示相对原图的最终倍率：`0.5` 缩小一半，`2` 放大两倍。
- 支持批量图片和 RGBA 透明通道，输出 `image / width / height`。尺寸按整数像素舍入。

仓库已包含官方轻量通用模型 **realesr-general-x4v3.pth**（约 4.7 MiB）。插件会注册内置模型目录，无需搬动模型文件。也可选择 `ComfyUI/models/upscale_models/` 下的其他原生兼容模型。

普通缩放不会增加真实细节，模型超分可能改变纹理。内置模型原生放大 4 倍，因此即使目标为 2 倍，也会先完成模型推理再缩至目标尺寸。

## 图片对比

预览使用 1px 半透明分割线，无中间手柄。鼠标左右移动即可对比，双击回到中间。鼠标停在预览上滚动滚轮时，事件会传给 ComfyUI 画布进行整体缩放。

## 依赖与验证

复用 ComfyUI 的 Python 环境，包括 torch、numpy、Pillow、folder_paths 和原生超分后端 spandrel。不需要额外安装第三方节点，不会自动下载模型或安装依赖。建议使用更新的 ComfyUI；普通比例缩放不加载超分后端。

已验证：实际 CPU 模型超分、比例缩放、批量、RGBA、目标倍率和模型缓存；多 LoRA、类型切换、工作流保存恢复及滚轮转发完成模拟测试。GPU、实际浏览器交互及各 CLIP 类型的真实权重组合尚未逐一验证。

## 内置模型来源与许可证

- 项目：[Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN)
- [官方模型说明](https://github.com/xinntao/Real-ESRGAN/blob/master/docs/model_zoo.md)
- [官方权重下载](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth)
- 第三方模型许可证：[BSD 3-Clause](models/Real-ESRGAN-LICENSE.txt)
- 权重 SHA256：`8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292`

第三方模型的授权声明保留在 `models/Real-ESRGAN-LICENSE.txt` 中。

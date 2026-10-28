"""
ComfyUI 自定义节点：文件夹图片顺序读取 + 指定路径保存 + 通用图片对比（均带节点内预览）
依赖：ComfyUI 自带环境（torch / numpy / PIL / folder_paths），无需额外安装。

节点一 FCLoadImage（FC Load Image）
  - folder_path：图片所在文件夹路径
  - reset：勾选后本次从第 1 张重新开始
  - start_index：填 >=0 的数字直接跳到该张（0 起算），并从此位置继续往后；-1 表示沿用当前进度
  - sort_by：name(文件名自然数字序) / time(修改时间)
  - 每次执行读取"下一张"，指针 +1 持久化到 load_state.json；末尾循环回开头
  - 节点预览顶部标注 [第几张/总数] 文件名
  - 输出 image / mask / filename / index

节点二 FCSaveImage（FC Save Image）
  - images：上游 IMAGE
  - output_path：留空默认 ComfyUI output 目录；可写自定义路径
  - filename_prefix：文件名前缀，默认 ComfyUI
  - 每次按 前缀_00001.png 自动递增，不覆盖
  - 节点预览顶部标注实际保存路径
  - 输出 saved_path

节点三 FCCompareImages（FC Image Compare）—— 通用图片对比（拖动滑块）
  - image_a / image_b：任意两张 IMAGE（如 原图 vs Krea2/Z-Image/Moss 生成图），与具体模型无关
  - label_a / label_b：两侧标注文字（默认 输入 / 输出）
  - 节点内渲染可拖动分割线的对比滑块：按住左右拖动，分割线左侧显示 A、右侧显示 B
  - 同时把两张图透传输出，方便接后续节点
  - 输出 image_a / image_b
  - 前端交互由 web/compare.js 提供（WEB_DIRECTORY 自动加载）

关键说明：
1) 输入不变时 ComfyUI 会复用缓存、不再执行函数。用 IS_CHANGED 返回自增计数强制每次重新执行。
2) 节点内预览通过返回 {"ui": {"images": [...]}, "result": (...)} 实现；图片若在 ComfyUI 目录外，
   每次把带标注的当前图拷到 temp 目录供前端显示。
"""

import os
import re
import json
import torch
import numpy as np
from PIL import Image, ImageOps, ImageDraw, ImageFont

import folder_paths

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "load_state.json")
_EXEC_COUNTER = 0  # 用于 IS_CHANGED，强制每次排队重新执行
VALID_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff")


def _normalize_path(p):
    return "" if p is None else os.path.normpath(p.strip())


def _load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def _natural_key(name):
    """自然数字排序键：img2 排在 img10 前面；中英文文件名同样适用。"""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def _list_images(folder, sort_by="name"):
    if not folder or not os.path.isdir(folder):
        return []
    files = [f for f in os.listdir(folder) if f.lower().endswith(VALID_EXT)]
    if sort_by == "time":
        files.sort(key=lambda f: os.path.getmtime(os.path.join(folder, f)))
    else:
        files.sort(key=_natural_key)
    return files


def _load_font(size=24):
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _fit_font(draw, text, max_width, start_size=26):
    size = start_size
    while size > 10:
        font = _load_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
        size -= 2
    return _load_font(10)


def _draw_label(pil_img, text):
    img = pil_img.convert("RGB").copy()
    draw = ImageDraw.Draw(img)
    pad = 6
    max_w = img.width - pad * 2
    font = _fit_font(draw, text, max_w)
    bbox = draw.textbbox((0, 0), text, font=font)
    bar_h = (bbox[3] - bbox[1]) + pad * 2
    draw.rectangle([0, 0, img.width, bar_h], fill=(0, 0, 0))
    draw.text((pad, pad), text, fill=(255, 255, 0), font=font)
    return img


def _temp_preview(pil_img, base_name):
    temp_dir = folder_paths.get_temp_directory()
    os.makedirs(temp_dir, exist_ok=True)
    fn = f"{base_name}.png"
    pil_img.save(os.path.join(temp_dir, fn))
    return {"filename": fn, "subfolder": "", "type": "temp"}


def _tensor_to_pil(t):
    """IMAGE 张量 -> PIL RGB（取 batch 第 1 张）。"""
    arr = t.cpu().numpy()
    if arr.ndim == 4:
        arr = arr[0]
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode="RGB")


class FCLoadImage:
    SEARCH_ALIASES = ["读取图片", "加载图片", "文件夹图片", "顺序读图", "批量读图"]
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder_path": ("STRING", {"multiline": False, "default": ""}),
            },
            "optional": {
                "reset": ("BOOLEAN", {"default": False}),
                "start_index": ("INT", {"default": -1, "min": -1, "max": 1000000, "step": 1}),
                "sort_by": (["name", "time"],),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK", "STRING", "INT")
    RETURN_NAMES = ("image", "mask", "filename", "index")
    FUNCTION = "load_next"
    CATEGORY = "image/io"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        global _EXEC_COUNTER
        _EXEC_COUNTER += 1
        return _EXEC_COUNTER

    def load_next(self, folder_path, reset=False, start_index=-1, sort_by="name"):
        global _EXEC_COUNTER
        folder = _normalize_path(folder_path)
        files = _list_images(folder, sort_by)

        if not files:
            img = torch.zeros((1, 64, 64, 3), dtype=torch.float32)
            mask = torch.zeros((1, 64, 64), dtype=torch.float32)
            return {"ui": {"images": []}, "result": (img, mask, "NO_IMAGE_FOUND", -1)}

        state = _load_state()
        key = f"{folder}|{sort_by}"

        # 定位：start_index >= 0 直接跳到该张；否则 reset 从第 1 张；否则沿用进度
        if start_index is not None and start_index >= 0:
            idx = start_index % len(files)
        elif reset:
            idx = 0
        else:
            idx = state.get(key, 0)
        idx = idx % len(files)

        fname = files[idx]
        path = os.path.join(folder, fname)

        i = Image.open(path)
        i = ImageOps.exif_transpose(i)
        has_alpha = i.mode == "RGBA"

        img = i.convert("RGB")
        image = np.array(img).astype(np.float32) / 255.0
        image = torch.from_numpy(image)[None,]

        if has_alpha:
            alpha = np.array(i.split()[-1]).astype(np.float32) / 255.0
            mask = 1.0 - torch.from_numpy(alpha)
        else:
            mask = torch.zeros((image.shape[1], image.shape[2]), dtype=torch.float32)
        mask = mask.unsqueeze(0)

        # 指针前进并持久化
        state[key] = (idx + 1) % len(files)
        _save_state(state)

        label = f"[{idx + 1}/{len(files)}] {fname}"
        preview = _temp_preview(_draw_label(img, label), "fc_load_preview")

        return {"ui": {"images": [preview]}, "result": (image, mask, fname, idx)}


class FCSaveImage:
    SEARCH_ALIASES = ["保存图片", "图片保存", "导出图片"]
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
            },
            "optional": {
                "output_path": ("STRING", {"multiline": False, "default": ""}),
                "filename_prefix": ("STRING", {"default": "ComfyUI"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_path",)
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "image/io"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        global _EXEC_COUNTER
        _EXEC_COUNTER += 1
        return _EXEC_COUNTER

    def save(self, images, output_path="", filename_prefix="ComfyUI"):
        out_dir = _normalize_path(output_path)
        if not out_dir:
            out_dir = folder_paths.get_output_directory()
        os.makedirs(out_dir, exist_ok=True)

        saved = []
        previews = []
        for n, image in enumerate(images):
            i = 255.0 * image.cpu().numpy()
            pil = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

            (
                full_output_folder,
                filename,
                counter,
                subfolder,
                _,
            ) = folder_paths.get_save_image_path(filename_prefix, out_dir)
            file = f"{filename}_{counter:05d}.png"
            full_path = os.path.join(full_output_folder, file)
            pil.save(full_path)
            saved.append(full_path)

            preview = _temp_preview(
                _draw_label(pil, f"已保存: {full_path}"),
                f"fc_save_preview_{n}",
            )
            previews.append(preview)

        return {"ui": {"images": previews}, "result": ("\n".join(saved),)}


class FCCompareImages:
    SEARCH_ALIASES = ["图片对比", "图像对比", "滑动对比", "对比图"]
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_a": ("IMAGE",),
            },
            "optional": {
                "image_b": ("IMAGE",),
                "label_a": ("STRING", {"default": "输入"}),
                "label_b": ("STRING", {"default": "输出"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("image_a", "image_b")
    FUNCTION = "compare"
    OUTPUT_NODE = True
    CATEGORY = "image/io"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        global _EXEC_COUNTER
        _EXEC_COUNTER += 1
        return _EXEC_COUNTER

    def compare(self, image_a, image_b=None, label_a="输入", label_b="输出"):
        # 前端 JS 扩展（web/compare.js）读取 fc_a / fc_b 渲染可拖动分割线的对比滑块
        ui = {
            "fc_labels": [label_a, label_b],
            "fc_a": [_temp_preview(_tensor_to_pil(image_a), "fc_compare_a")],
        }
        if image_b is not None:
            ui["fc_b"] = [_temp_preview(_tensor_to_pil(image_b), "fc_compare_b")]
        return {"ui": ui, "result": (image_a, image_b if image_b is not None else image_a)}

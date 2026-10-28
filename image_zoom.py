"""Image resizing and native tiled super resolution."""

import math
import os

import torch
import comfy.utils
import folder_paths


_BUNDLED_MODELS = os.path.join(os.path.dirname(__file__), "models", "upscale_models")
folder_paths.add_model_folder_path("upscale_models", _BUNDLED_MODELS)


class FCImageZoom:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE",),
            "mode": (["按比例缩放", "模型放大"],),
            "scale_by": ("FLOAT", {"default": 2.0, "min": 0.01, "max": 8.0, "step": 0.01,
                "tooltip": "最终尺寸相对于原图的倍率；两种模式均生效，0.5 为缩小一半。"}),
            "upscale_model": (["None"] + folder_paths.get_filename_list("upscale_models"), {
                "default": "realesr-general-x4v3.pth",
                "tooltip": "仅模型放大模式使用。可使用内置模型，或 models/upscale_models 下的其他模型。"}),
            "interpolation": (["lanczos", "bicubic", "bilinear", "area", "nearest-exact"], {
                "tooltip": "比例缩放的插值方式，也用于模型放大后调整到目标倍率。"}),
        }}

    RETURN_TYPES = ("IMAGE", "INT", "INT")
    RETURN_NAMES = ("image", "width", "height")
    FUNCTION = "zoom"
    CATEGORY = "FC/图像"
    SEARCH_ALIASES = ["图片放大", "图像放大", "图片缩放", "比例缩放", "模型放大", "超分", "缩小", "FC_image_Zoom"]
    DESCRIPTION = "按比例缩放，或使用超分模型分块放大，再调整到指定倍率。支持批量图片及透明通道。"

    def __init__(self):
        self._model_key = None
        self._model = None

    @classmethod
    def IS_CHANGED(cls, mode, upscale_model="None", **kwargs):
        if mode != "模型放大" or upscale_model == "None":
            return None
        path = folder_paths.get_full_path_or_raise("upscale_models", upscale_model)
        stat = os.stat(path)
        return (path, stat.st_mtime_ns, stat.st_size)

    def zoom(self, image, mode, scale_by, upscale_model="None", interpolation="lanczos"):
        if not math.isfinite(scale_by) or not 0.01 <= scale_by <= 8:
            raise ValueError("FC_image_Zoom：倍率必须在 0.01 到 8 之间。")
        width = max(1, round(image.shape[2] * scale_by))
        height = max(1, round(image.shape[1] * scale_by))
        result = image
        if mode == "模型放大":
            if upscale_model == "None":
                raise ValueError("FC_image_Zoom：请选择放大模型，或切换到按比例缩放。")
            # Keep ordinary resizing usable even if the optional model backend is unavailable.
            from comfy_extras.nodes_upscale_model import UpscaleModelLoader, ImageUpscaleWithModel

            path = folder_paths.get_full_path_or_raise("upscale_models", upscale_model)
            stat = os.stat(path)
            key = (path, stat.st_mtime_ns, stat.st_size)
            if key != self._model_key:
                self._model = None
                self._model_key = None
                self._model = UpscaleModelLoader().load_model(upscale_model)[0]
                self._model_key = key
            rgb = image[..., :3]
            result = ImageUpscaleWithModel().upscale(self._model, rgb)[0]
        elif mode != "按比例缩放":
            raise ValueError("FC_image_Zoom：未知缩放模式。")

        if result.shape[1:3] != (height, width):
            result = comfy.utils.common_upscale(
                result.movedim(-1, 1), width, height, interpolation, "disabled").movedim(1, -1)
        if mode == "模型放大" and image.shape[-1] == 4:
            alpha = comfy.utils.common_upscale(
                image[..., 3:].movedim(-1, 1), width, height, "bilinear", "disabled").movedim(1, -1)
            result = torch.cat((result, alpha.to(device=result.device, dtype=result.dtype)), dim=-1)
        return (result, width, height)

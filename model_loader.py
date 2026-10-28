"""Native diffusion model, text encoder and optional LoRAs in one node."""

import os
import json
import math

import folder_paths
from nodes import CLIPLoader, LoraLoader, UNETLoader


def _file_key(category, name):
    path = folder_paths.get_full_path_or_raise(category, name)
    stat = os.stat(path)
    return (path, stat.st_mtime_ns, stat.st_size)


def _active_loras(raw, name, sm, sc, enabled):
    if not enabled:
        return []
    rows = json.loads(raw) if raw.strip() else [
        {"name": name, "strength_model": sm, "strength_clip": sc, "enabled": True}]
    if not isinstance(rows, list) or len(rows) > 64:
        raise ValueError("FC Load model: LoRA 列表必须为数组，最多 64 项。")
    active = []
    for row in rows:
        if not row.get("enabled", True) or row.get("name", "None") == "None":
            continue
        sm, sc = float(row.get("strength_model", 1)), float(row.get("strength_clip", 1))
        if not all(math.isfinite(v) and -100 <= v <= 100 for v in (sm, sc)):
            raise ValueError("FC Load model: LoRA 强度必须在 -100 到 100 之间。")
        if sm or sc:
            active.append((row["name"], sm, sc))
    return active


class FCLoadModel:
    @classmethod
    def INPUT_TYPES(cls):
        clip_types = CLIPLoader.INPUT_TYPES()["required"]["type"][0]
        return {
            "required": {
                "model_name": (folder_paths.get_filename_list("diffusion_models"),),
                "clip_name": (folder_paths.get_filename_list("text_encoders"), {
                    "tooltip": "选择与扩散模型和 CLIP 类型匹配的文本编码器。"}),
                "lora_name": (["None"] + folder_paths.get_filename_list("loras"),),
                "strength_model": ("FLOAT", {"default": 1.0, "min": -100.0,
                    "max": 100.0, "step": 0.01}),
                "strength_clip": ("FLOAT", {"default": 1.0, "min": -100.0,
                    "max": 100.0, "step": 0.01,
                    "tooltip": "仅影响包含文本编码器权重的 LoRA。"}),
            },
            "optional": {
                "lora_enabled": ("BOOLEAN", {"default": True}),
                "weight_dtype": (["default", "fp8_e4m3fn", "fp8_e4m3fn_fast", "fp8_e5m2"], {
                    "default": "default", "advanced": True,
                    "tooltip": "建议 default，沿用模型自身精度和 ComfyUI 显存管理。"}),
                "clip_device": (["default", "cpu"], {"default": "default", "advanced": True,
                    "tooltip": "cpu 可减少文本编码器的显存占用，但编码更慢。"}),
                "lora_stack": ("STRING", {"default": "", "multiline": False}),
                "clip_type": (clip_types, {
                    "default": "krea2" if "krea2" in clip_types else clip_types[0],
                    "tooltip": "与原生 CLIP 加载器类型列表同步；请按所用模型选择。"}),
            },
        }

    RETURN_TYPES = ("MODEL", "CLIP")
    RETURN_NAMES = ("model", "clip")
    FUNCTION = "load"
    CATEGORY = "FC/loaders"
    DESCRIPTION = "一次加载扩散模型、文本编码器和多 LoRA；CLIP 类型与当前 ComfyUI 同步。输出 MODEL / CLIP，VAE 单独加载。仅支持原生单 CLIP 加载方式。"
    SEARCH_ALIASES = ["Krea2", "FC Load model", "LoRA", "模型加载", "加载模型", "多LoRA", "模型与LoRA"]

    def __init__(self):
        self._model_key = None
        self._clip_key = None
        self._model = None
        self._clip = None
        self._lora_cache = {}

    @classmethod
    def IS_CHANGED(cls, model_name, clip_name, lora_name, strength_model=1.0,
                   strength_clip=1.0, lora_enabled=True, lora_stack="", **kwargs):
        keys = [_file_key("diffusion_models", model_name),
                _file_key("text_encoders", clip_name)]
        for name, sm, sc in _active_loras(lora_stack, lora_name, strength_model, strength_clip, lora_enabled):
            keys.append(_file_key("loras", name))
        return tuple(keys)

    def load(self, model_name, clip_name, lora_name="None", strength_model=1.0,
             strength_clip=1.0, lora_enabled=True, weight_dtype="default",
             clip_device="default", lora_stack="", clip_type="krea2"):
        if clip_type not in CLIPLoader.INPUT_TYPES()["required"]["type"][0]:
            raise RuntimeError(f"FC Load model: 当前 ComfyUI 不支持 CLIP 类型 {clip_type}，请更新 ComfyUI 或选择已有类型。")

        # Validate selected files before allocating model memory.
        model_key = (_file_key("diffusion_models", model_name), weight_dtype)
        clip_key = (_file_key("text_encoders", clip_name), clip_device, clip_type)
        stack = _active_loras(lora_stack, lora_name, strength_model, strength_clip, lora_enabled)
        lora_keys = {name: _file_key("loras", name) for name, _, _ in stack}

        if model_key != self._model_key:
            self._model = None
            self._model_key = None
            self._model = UNETLoader().load_unet(model_name, weight_dtype)[0]
            self._model_key = model_key
        if clip_key != self._clip_key:
            self._clip = None
            self._clip_key = None
            self._clip = CLIPLoader().load_clip(clip_name, type=clip_type, device=clip_device)[0]
            self._clip_key = clip_key

        self._lora_cache = {name: entry for name, entry in self._lora_cache.items()
                            if name in lora_keys and entry[0] == lora_keys[name]}
        model, clip = self._model, self._clip
        for name, sm, sc in stack:
            if name not in self._lora_cache:
                self._lora_cache[name] = (lora_keys[name], LoraLoader())
            model, clip = self._lora_cache[name][1].load_lora(model, clip, name, sm, sc)
        return (model, clip)

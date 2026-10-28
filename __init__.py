from .nodes import FCLoadImage, FCSaveImage, FCCompareImages
from .model_loader import FCLoadModel
from .image_zoom import FCImageZoom

NODE_CLASS_MAPPINGS = {
    "FC_image_Zoom": FCImageZoom,
    "FCLoadModel": FCLoadModel,
    "FCLoadImage": FCLoadImage,
    "FCSaveImage": FCSaveImage,
    "FCCompareImages": FCCompareImages,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FC_image_Zoom": "FC_image_Zoom 图片缩放·模型放大",
    "FCLoadModel": "FC Load model 模型加载·多LoRA",
    "FCLoadImage": "FC Load Image 文件夹读取图片",
    "FCSaveImage": "FC Save Image 保存图片",
    "FCCompareImages": "FC Image Compare 图片对比",
}

# 前端扩展目录：ComfyUI 会自动加载 web/ 下的 JS（拖动对比滑块）
WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

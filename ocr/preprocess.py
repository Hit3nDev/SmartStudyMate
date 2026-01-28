import io
from typing import Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps


def _pil_to_cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def _cv_to_pil(img: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def deskew(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    coords = np.column_stack(np.where(gray > 0))
    if coords.size == 0:
        return image
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def preprocess_image(img_bytes: bytes) -> Tuple[Image.Image, bytes]:
    """Denoise, deskew, binarize, and contrast-normalize the image."""
    pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    pil_img = ImageOps.exif_transpose(pil_img)

    cv_img = _pil_to_cv(pil_img)
    cv_img = cv2.bilateralFilter(cv_img, 5, 75, 75)
    cv_img = deskew(cv_img)

    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
    bw = cv2.medianBlur(bw, 3)

    processed = cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)
    pil_out = _cv_to_pil(processed)
    buf = io.BytesIO()
    pil_out.save(buf, format="PNG")
    return pil_out, buf.getvalue()


def detect_handwritten(pil_img: Image.Image) -> bool:
    """Lightweight heuristic: measure edge complexity to guess handwriting."""
    cv_img = _pil_to_cv(pil_img)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    density = edges.mean()
    # Higher edge density often correlates with handwriting strokes
    return density > 20


from typing import Dict, Any, Optional

from ocr.preprocess import preprocess_image, detect_handwritten
from ocr.tesseract_adapter import run_tesseract
from ocr.easyocr_adapter import run_easyocr
from ocr.postprocess import clean_text


def ocr_image(img_bytes: bytes, mode: str = "auto", engine_preference: Optional[str] = None, enable_spellcheck: bool = False) -> Dict[str, Any]:
    """Privacy-first OCR pipeline with preprocessing and engine selection."""
    pil_processed, processed_bytes = preprocess_image(img_bytes)

    use_handwritten = False
    if mode == "handwritten":
        use_handwritten = True
    elif mode == "printed":
        use_handwritten = False
    else:
        use_handwritten = detect_handwritten(pil_processed)

    chosen_engine = engine_preference or ("easyocr" if use_handwritten else "tesseract")
    result: Dict[str, Any] = {"text": "", "segments": [], "confidences": [], "engine": chosen_engine, "processed_image": processed_bytes}

    try:
        if chosen_engine == "easyocr":
            result.update(run_easyocr(pil_processed))
        else:
            result.update(run_tesseract(pil_processed))
    except ImportError as e:
        result["text"] = ""
        result["error"] = str(e)
    except Exception as e:
        result["text"] = ""
        result["error"] = f"OCR failed: {e}"

    cleaned = clean_text(result.get("text", ""), enable_spellcheck=enable_spellcheck)
    result["text"] = cleaned.get("text", result.get("text", ""))
    return result


from typing import Dict, Any, Optional

try:
    import easyocr
except ImportError:
    easyocr = None


def run_easyocr(pil_img, lang_list=None) -> Dict[str, Any]:
    if easyocr is None:
        raise ImportError("easyocr is not installed")
    if lang_list is None:
        lang_list = ["en"]
    reader = easyocr.Reader(lang_list, gpu=False)
    results = reader.readtext(pil_img, detail=1, paragraph=False)

    texts = []
    confs = []
    for _, text, conf in results:
        texts.append(text)
        confs.append(conf)
    joined = "\n".join(texts)
    avg_conf = sum(confs) / max(1, len(confs))
    return {
        "text": joined,
        "segments": texts,
        "confidences": confs,
        "engine": "easyocr",
        "avg_confidence": avg_conf,
    }


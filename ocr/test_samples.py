import argparse
import json
from pathlib import Path

from ocr.engine import ocr_image


def main():
    parser = argparse.ArgumentParser(description="Run OCR pipeline on sample images")
    parser.add_argument("--input", required=True, help="Path to image file")
    parser.add_argument("--mode", default="auto", choices=["auto", "printed", "handwritten"])
    parser.add_argument("--engine", default=None, choices=["tesseract", "easyocr", None])
    args = parser.parse_args()

    img_path = Path(args.input)
    if not img_path.exists():
        print(json.dumps({"error": "file not found", "path": str(img_path)}))
        return

    with open(img_path, "rb") as f:
        img_bytes = f.read()

    result = ocr_image(img_bytes, mode=args.mode, engine_preference=args.engine)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()


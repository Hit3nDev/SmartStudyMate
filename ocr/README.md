# Privacy-First OCR Pipeline

This module provides a robust, local-first OCR pipeline for SmartStudyMate.

## Features
- **Preprocessing**: Automatic noise removal, deskewing, and adaptive thresholding.
- **Hybrid Engine**: 
  - Uses **Tesseract** for high-accuracy printed text extraction.
  - Uses **EasyOCR** (optional) for handwritten text and complex layouts.
- **Privacy**: All processing happens locally on the CPU/GPU. No images are sent to external APIs unless explicitly configured.

## Setup
1. **Dependencies**:
   - `tesseract-ocr` must be installed on the system (e.g., `apt install tesseract-ocr` or Windows installer).
   - Python packages: `pytesseract`, `opencv-python-headless`, `numpy`, `pillow`.
   - Optional: `easyocr`, `torch`.

2. **Configuration**:
   - The pipeline automatically detects if `easyocr` is available.
   - Use `ocr_image(mode='handwritten')` to prefer EasyOCR.

## Usage
```python
from ocr.engine import ocr_image

# Basic usage (auto-detects mode)
result = ocr_image(image_bytes)
print(result['text'])

# Force handwritten mode
result = ocr_image(image_bytes, mode='handwritten')
```

## Privacy Policy
- **Local Processing**: Default behavior. No data leaves the machine.
- **Cloud Opt-in**: Future support for cloud APIs requires explicit user consent and API keys.

# UI & System Overhaul Changelog

## New Files
- `assets/ui_theme.css`: Centralized CSS for themes, spacing, cards, and pills.
- `ui/components.py`: Reusable UI wrappers (`hero_card`, `ui_card`, `focus_widget`, `status_pill`).
- `pages/focus.py`: Dedicated page for Focus Mode settings and calibration.
- `pages/upload_ocr.py`: Refactored Upload & OCR page with privacy-first pipeline.
- `pages/learning_tracker.py`: Refactored Learning Tracker page with UI fixes.
- `pages/analytics.py`: Refactored Analytics page.
- `ocr/preprocess.py`: Image preprocessing functions (denoise, deskew, grayscale).
- `ocr/engine.py`: Main OCR engine with routing logic (Tesseract vs EasyOCR).
- `ocr/postprocess.py`: Text cleanup and spellchecking.
- `ocr/tesseract_adapter.py`: Adapter for Tesseract OCR.
- `ocr/easyocr_adapter.py`: Adapter for EasyOCR.
- `utils/text.py`: Utility for stripping emojis.

## UI/UX Improvements
- **Hero Section**: Centered layout with max-width 1200px, removed offsetting containers, fixed background blur.
- **Focus UI**: 
  - Integrated `focus_widget` into header and pages.
  - Restyled `components/focus_detector.html` to match the new theme (pills, colors).
  - Added "Focus Mode" page for detailed settings.
- **Consistency**:
  - Removed all emojis from UI text.
  - Added global `app-container` and `page-content` wrappers for consistent scrolling and spacing.
  - Fixed "Disabled" pill alignment.
- **Cleanup**:
  - Removed stray timeline artifacts from Learning Tracker.
  - Fixed unmatched HTML tags and visible `</div>` text.
  - Removed hardcoded heights to prevent content clipping.

## OCR Pipeline (Privacy-First)
- **Architecture**:
  - Local-first processing (Tesseract/EasyOCR).
  - Cloud opt-in (structure ready, defaulted to off).
- **Features**:
  - Image preprocessing (adaptive thresholding, noise removal).
  - Smart routing: Tesseract for printed text, EasyOCR for handwritten (fallback).
  - Confidence scoring and editable text output.
  - "Focus during upload" metadata tagging.
- **Privacy**:
  - No raw images uploaded to external servers by default.
  - Explicit user opt-in required for cloud features.

## Dependency Updates
- Added `watchdog` for Streamlit.
- Added comments for CPU-only `torch` installation.
- Made `easyocr` optional (graceful fallback).

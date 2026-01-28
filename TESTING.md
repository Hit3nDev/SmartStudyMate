# Testing Checklist & Guide

## Verification Checklist

### UI & Layout
- [ ] **Hero Alignment**: Header is centered, max-width 1200px, consistent on desktop/tablet.
- [ ] **Spacing**: No content clipping at the bottom of pages. Global scroll works.
- [ ] **Artifacts**: No stray timeline charts or "None" text in Learning Tracker.
- [ ] **HTML**: No visible `</div>` tags or raw HTML injection errors.
- [ ] **Pills**: "Disabled" and status pills are correctly aligned and styled (no emojis).
- [ ] **Emojis**: All UI text is stripped of emojis.

### Focus Integration
- [ ] **Widget**: Focus widget appears in Hero and Page Headers.
- [ ] **Page**: `pages/focus.py` loads correctly with settings and camera preview.
- [ ] **Component**: Camera preview works (if enabled) and status updates (Focused/Away).
- [ ] **Styles**: Component pills match the new theme (green/amber/red dots).

### OCR Pipeline
- [ ] **Printed Text**: Uploading a clean PDF/Image extracts text using Tesseract.
- [ ] **Handwritten**: Uploading a handwritten note uses EasyOCR (if installed) or falls back gracefully.
- [ ] **Privacy**: "Processing image — runs locally" message appears.
- [ ] **Editable**: Extracted text is shown in an editable text area.
- [ ] **Confidence**: Confidence score is displayed.

## Local Test Guide

1. **Setup Environment**:
   ```bash
   pip install -r requirements.txt
   # Ensure Tesseract is installed on your OS
   ```

2. **Run Application**:
   ```bash
   streamlit run main.py
   ```

3. **Verify OCR**:
   - Go to "Upload & OCR" page.
   - Upload `test_image.png` (or any text image).
   - Check if text is extracted and editable.
   - Toggle "Handwritten" mode and verify behavior.

4. **Verify Focus**:
   - Go to "Focus Mode" page.
   - Enable "Focus Tracking".
   - Enable "Show Preview".
   - Verify camera starts and face mesh is drawn.
   - Look away and verify status changes to "Away".

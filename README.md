## Focus / Attention Detection

SmartStudyMate now ships with an on-device focus detector that uses MediaPipe Face Mesh in the browser. No images or video frames ever leave the browser; only numeric scores and states are shared with Streamlit.

### How it works
- The client runs MediaPipe Face Mesh to estimate a focus score (0–1) using: face present (+0.3), eyes open (+0.4), head facing camera (+0.3).
- Scores are smoothed and mapped to states: `focused` (>=0.75), `partial` (>=0.45), `not_focused` (<0.45), `away` (no face >5s).
- Updates are sent every 0.5–3s (configurable) via `Streamlit.setComponentValue`—only numbers/timestamps.

### Configure in the UI
- Toggle **Enable Focus Tracking** to start/stop webcam use (permission requested only when enabled).
- Optional camera preview toggle.
- Sensitivity: low/medium/high (adjusts thresholds).
- Sampling interval (ms), auto-pause timers, and history retention window.
- Privacy notice is shown inline: processing stays in-browser; only scores/timestamps stored.

### Integrations
- **Learning Tracker:** timers auto-pause when not focused/away (if enabled). Session summaries store focus % and events (numeric only) in `data/focus_sessions.json`.
- **Upload & OCR:** each upload is tagged with focus metadata and shows a “Focus during upload” label; optional quality warning if attention was low.
- **Analytics:** new focus timeline, distribution, heatmap, and per-topic focus summaries with CSV export.

### Testing / QA script
1. Toggle **Enable Focus Tracking** on; accept camera permission; confirm header pill updates as you move/look away.
2. Start a learning timer, then look away—timer shows “Paused — you’re away”; look back to resume; stop and confirm focus summary appears.
3. Upload a file while looking at the camera; note “Focus during upload” label; repeat while looking away to trigger low-focus warning.
4. Visit Analytics → Focus Analytics to see timeline/distribution and export CSV.
5. Turn tracking off and confirm webcam stops and the indicator shows “Disabled”.


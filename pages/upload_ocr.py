import os
import sys
import time
import streamlit as st

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import add_topic
from focus.integrations import tag_ocr_session_with_focus
from ui.components import (
    ui_section_heading,
    focus_summary_card,
    hero_card
)
from utils.text import strip_emojis
from summarizer import extract_keywords, get_related_resources, summarize_text

# Import new OCR pipeline
from ocr.engine import ocr_image
from ocr.postprocess import clean_text

st.set_page_config(page_title="Upload & OCR", page_icon="📄", layout="wide")

# Load Theme
def load_custom_css():
    css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "ui_theme.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_custom_css()

def rerun_app():
    st.rerun()

# Section Header
with hero_card():
    st.markdown(
        f"""
        <h1 class="hero-title">{strip_emojis("Upload & OCR Recognition")}</h1>
        <p class="hero-tagline">{strip_emojis("Extract & summarize")}</p>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div style="margin-top: 24px; display:flex; justify-content:center;">', unsafe_allow_html=True)
    from ui.components import focus_widget
    focus_widget(
        st.session_state.get("focus_state", "disabled"),
        st.session_state.get("focus_score", 0.0),
    )
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="app-container">', unsafe_allow_html=True)
st.markdown('<div class="page-content">', unsafe_allow_html=True)

# Info Banner
st.markdown(
    f"""
    <div class="info-banner">
        <div class="info-banner-icon"></div>
        <p class="info-banner-text">
            <strong>{strip_emojis("Tip:")}</strong> {strip_emojis("Upload handwritten notes, whiteboard photos, or PDFs. Our advanced privacy-first OCR runs locally to extract text and AI will summarize it for you!")}
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

# Upload Section
st.markdown("### Upload File")

col_upload1, col_upload2 = st.columns([2, 1])

with col_upload1:
    uploaded_file = st.file_uploader(
        "Upload your file",
        type=["jpg", "jpeg", "png", "pdf"],
        key="upload_file",
        help="Supported formats: JPG, PNG, PDF"
    )

with col_upload2:
    st.markdown("<br>", unsafe_allow_html=True)
    
    ocr_mode = st.radio(
        "Text Type",
        ["Auto", "Printed", "Handwritten"],
        index=0,
        horizontal=True,
        help="Help the engine choose the best model."
    )
    
    engine_pref = st.selectbox(
        "Engine Preference",
        ["Auto", "Tesseract (Printed)", "EasyOCR (Handwritten/Complex)"],
        index=0,
        help="Force a specific OCR engine."
    )
    
    focus_quality_check = st.checkbox(
        "Apply focus-based quality check",
        value=True,
        help="Warns if attention was low while uploading/processing.",
    )
    
    # Show preview if image
    if uploaded_file and uploaded_file.type.startswith('image'):
        st.image(uploaded_file, caption="Preview", use_container_width=True)

if uploaded_file:
    # Validate file size (max 50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    file_size = len(uploaded_file.getbuffer())
    if file_size > MAX_FILE_SIZE:
        st.error(f"File too large! Maximum size is 50MB. Your file is {file_size / (1024*1024):.1f}MB")
        st.stop()
    
    os.makedirs("data", exist_ok=True)
    file_path = os.path.join("data", uploaded_file.name)
    st.session_state.setdefault("upload_focus_start", time.time())
    
    # Read file bytes for OCR
    file_bytes = uploaded_file.getvalue()
    
    try:
        with open(file_path, "wb") as f:
            f.write(file_bytes)
    except Exception as e:
        st.error(f"Error saving file: {e}")
        st.stop()

    if st.button("Extract and Process", key="process_file", type="primary", use_container_width=True):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.info("Processing image — runs locally. No images uploaded.")
        progress_bar.progress(20)
        
        # Determine parameters
        mode_map = {"Auto": "auto", "Printed": "printed", "Handwritten": "handwritten"}
        engine_map = {"Auto": None, "Tesseract (Printed)": "tesseract", "EasyOCR (Handwritten/Complex)": "easyocr"}
        
        selected_mode = mode_map.get(ocr_mode, "auto")
        selected_engine = engine_map.get(engine_pref)
        
        try:
            # Run OCR Pipeline
            ocr_result = ocr_image(
                file_bytes, 
                mode=selected_mode, 
                engine_preference=selected_engine,
                enable_spellcheck=True
            )
            
            extracted_text = ocr_result.get("text", "")
            confidence = ocr_result.get("avg_confidence", 0)
            used_engine = ocr_result.get("engine", "unknown")
            error = ocr_result.get("error")
            
            progress_bar.progress(60)
            
            if error:
                st.error(f"OCR Error: {error}")
            
        except Exception as e:
            st.error(f"Error processing file: {e}")
            extracted_text = ""
            confidence = None
            used_engine = "error"
            progress_bar.progress(0)
            st.exception(e)

        progress_bar.progress(100)
        
        if extracted_text.strip():
            status_text.success("Text successfully extracted!")
        else:
            status_text.warning("No text detected or extraction failed.")

        focus_meta = tag_ocr_session_with_focus(
            st.session_state.get("focus_state", "disabled"),
            st.session_state.get("focus_score", 0.0),
            st.session_state.get("focus_history", []),
            session_start_time=st.session_state.get("upload_focus_start"),
        )
        
        st.info(f"Focus during upload: {focus_meta.get('focus_during_upload', 'N/A')}")
        if focus_quality_check and focus_meta.get("avg_focus_score", 0.0) < 0.45:
            st.warning("Low focus detected during upload. Consider re-scanning for best results.")
        
        # Show confidence & engine
        col_meta1, col_meta2 = st.columns(2)
        with col_meta1:
            if confidence is not None:
                # Confidence is often 0-100 or 0-1
                if confidence <= 1.0: confidence *= 100
                confidence_label = "High" if confidence > 70 else "Medium" if confidence > 40 else "Low"
                st.info(f"Confidence: {confidence:.1f}% ({confidence_label})")
        with col_meta2:
            st.info(f"Engine Used: {used_engine}")
        
        st.markdown("---")
        
        # Extracted Text (Editable)
        st.markdown("### Extracted Text")
        final_text = st.text_area("Detected text (Editable)", extracted_text, height=300)
        
        st.markdown("---")
        
        # AI Summary
        st.markdown("### AI Summary")
        if st.button("Generate Summary", key="gen_summary"):
            with st.spinner("Generating summary with AI..."):
                try:
                    summary = summarize_text(final_text)
                    st.success("Summary generated!")
                    st.info(summary)
                except Exception as e:
                    st.error(f"Summary failed: {e}")

            # Keywords
            st.markdown("### Key Concepts Detected")
            with st.spinner("Extracting keywords..."):
                try:
                    keywords = extract_keywords(final_text, num_keywords=8)
                    if keywords:
                        # Display as badges
                        keyword_badges = " ".join([f"`{strip_emojis(kw)}`" for kw in keywords])
                        st.markdown(keyword_badges)
                        
                        # Study Resource Recommendations
                        st.markdown("### Recommended Study Resources")
                        with st.spinner("Finding learning resources..."):
                            try:
                                resources = get_related_resources(keywords)
                                for topic, links in resources.items():
                                    st.markdown(f"**{topic.capitalize()}**")
                                    st.markdown(links, unsafe_allow_html=True)
                                    st.markdown("")
                            except Exception as e:
                                st.error(f"Could not fetch resources: {e}")

                    else:
                        st.info("No clear keywords detected.")
                except Exception as e:
                    st.error(f"Keyword extraction failed: {e}")

        # Add to Tracker
        st.markdown("---")
        st.markdown("### Save to Tracker")
        col_track1, col_track2 = st.columns([2, 1])
        with col_track1:
            tracker_topic = st.text_input("Enter topic name:", key="tracker_topic_input", placeholder="e.g., Machine Learning Basics")
        with col_track2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Save to Tracker", key="save_tracker_button", type="primary", use_container_width=True):
                cleaned_topic = strip_emojis(tracker_topic).strip()
                if cleaned_topic:
                    add_topic(cleaned_topic, notes=strip_emojis(final_text))
                    st.success(f"'{cleaned_topic}' added to tracker!")
                else:
                    st.warning("Please enter a topic name.")

# End page content
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

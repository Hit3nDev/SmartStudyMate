import os
import sys
import streamlit as st

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from database import init_db
from focus.focus_wrapper import (
    ensure_focus_session_state,
    get_focus_status_indicator,
    render_focus_detector,
    update_focus_state,
)
from ui.components import (
    hero_card,
    status_pill,
    focus_widget
)

# --------------------------------------------
# Initialize
# --------------------------------------------
st.set_page_config(
    page_title="SmartStudyMate",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)
init_db()

# --------------------------------------------
# 🎨 Load Theme
# --------------------------------------------
def load_custom_css():
    """Load the premium 3D glassmorphism CSS theme."""
    css_path = os.path.join(os.path.dirname(__file__), "assets", "ui_theme.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)

load_custom_css()

def load_focus_css():
    """Inject focus-specific styles if available."""
    css_path = os.path.join(os.path.dirname(__file__), "components", "focus_styles.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)

def init_focus_state():
    """Ensure all focus-related session state keys exist."""
    ensure_focus_session_state(st.session_state)
    focus_settings = st.session_state.get("focus_settings", {})
    st.session_state.setdefault("focus_show_preview", focus_settings.get("show_preview", False))

def render_focus_controls():
    """Render global focus controls and wire component updates into session_state."""
    init_focus_state()
    load_focus_css()

    focus_settings = st.session_state.get("focus_settings", {})
    
    # Minimal feedback on Main page if enabled
    if st.session_state.get("focus_enabled", False):
         st.caption("Focus Tracking Active")

    # Ensure settings are promoted
    if "sensitivity" not in focus_settings:
        focus_settings.update({
            "sensitivity": "medium",
            "sampling_interval": 1000,
            "auto_pause": True,
            "history_hours": 24,
            "show_preview": False
        })
        st.session_state["focus_settings"] = focus_settings

    # Render component and capture updates
    # We run this on Main so focus tracking works if enabled, 
    # but we hide the settings since they are now in pages/focus.py
    if st.session_state.get("focus_enabled", False):
        max_history = int((focus_settings["history_hours"] * 3600 * 1000) / focus_settings["sampling_interval"])
        focus_component_data = render_focus_detector(
            enabled=True,
            show_preview=st.session_state.get("focus_show_preview", False),
            settings=focus_settings,
            key="focus_detector_main",
            height=260 if st.session_state.get("focus_show_preview", False) else 0,
        )
        update_focus_state(
            focus_component_data,
            st.session_state,
            max_history=max(200, min(max_history, 5000)),
        )

# Initialize focus state early
init_focus_state()

# --------------------------------------------
# 🎛️ Sidebar Controls - 3D Glass Panel
# --------------------------------------------
with st.sidebar:
    st.markdown(
        '<div style="text-align: center; padding: 1rem 0; margin-bottom: 2rem;">'
        '<h3 style="font-family: \'Sora\', sans-serif; color: rgba(255, 255, 255, 0.95);">🎛️ Controls</h3>'
        '</div>',
        unsafe_allow_html=True
    )
    
    st.page_link("main.py", label="Home", icon="🏠")
    st.page_link("pages/learning_tracker.py", label="Learning Tracker", icon="📝")
    st.page_link("pages/upload_ocr.py", label="Upload & OCR", icon="📄")
    st.page_link("pages/analytics.py", label="Analytics", icon="📊")
    st.page_link("pages/focus.py", label="Focus Zone", icon="🧘")
    
    st.markdown("---")

    if st.button("Reset Tracker", use_container_width=True, type="secondary"):
        from database import reset_database
        reset_database()
        st.success("All topics and progress have been cleared!")
        st.rerun()
    
    st.markdown(
        '<div style="text-align: center; padding: 1rem 0;">'
        '<h3 style="font-family: \'Sora\', sans-serif; color: rgba(255, 255, 255, 0.95); font-size: 1.2rem;">About</h3>'
        '<p style="color: rgba(255, 255, 255, 0.7); font-family: \'Inter\', sans-serif; margin-top: 0.5rem;">SmartStudyMate v2.1</p>'
        '<p style="color: rgba(255, 255, 255, 0.7); font-family: \'Inter\', sans-serif;">AI-powered learning companion</p>'
        '</div>',
        unsafe_allow_html=True
    )

# --------------------------------------------
# 🎨 Premium SaaS Hero Section
# --------------------------------------------
st.markdown('<div class="app-container">', unsafe_allow_html=True)
st.markdown('<div class="page-content">', unsafe_allow_html=True)

with hero_card():
    st.markdown(
        """
        <h1 class="hero-title">SmartStudyMate</h1>
        <p class="hero-tagline">Your AI-powered learning companion</p>
        <p class="hero-subtext">Extract, summarize, and track your study notes with polished focus-aware insights.</p>
        """,
        unsafe_allow_html=True,
    )
    
    # Hero Focus Indicator
    st.markdown('<div style="margin-top: 24px; display:flex; justify-content:center;">', unsafe_allow_html=True)
    focus_widget(
        st.session_state.get("focus_state", "disabled"),
        st.session_state.get("focus_score", 0.0),
    )
    st.markdown('</div>', unsafe_allow_html=True)

# Global focus controls
# We don't render the full controls here anymore, just ensuring the state is initialized.
# The actual controls are in pages/focus.py
render_focus_controls()

st.markdown('</div>', unsafe_allow_html=True) # End page-content
st.markdown('</div>', unsafe_allow_html=True) # End app-container

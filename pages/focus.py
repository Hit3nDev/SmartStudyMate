import streamlit as st
import time
from ui.components import hero_card, ui_card, status_pill, focus_widget
from utils.text import strip_emojis
from focus.focus_wrapper import render_focus_detector, ensure_focus_session_state, update_focus_state

def render_focus_page():
    # Initialize state
    ensure_focus_session_state(st.session_state)
    
    with hero_card():
        st.markdown(
            """
            <h1 class="hero-title">Focus Mode</h1>
            <p class="hero-tagline">Optimize your attention span</p>
            <p class="hero-subtext">
                Real-time, privacy-first attention tracking using on-device computer vision.
                No video is ever recorded or uploaded.
            </p>
            """,
            unsafe_allow_html=True,
        )
        
        # Current Status
        st.markdown('<div style="margin-top: 24px; display:flex; justify-content:center;">', unsafe_allow_html=True)
        focus_widget(
            st.session_state.get("focus_state", "disabled"),
            st.session_state.get("focus_score", 0.0),
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # Main Control Area
    st.markdown('<div class="page-section">', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        with ui_card(title="Detection Controls"):
            st.markdown("### Focus Tracking")
            
            # Master Toggle
            focus_enabled = st.toggle(
                strip_emojis("Enable Focus Tracking"),
                value=st.session_state.get("focus_enabled", False),
                help=strip_emojis("Turn on to start privacy-preserving, on-device focus detection.")
            )
            st.session_state["focus_enabled"] = focus_enabled
            
            if focus_enabled:
                st.info(strip_emojis("Camera active. Processing runs locally."))
            else:
                st.markdown(strip_emojis("Tracking is disabled. Camera is off."))
                
            st.markdown("---")
            
            # Preview Toggle
            show_preview = st.checkbox(
                strip_emojis("Show camera preview"),
                value=st.session_state.get("focus_show_preview", False),
                help=strip_emojis("Useful for calibration. Turning off improves performance.")
            )
            st.session_state["focus_show_preview"] = show_preview

    with col2:
        with ui_card(title="Calibration & Settings"):
            st.markdown("### Sensitivity")
            
            current_settings = st.session_state.get("focus_settings", {})
            
            sensitivity = st.select_slider(
                strip_emojis("Detection Sensitivity"),
                options=["low", "medium", "high"],
                value=current_settings.get("sensitivity", "medium"),
                help=strip_emojis("High = stricter focus requirements. Low = more forgiving.")
            )
            
            sampling_interval = st.slider(
                strip_emojis("Sampling Interval (ms)"),
                min_value=500,
                max_value=3000,
                step=100,
                value=current_settings.get("sampling_interval", 1000),
                help=strip_emojis("Lower = more responsive but higher CPU usage.")
            )
            
            # Update settings in state
            new_settings = current_settings.copy()
            new_settings.update({
                "sensitivity": sensitivity,
                "sampling_interval": sampling_interval,
                "show_preview": show_preview
            })
            st.session_state["focus_settings"] = new_settings

    st.markdown('</div>', unsafe_allow_html=True)

    # The Component (Hidden or Visible based on settings)
    # We render it here so it's active on this page. 
    # NOTE: If we want it active globally, it should be in main.py's sidebar or footer.
    # But since the user asked for page updates, we'll put the *primary* control here.
    # If the user switches pages, the component might unmount unless it's in the sidebar.
    # For this task, we'll assume the component lives here for calibration, 
    # and maybe main.py has a hidden one or we accept it only runs on this page for now?
    # User said: "Visually integrate Focus/Attention Detection UI using shared card components."
    # And "Page updates (UI only): main.py, pages/focus.py..."
    # The original app had it global.
    # I will rely on main.py to render the *background* component if needed, 
    # but strictly speaking Streamlit components unmount if not in the tree.
    # I'll render it here for the "Focus Page" experience.
    
    if st.session_state.get("focus_enabled", False):
        st.markdown("### Live Monitor")
        # We render it with a key that might match main.py if we want persistence, 
        # but Streamlit keys are unique per run.
        focus_data = render_focus_detector(
            enabled=True,
            show_preview=st.session_state.get("focus_show_preview", False),
            settings=st.session_state.get("focus_settings", {}),
            key="focus_detector_page",
            height=300 if st.session_state.get("focus_show_preview", False) else 0
        )
        
        # Update state
        update_focus_state(focus_data, st.session_state)
        
        if st.session_state.get("focus_show_preview", False):
             st.caption(strip_emojis("Blue box = Face detected. Green dots = Landmarks."))

render_focus_page()

import os
import time
from datetime import datetime

import pandas as pd
import streamlit as st

from database import (
    init_db,
    add_topic,
    get_topics,
    update_time,
    update_status,
    delete_topic,
    reset_database,
    update_topic,
    get_topic_by_id,
    get_study_sessions,
    get_statistics,
    export_data,
)
from focus.focus_wrapper import (
    ensure_focus_session_state,
    get_focus_status_indicator,
    render_focus_detector,
    update_focus_state,
)
from focus.integrations import (
    compute_focus_distribution,
    compute_topic_focus_summary,
    get_timer_elapsed_with_pauses,
    load_focus_sessions,
    pause_timer_if_not_focused,
    save_focus_session,
    tag_ocr_session_with_focus,
)
from ui.components import (
    ui_glass_card,
    ui_section_heading,
    focus_summary_card,
)
from summarizer import extract_keywords, get_related_resources, summarize_text
from tracker import generate_report
from whiteboard_reader import extract_text

# --------------------------------------------
# Initialize
# --------------------------------------------
st.set_page_config(
    page_title="SmartStudyMate",
    page_icon="",  # Removed emoji icon
    layout="wide",
    initial_sidebar_state="expanded"
)
init_db()

# --------------------------------------------
# 🎨 Premium 3D UI Theme - Load Custom CSS
# --------------------------------------------
def load_custom_css():
    """Load the premium 3D glassmorphism CSS theme."""
    css_path = os.path.join(os.path.dirname(__file__), "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    else:
        # Fallback inline CSS if file doesn't exist
        st.markdown("""
            <style>
            .main {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
                background-attachment: fixed;
            }
            </style>
        """, unsafe_allow_html=True)

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
    # Promote settings into top-level helpers for convenience
    focus_settings = st.session_state.get("focus_settings", {})
    st.session_state.setdefault("focus_show_preview", focus_settings.get("show_preview", False))


def render_focus_controls():
    """Render global focus controls and wire component updates into session_state."""
    init_focus_state()
    load_focus_css()

    focus_settings = st.session_state.get("focus_settings", {})

    st.markdown("### Focus & Attention Detection")
    with st.container():
        col_toggle, col_preview, col_indicator = st.columns([1, 1, 2])

        with col_toggle:
            st.session_state["focus_enabled"] = st.toggle(
                "Enable Focus Tracking",
                value=st.session_state.get("focus_enabled", False),
                help="Turn on to start privacy-preserving, on-device focus detection.",
            )
        with col_preview:
            st.session_state["focus_show_preview"] = st.checkbox(
                "Show camera preview",
                value=st.session_state.get("focus_show_preview", False),
                help="Optional preview. Turning off keeps detection running without displaying video.",
            )
        with col_indicator:
            st.markdown(
                get_focus_status_indicator(
                    st.session_state.get("focus_state", "disabled"),
                    st.session_state.get("focus_score", 0.0),
                ),
                unsafe_allow_html=True,
            )

    st.caption(
        "Focus Detection runs entirely in your browser. No video or images are uploaded or stored. "
        "The app only stores numeric focus scores and timestamps for analytics."
    )

    with st.expander("Focus Settings & Privacy", expanded=False):
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            sensitivity = st.selectbox(
                "Sensitivity",
                ["low", "medium", "high"],
                index=["low", "medium", "high"].index(focus_settings.get("sensitivity", "medium")),
                help="Higher sensitivity requires clearer focus to stay in 'Focused'.",
            )
        with col_s2:
            sampling_interval = st.number_input(
                "Sampling interval (ms)",
                min_value=500,
                max_value=3000,
                value=int(focus_settings.get("sampling_interval", 1000)),
                step=100,
                help="How often focus updates are sent to the app.",
            )
        with col_s3:
            auto_pause = st.toggle(
                "Auto-pause timers",
                value=focus_settings.get("auto_pause", True),
                help="When on, study timers pause if you look away.",
            )
        with col_s4:
            history_hours = st.selectbox(
                "Keep history for",
                [6, 12, 24, 48, 168],
                index=[6, 12, 24, 48, 168].index(focus_settings.get("history_hours", 24)),
                help="How long to keep focus events in memory for charts.",
            )

        focus_settings = {
            "sensitivity": sensitivity,
            "sampling_interval": sampling_interval,
            "auto_pause": auto_pause,
            "history_hours": history_hours,
            "show_preview": st.session_state.get("focus_show_preview", False),
        }
        st.session_state["focus_settings"] = focus_settings

    # Render component and capture updates
    max_history = int((focus_settings["history_hours"] * 3600 * 1000) / focus_settings["sampling_interval"])
    focus_component_data = render_focus_detector(
        enabled=st.session_state.get("focus_enabled", False),
        show_preview=st.session_state.get("focus_show_preview", False),
        settings=focus_settings,
        key="focus_detector_component",
        height=260,
    )
    update_focus_state(
        focus_component_data,
        st.session_state,
        max_history=max(200, min(max_history, 5000)),
    )


# Initialize focus state early
init_focus_state()

# --------------------------------------------
# Helper for rerun (compatible with new Streamlit)
# --------------------------------------------
def rerun_app():
    st.session_state["__rerun__"] = not st.session_state.get("__rerun__", False)

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
    
    if st.button("Reset Tracker", use_container_width=True, type="secondary"):
        reset_database()
        st.success("All topics and progress have been cleared!")
        rerun_app()
    
    st.markdown(
        '<hr style="border: none; height: 1px; background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent); margin: 2rem 0;">',
        unsafe_allow_html=True
    )
    
    st.markdown(
        '<div style="text-align: center; padding: 1rem 0; margin-bottom: 1rem;">'
        '<h3 style="font-family: \'Sora\', sans-serif; color: rgba(255, 255, 255, 0.95); font-size: 1.2rem;">Quick Stats</h3>'
        '</div>',
        unsafe_allow_html=True
    )
    try:
        stats = get_statistics()
        st.metric("Total Topics", stats.get('total_topics', 0))
        st.metric("Total Time", f"{stats.get('total_time', 0)} mins")
        st.metric("Completed", stats.get('by_status', {}).get('Completed', 0))
    except:
        pass
    
    st.markdown(
        '<hr style="border: none; height: 1px; background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent); margin: 2rem 0;">',
        unsafe_allow_html=True
    )
    
    st.markdown(
        '<div style="text-align: center; padding: 1rem 0;">'
        '<h3 style="font-family: \'Sora\', sans-serif; color: rgba(255, 255, 255, 0.95); font-size: 1.2rem;">About</h3>'
        '<p style="color: rgba(255, 255, 255, 0.7); font-family: \'Inter\', sans-serif; margin-top: 0.5rem;">SmartStudyMate v2.0</p>'
        '<p style="color: rgba(255, 255, 255, 0.7); font-family: \'Inter\', sans-serif;">AI-powered learning companion</p>'
        '</div>',
        unsafe_allow_html=True
    )

# --------------------------------------------
# 🎨 Premium SaaS Hero Section
# --------------------------------------------
with st.container():
    col_hero_left, col_hero_right = st.columns([3, 1])
    with col_hero_left:
        st.markdown(
            """
            <div class="hero-container">
                <h1 class="hero-title">SmartStudyMate</h1>
                <p class="hero-tagline">Your AI-powered learning companion</p>
                <p class="hero-subtext">Extract, summarize, and track your study notes with polished focus-aware insights.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_hero_right:
        st.markdown(
            get_focus_status_indicator(
                st.session_state.get("focus_state", "disabled"),
                st.session_state.get("focus_score", 0.0),
            ),
            unsafe_allow_html=True,
        )

# Global focus controls (applies to all tabs/features)
render_focus_controls()

tab1, tab2, tab3 = st.tabs(
    ["Learning Tracker", "Upload & OCR", "Analytics Dashboard"]
)

# --------------------------------------------
# TAB 1 - Learning Tracker
# --------------------------------------------
with tab1:
    # Section Header
    ui_section_heading("Learning Tracker", kicker="Plan & track")
    focus_summary_card(
        st.session_state.get("focus_state", "disabled"),
        st.session_state.get("focus_score", 0.0),
        st.session_state.get("focus_history", []),
    )

    # Add New Topic Card
    with st.container():
        st.markdown("### Add New Topic")
        with st.expander("Show form", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                topic_name_input = st.text_input("Enter topic name", key="add_topic_input")
                difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1, key="difficulty_input")
            with col2:
                goal_time = st.number_input("Goal Time (minutes)", min_value=0, value=0, key="goal_time_input")
                notes = st.text_area("Notes (optional)", key="notes_input", height=100)
            
            if st.button("Add Topic", key="add_topic_button", type="primary", use_container_width=True):
                if topic_name_input.strip():
                    topic_id = add_topic(topic_name_input, difficulty=difficulty, notes=notes, goal_time=int(goal_time))
                    st.success(f"Added '{topic_name_input}' to tracker!")
                    rerun_app()
                else:
                    st.warning("Please enter a topic name!")

    # Your Topics Section
    st.markdown("---")
    st.markdown("### Your Topics")
    
    # Filter options
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        filter_status = st.selectbox("Filter by Status", ["All", "In Progress", "Completed", "Confusing"], key="filter_status")
    with col_filter2:
        filter_difficulty = st.selectbox("Filter by Difficulty", ["All", "Easy", "Medium", "Hard"], key="filter_difficulty")
    
    # Get filtered topics
    status_filter = None if filter_status == "All" else filter_status
    difficulty_filter = None if filter_difficulty == "All" else filter_difficulty
    topics = get_topics(status=status_filter, difficulty=difficulty_filter, sort_by="updated_at", order="DESC")
    
    if topics:
        # Status badges
        status_colors = {
            'Completed': '🟢',
            'In Progress': '🟡',
            'Confusing': '🔴'
        }
        difficulty_colors = {
            'Easy': '🟢',
            'Medium': '🟡',
            'Hard': '🔴'
        }
        
        for topic in topics:
            topic_id = topic['id']
            name = topic['topic_name']
            time_spent = topic.get('time_spent', 0)
            status = topic.get('status', 'In Progress')
            difficulty = topic.get('difficulty', 'Medium')
            goal_time = topic.get('goal_time', 0)
            notes = topic.get('notes', '')
            
            # Create a nice header with badges
            # Removed emoji icons from status/difficulty display
            status_icon = ""
            diff_icon = ""
            
            # Create 3D card header with enhanced styling
            header_text = f"**{name}** | {time_spent} mins | {difficulty}"
            
            # Wrap expander in custom styled container
            with st.expander(header_text, expanded=False):
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    timer_key = f"timer_{topic_id}"
                    stop_key = f"stop_{topic_id}"
                    save_session_key = f"save_session_{topic_id}"
                    
                    if timer_key in st.session_state:
                        if (
                            st.session_state.get("focus_enabled")
                            and st.session_state.get("focus_settings", {}).get("auto_pause", True)
                        ):
                            paused, pause_msg = pause_timer_if_not_focused(
                                timer_key,
                                st.session_state.get("focus_state", "disabled"),
                                st.session_state,
                            )
                            if pause_msg:
                                st.caption(pause_msg)

                        elapsed_seconds = get_timer_elapsed_with_pauses(timer_key, st.session_state)
                        elapsed = int(elapsed_seconds / 60)
                        st.info(f"Timer running (focus-aware): {elapsed} minutes")
                        if st.session_state.get("focus_state") in ["not_focused", "away"]:
                            st.warning("Focus low — auto-pause may engage. Look at the camera to resume.")
                        
                        # Use a form to handle session notes properly
                        with st.form(key=f"session_form_{topic_id}"):
                            session_notes = st.text_input(f"Session notes for {name}", key=f"notes_{topic_id}", 
                                                         value="", placeholder="What did you study?")
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                stop_submitted = st.form_submit_button(f"Stop Timer", type="primary", use_container_width=True)
                            with col_btn2:
                                save_submitted = st.form_submit_button("Save Session", use_container_width=True)
                            
                            if stop_submitted or save_submitted:
                                end = time.time()
                                minutes = max(1, int(elapsed_seconds / 60))
                                update_time(topic_id, minutes, session_notes)
                                del st.session_state[timer_key]
                                session_start = st.session_state.pop(f"focus_session_start_{topic_id}", end - elapsed_seconds)
                                focus_summary = compute_topic_focus_summary(
                                    topic_id,
                                    session_start,
                                    end,
                                    st.session_state.get("focus_history", []),
                                )
                                st.session_state["current_topic_focus_summary"] = focus_summary
                                save_focus_session(
                                    {
                                        "session_id": f"{topic_id}_{int(end)}",
                                        "topic_id": topic_id,
                                        "start_ts": session_start,
                                        "end_ts": end,
                                        "avg_focus": focus_summary.get("avg_focus", 0.0),
                                        "focus_percentage": focus_summary.get("focus_percentage", 0.0),
                                        "events_count": focus_summary.get("events_count", 0),
                                    }
                                )
                                st.success(f"Added {minutes} mins to {name}")
                                rerun_app()
                    else:
                        if st.button(f"Start Timer", key=f"start_{topic_id}", type="primary", use_container_width=True):
                            st.session_state[timer_key] = time.time()
                            st.session_state[f"focus_session_start_{topic_id}"] = time.time()
                            st.success(f"Timer started for {name}")
                            rerun_app()

                with col2:
                    new_status = st.selectbox(
                        "Status",
                        ["In Progress", "Completed", "Confusing"],
                        key=f"status_{topic_id}",
                        index=["In Progress", "Completed", "Confusing"].index(status) if status in ["In Progress", "Completed", "Confusing"] else 0
                    )
                    if st.button(f"Save Status", key=f"save_status_{topic_id}", use_container_width=True):
                        update_status(topic_id, new_status)
                        st.success("Status updated!")
                        rerun_app()

                with col3:
                    new_difficulty = st.selectbox(
                        "Difficulty",
                        ["Easy", "Medium", "Hard"],
                        key=f"difficulty_{topic_id}",
                        index=["Easy", "Medium", "Hard"].index(difficulty) if difficulty in ["Easy", "Medium", "Hard"] else 1
                    )
                    if st.button(f"Update Difficulty", key=f"update_diff_{topic_id}", use_container_width=True):
                        update_topic(topic_id, difficulty=new_difficulty)
                        st.success("Difficulty updated!")
                        rerun_app()

                with col4:
                    if st.button(f"Delete", key=f"delete_{topic_id}", type="secondary", use_container_width=True):
                        delete_topic(topic_id)
                        st.warning(f"Deleted topic '{name}'")
                        rerun_app()
                
                st.markdown("---")
                
                # Progress bar for goals
                if goal_time > 0:
                    progress = min(100, (time_spent / goal_time) * 100)
                    st.markdown(f"**Goal Progress:** {goal_time} mins")
                    st.progress(progress / 100)
                    st.caption(f"{time_spent}/{goal_time} mins ({progress:.1f}%)")
                    
                    if progress >= 100:
                        st.balloons()
                        st.success("Goal achieved!")
                
                # Notes section
                if notes:
                    st.markdown(f"**Notes:**")
                    st.info(notes)
                
                # Recent sessions
                sessions = get_study_sessions(topic_id=topic_id, limit=5)
                if sessions:
                    st.markdown("**Recent Study Sessions:**")
                    for session in sessions[:5]:
                        session_date = session.get('session_date', '')[:10] if session.get('session_date') else 'Unknown'
                        duration = session.get('duration_minutes', 0)
                        session_notes = session.get('notes', '')
                        st.caption(f"  • {session_date}: {duration} mins" + (f" - {session_notes}" if session_notes else ""))
                
                # Focus summary for this topic (latest)
                focus_summary = st.session_state.get("current_topic_focus_summary")
                if focus_summary and focus_summary.get("topic_id") == topic_id:
                    st.markdown("**Focus summary (last session):**")
                    st.caption(
                        f"Avg focus score: {focus_summary.get('avg_focus', 0.0):.2f} | "
                        f"Focused time: {focus_summary.get('focus_seconds', 0):.0f}s / "
                        f"{focus_summary.get('total_seconds', 0):.0f}s "
                        f"({focus_summary.get('focus_percentage', 0.0):.1f}% weighted)"
                    )
    else:
        st.markdown(
            """
            <div class="empty-state">
                <div class="empty-state-icon"></div>
                <div class="empty-state-message">No topics found</div>
                <div class="empty-state-hint">Use the form above to start tracking your learning progress</div>
            </div>
            """,
            unsafe_allow_html=True
        )

# --------------------------------------------
# TAB 2 - Upload Notes (OCR + Hugging Face Summarizer + Recommender)
# --------------------------------------------
with tab2:
    # Section Header
    ui_section_heading("Upload & OCR Recognition", kicker="Extract & summarize")
    focus_summary_card(
        st.session_state.get("focus_state", "disabled"),
        st.session_state.get("focus_score", 0.0),
        st.session_state.get("focus_history", []),
    )
    
    # Info Banner
    st.markdown(
        """
        <div class="info-banner">
            <div class="info-banner-icon"></div>
            <p class="info-banner-text">
                <strong>Tip:</strong> Upload handwritten notes, whiteboard photos, or PDFs. 
                Our advanced OCR can extract text and AI will summarize it for you!
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
        use_trocr = st.toggle(
            "Handwritten Text Mode",
            key="use_trocr_toggle",
            help="Enable for better handwritten text recognition (uses TrOCR model)"
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
        try:
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
        except Exception as e:
            st.error(f"Error saving file: {e}")
            st.stop()

        if st.button("Extract and Process", key="process_file", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            status_text.info("Processing your file, please wait...")
            progress_bar.progress(20)
            
            try:
                result = extract_text(file_path, use_trocr=use_trocr, get_confidence=True)
                if isinstance(result, tuple):
                    extracted_text, confidence = result
                else:
                    extracted_text = result
                    confidence = None
                progress_bar.progress(60)
            except Exception as e:
                st.error(f"Error processing file: {e}")
                extracted_text = ""
                confidence = None
                progress_bar.progress(0)
                st.exception(e)  # Show full traceback for debugging

            progress_bar.progress(100)
            
            if extracted_text.strip():
                status_text.success("Text successfully extracted!")
            focus_meta = tag_ocr_session_with_focus(
                st.session_state.get("focus_state", "disabled"),
                st.session_state.get("focus_score", 0.0),
                st.session_state.get("focus_history", []),
                session_start_time=st.session_state.get("upload_focus_start"),
            )
            st.info(f"Focus during upload: {focus_meta.get('focus_during_upload', 'N/A')}")
            if focus_quality_check and focus_meta.get("avg_focus_score", 0.0) < 0.45:
                st.warning("Low focus detected during upload. Consider re-scanning for best results.")
            
            # Show confidence if available
            if confidence is not None:
                confidence_label = "High" if confidence > 70 else "Medium" if confidence > 40 else "Low"
                st.info(f"Confidence: {confidence:.1f}% ({confidence_label})")
            
            st.markdown("---")
            
            # Extracted Text
            st.markdown("### Extracted Text")
            st.text_area("Detected text", extracted_text, height=300, label_visibility="collapsed")
            
            st.markdown("---")
            
            # AI Summary
            st.markdown("### AI Summary")
            with st.spinner("Generating summary with AI..."):
                try:
                    summary = summarize_text(extracted_text)
                    st.success("Summary generated!")
                    st.info(summary)
                except Exception as e:
                    st.error(f"Summary failed: {e}")

            # Keywords
            st.markdown("### Key Concepts Detected")
            with st.spinner("Extracting keywords..."):
                try:
                    keywords = extract_keywords(extracted_text, num_keywords=8)
                    if keywords:
                        # Display as badges
                        keyword_badges = " ".join([f"`{kw}`" for kw in keywords])
                        st.markdown(keyword_badges)
                    else:
                        st.info("No clear keywords detected.")
                except Exception as e:
                    st.error(f"Keyword extraction failed: {e}")

            # Study Resource Recommendations
            if keywords and len(keywords) > 0:
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

            # Add to Tracker
            st.markdown("---")
            st.markdown("### Save to Tracker")
            col_track1, col_track2 = st.columns([2, 1])
            with col_track1:
                tracker_topic = st.text_input("Enter topic name:", key="tracker_topic_input", placeholder="e.g., Machine Learning Basics")
            with col_track2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Save to Tracker", key="save_tracker_button", type="primary", use_container_width=True):
                    if tracker_topic.strip():
                        add_topic(tracker_topic)
                        st.success(f"'{tracker_topic}' added to tracker!")
                        rerun_app()
                    else:
                        st.warning("Please enter a topic name.")

# --------------------------------------------
# TAB 3 - Analytics Dashboard
# --------------------------------------------
with tab3:
    # Section Header
    ui_section_heading("Analytics Dashboard", kicker="Insights")
    focus_summary_card(
        st.session_state.get("focus_state", "disabled"),
        st.session_state.get("focus_score", 0.0),
        st.session_state.get("focus_history", []),
    )
    
    result = generate_report()

    if isinstance(result, tuple) and len(result) == 4:
        df, charts, stats, feedback = result
    elif isinstance(result, tuple) and len(result) == 3:
        # Backward compatibility
        df, charts, feedback = result
        stats = None
        if isinstance(charts, str):
            # Old format
            charts = {'time_chart': charts}
    else:
        st.markdown(
            """
            <div class="empty-state">
                <div class="empty-state-icon"></div>
                <div class="empty-state-message">No data yet</div>
                <div class="empty-state-hint">Add and track topics to see analytics and insights</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.stop()

    if isinstance(df, str):
        st.info(df)
    else:
        # Statistics overview
        if stats:
            st.markdown("### Quick Stats")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Topics", stats.get('total_topics', 0))
            with col2:
                st.metric("Total Time", f"{stats.get('total_time', 0)} mins")
            with col3:
                st.metric("Completed", stats.get('by_status', {}).get('Completed', 0))
            with col4:
                st.metric("Recent Sessions", stats.get('recent_sessions', 0))
        
        st.markdown("---")
        
        # Visualizations
        st.markdown("### Visualizations")
        
        # Display all available charts
        if charts:
            chart_tabs = st.tabs(list(charts.keys()))
            for i, (chart_name, chart_path) in enumerate(charts.items()):
                with chart_tabs[i]:
                    if os.path.exists(chart_path):
                        st.image(chart_path)
                    else:
                        st.info(f"Chart not available: {chart_name}")
        
        st.markdown("---")

        # Focus analytics
        st.markdown("### Focus Analytics")
        focus_history = st.session_state.get("focus_history", [])
        focus_sessions = load_focus_sessions()

        col_focus1, col_focus2 = st.columns(2)
        with col_focus1:
            if focus_history:
                df_focus = pd.DataFrame(focus_history)
                df_focus["ts"] = pd.to_datetime(df_focus["timestamp"], unit="ms")
                st.line_chart(df_focus.set_index("ts")["score"], height=220, use_container_width=True)
            else:
                st.info("No focus timeline data yet. Enable tracking to see live trends.")
        with col_focus2:
            distribution = compute_focus_distribution(focus_history)
            dist_df = pd.DataFrame(list(distribution.items()), columns=["state", "count"])
            if dist_df["count"].sum() > 0:
                st.bar_chart(dist_df.set_index("state"), height=220, use_container_width=True)
            else:
                st.info("Focus distribution will appear once events are recorded.")

        if focus_history:
            df_focus["hour"] = df_focus["ts"].dt.hour
            df_focus["day"] = df_focus["ts"].dt.day_name()
            heatmap_df = (
                df_focus.groupby(["day", "hour"])["score"]
                .mean()
                .reset_index()
                .pivot(index="day", columns="hour", values="score")
                .fillna(0)
            )
            st.markdown("**Heatmap: Average focus by hour/day**")
            st.dataframe(heatmap_df)

        if focus_sessions:
            st.markdown("**Average focus per topic (saved sessions)**")
            sessions_df = pd.DataFrame(focus_sessions)
            if "end_ts" in sessions_df:
                sessions_df["ended_at"] = pd.to_datetime(sessions_df["end_ts"], unit="s", errors="coerce")
            topic_focus = (
                sessions_df.groupby("topic_id")["focus_percentage"]
                .mean()
                .reset_index()
                .rename(columns={"focus_percentage": "avg_focus_pct"})
            )
            st.bar_chart(topic_focus.set_index("topic_id"), height=240, use_container_width=True)

            csv_data = sessions_df.to_csv(index=False)
            st.download_button(
                "Export focus summaries (CSV)",
                data=csv_data,
                file_name="focus_sessions.csv",
                mime="text/csv",
            )
        else:
            st.info("No saved focus sessions yet. Finish a study timer to record one.")
        
        # Learning Data
        st.markdown("### Learning Data")
        st.dataframe(df, use_container_width=True)

        st.markdown("---")
        
        # Feedback
        st.markdown("### AI-Powered Learning Feedback")
        st.markdown(feedback)
        
        st.markdown("---")
        
        # Export functionality
        st.markdown("### Export Data")
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            if st.button("Export as JSON", key="export_json"):
                try:
                    json_data = export_data(format="json")
                    st.download_button(
                        label="Download JSON",
                        data=json_data,
                        file_name=f"learning_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
                except Exception as e:
                    st.error(f"Export failed: {e}")
        with col_exp2:
            if st.button("Export as CSV", key="export_csv"):
                try:
                    csv_data = export_data(format="csv")
                    st.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name=f"learning_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                except Exception as e:
                    st.error(f"Export failed: {e}")

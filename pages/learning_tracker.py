import os
import sys
import time
import streamlit as st

# Add parent directory to path to allow imports from root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import (
    add_topic,
    get_topics,
    update_time,
    update_status,
    delete_topic,
    update_topic,
    get_study_sessions
)
from focus.integrations import (
    compute_topic_focus_summary,
    get_timer_elapsed_with_pauses,
    pause_timer_if_not_focused,
    save_focus_session
)
from ui.components import (
    ui_section_heading,
    focus_summary_card,
    hero_card
)
from utils.text import strip_emojis

st.set_page_config(page_title="Learning Tracker", page_icon="📝", layout="wide")

# Load Theme
def load_custom_css():
    css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "ui_theme.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_custom_css()

# Helper for rerun
def rerun_app():
    st.rerun()

# Section Header
with hero_card():
    st.markdown(
        f"""
        <h1 class="hero-title">{strip_emojis("Learning Tracker")}</h1>
        <p class="hero-tagline">{strip_emojis("Plan & track")}</p>
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

# Add New Topic Card
with st.container():
    from ui.components import ui_card
    with ui_card(title=strip_emojis("Add New Topic")):
        with st.expander(strip_emojis("Show form"), expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            topic_name_input = st.text_input("Enter topic name", key="add_topic_input")
            difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1, key="difficulty_input")
        with col2:
            goal_time = st.number_input("Goal Time (minutes)", min_value=0, value=0, key="goal_time_input")
            notes = st.text_area("Notes (optional)", key="notes_input", height=100)
        
        if st.button("Add Topic", key="add_topic_button", type="primary", use_container_width=True):
            cleaned_topic = strip_emojis(topic_name_input).strip()
            if cleaned_topic:
                topic_id = add_topic(cleaned_topic, difficulty=difficulty, notes=strip_emojis(notes), goal_time=int(goal_time))
                st.success(f"Added '{cleaned_topic}' to tracker!")
                rerun_app()
            else:
                st.warning("Please enter a valid topic name!")

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
    for topic in topics:
        topic_id = topic['id']
        name = strip_emojis(topic['topic_name'])
        time_spent = topic.get('time_spent', 0)
        status = topic.get('status', 'In Progress')
        difficulty = topic.get('difficulty', 'Medium')
        goal_time = topic.get('goal_time', 0)
        notes = strip_emojis(topic.get('notes', ''))
        
        # Create header text without emojis
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
                            cleaned_notes = strip_emojis(session_notes)
                            update_time(topic_id, minutes, cleaned_notes)
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
                    session_notes = strip_emojis(session.get('notes', ''))
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
            <div class="empty-state-message">No topics found</div>
            <div class="empty-state-hint">Use the form above to start tracking your learning progress</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# End page content
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)


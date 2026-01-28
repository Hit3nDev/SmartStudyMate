import os
import sys
from datetime import datetime
import pandas as pd
import streamlit as st

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import (
    get_statistics,
    export_data
)
from focus.integrations import (
    compute_focus_distribution,
    load_focus_sessions
)
from ui.components import (
    ui_section_heading,
    focus_summary_card,
    hero_card
)
from tracker import generate_report

st.set_page_config(page_title="Analytics Dashboard", page_icon="📊", layout="wide")

# Load Theme
def load_custom_css():
    css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "ui_theme.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_custom_css()

# Section Header
with hero_card():
    st.markdown(
        """
        <h1 class="hero-title">Analytics Dashboard</h1>
        <p class="hero-tagline">Insights</p>
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
                    file_name="smartstudymate_export.json",
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
                    file_name="smartstudymate_export.csv",
                    mime="text/csv"
                )
            except Exception as e:
                st.error(f"Export failed: {e}")

# End page content
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

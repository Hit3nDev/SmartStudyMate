import streamlit as st
from typing import Optional, Union, List


def ui_container(max_width: int = 1180):
    """Context manager for a centered container."""
    return st.container()


def ui_glass_card(title: Optional[str] = None, subtitle: Optional[str] = None):
    """Context manager for a glassy card wrapper."""
    header = ""
    if title:
        header = f"""
        <div class="ui-card-header">
            <div class="ui-card-title">{title}</div>
            {'<div class="ui-card-subtitle">' + subtitle + '</div>' if subtitle else ''}
        </div>
        """
        st.markdown(header, unsafe_allow_html=True)
    return st.container()


def ui_section_heading(title: str, kicker: Optional[str] = None):
    """Render a consistent section heading."""
    st.markdown(
        f"""
        <div class="ui-section-heading">
            {f'<span class="ui-kicker">{kicker}</span>' if kicker else ''}
            <h2>{title}</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_pill(label: str, tone: str = "neutral", detail: Optional[str] = None):
    """Render a status pill with tone classes."""
    st.markdown(
        f"""
        <div class="status-pill status-{tone}">
            <span class="pill-dot"></span>
            <span>{label}</span>
            {f'<span class="pill-detail">{detail}</span>' if detail else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


from contextlib import contextmanager

@contextmanager
def hero_card():
    """Context manager for the hero section card."""
    st.markdown('<div class="hero-card">', unsafe_allow_html=True)
    yield
    st.markdown('</div>', unsafe_allow_html=True)


def focus_widget(state: str, score: float):
    """Render a compact focus status widget."""
    pct = int(score * 100)
    tone_map = {
        "focused": "success",
        "partial": "warning",
        "not_focused": "danger",
        "away": "muted",
        "disabled": "muted",
    }
    tone = tone_map.get(state, "muted")
    
    st.markdown(
        f"""
        <div class="focus-mini-card">
            <div class="focus-mini-top">
                <span style="font-weight:600; font-size:14px; color:rgba(255,255,255,0.8);">Focus Status</span>
                <div class="focus-pill pill-{tone}">
                    <span class="pill-dot"></span>
                    <span>{state.replace('_', ' ').title()}</span>
                    <span class="pill-detail">{pct}%</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def focus_summary_card(state: str, score: float, history: Optional[List[dict]] = None):
    """Compact focus summary widget with pill."""
    # Reusing focus_widget for consistency
    focus_widget(state, score)



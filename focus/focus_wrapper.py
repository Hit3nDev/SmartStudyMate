"""
Focus Detection Wrapper for Streamlit
Handles communication between the HTML/JS component and Streamlit app
"""
import json
import os
import time
from typing import Dict, Optional, Tuple

import streamlit.components.v1 as components

# Path to the HTML component
COMPONENT_PATH = os.path.join(os.path.dirname(__file__), "..", "components", "focus_detector.html")

def ensure_focus_session_state(session_state: Dict) -> None:
    """Initialize default focus-related session state keys."""
    defaults = {
        "focus_enabled": False,
        "focus_state": "disabled",
        "focus_score": 0.0,
        "focus_last_seen": None,
        "focus_history": [],
        "focus_settings": {
            "sensitivity": "medium",
            "sampling_interval": 1000,
            "auto_pause": True,
            "history_hours": 24,
            "show_preview": False,
        },
    }
    for key, value in defaults.items():
        session_state.setdefault(key, value)


def render_focus_detector(
    enabled: bool = False,
    show_preview: bool = False,
    settings: Optional[Dict] = None,
    key: str = "focus_detector",
    height: int = 260,
) -> Dict:
    """
    Render the focus detector component.
    
    Args:
        enabled: Whether focus detection is enabled
        show_preview: Whether to show camera preview
        key: Unique key for the component
    
    Returns:
        Dictionary with focus state data: {state, score, timestamp}
    """
    # Read the HTML file
    if not os.path.exists(COMPONENT_PATH):
        return {"state": "disabled", "score": 0.0, "timestamp": int(time.time() * 1000)}
    
    with open(COMPONENT_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()

    config_payload = {
        "sensitivity": settings.get("sensitivity") if settings else "medium",
        "samplingInterval": settings.get("sampling_interval", 1000) if settings else 1000,
        "showPreview": show_preview,
        "autoStart": enabled,
    }

    # Inject configuration so the component boots with the correct settings
    injection = f"<script>window.initialFocusConfig = {json.dumps(config_payload)};</script>"
    html_content = html_content.replace("<body>", f"<body>{injection}", 1)
    
    # Render the component
    result = components.html(
        html_content,
        height=height if show_preview else 80,
    )

    # Return result or default
    if result is None:
        return {"state": "disabled", "score": 0.0, "timestamp": int(time.time() * 1000)}
    
    return result if isinstance(result, dict) else {"state": "disabled", "score": 0.0, "timestamp": int(time.time() * 1000)}


def update_focus_state(
    focus_data: Dict,
    session_state: Dict,
    max_history: Optional[int] = None
) -> None:
    """
    Update Streamlit session state with focus detection data.
    
    Args:
        focus_data: Dictionary from focus detector component
        session_state: Streamlit session state dictionary
    """
    if not focus_data:
        return
    
    state = focus_data.get("state", "disabled")
    score = focus_data.get("score", 0.0)
    timestamp = focus_data.get("timestamp", int(time.time() * 1000))
    
    # Update session state
    session_state["focus_state"] = state
    session_state["focus_score"] = score
    session_state["focus_last_seen"] = timestamp
    
    # Update history
    if "focus_history" not in session_state:
        session_state["focus_history"] = []
    
    session_state["focus_history"].append({
        "timestamp": timestamp,
        "state": state,
        "score": score
    })
    
    # Keep only last N entries for performance
    max_history = max_history or 1000
    if len(session_state["focus_history"]) > max_history:
        session_state["focus_history"] = session_state["focus_history"][-max_history:]


def get_focus_status_indicator(state: str, score: float) -> str:
    """
    Get HTML for focus status indicator pill.
    
    Args:
        state: Focus state string
        score: Focus score (0-1)
    
    Returns:
        HTML string for the indicator
    """
    tone_map = {
        "focused": "success",
        "partial": "warning",
        "not_focused": "danger",
        "away": "muted",
        "disabled": "muted",
    }
    tone = tone_map.get(state, "muted")
    
    indicators = {
        "focused": ("🟢", "Focused"),
        "partial": ("🟡", "Partial"),
        "not_focused": ("🔴", "Not Focused"),
        "away": ("⚪", "Away"),
        "disabled": ("⚪", "Disabled")
    }
    
    icon, label = indicators.get(state, ("⚪", "Unknown"))
    detail = f"{int(score * 100)}%" if state != "disabled" else ""
    
    return f"""
    <div class="status-pill status-{tone}" style="margin-top: 12px;">
        <span class="pill-dot"></span>
        <span>{icon} {label}</span>
        {f'<span class="pill-detail">{detail}</span>' if detail else ''}
    </div>
    """

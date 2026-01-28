"""
Focus Detection Integration Helpers
Functions to integrate focus detection with app features
"""
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json
import os


def pause_timer_if_not_focused(
    timer_key: str,
    focus_state: str,
    session_state: Dict
) -> Tuple[bool, Optional[str]]:
    """
    Pause a timer if user is not focused.
    
    Args:
        timer_key: Key for the timer in session_state
        focus_state: Current focus state
        session_state: Streamlit session state
    
    Returns:
        Tuple of (was_paused, message)
    """
    if timer_key not in session_state:
        return False, None
    
    # States that should pause the timer
    pause_states = ["not_focused", "away"]
    
    if focus_state in pause_states:
        # Check if timer was already paused
        pause_key = f"{timer_key}_paused"
        if pause_key not in session_state:
            # Store original start time and pause
            session_state[pause_key] = {
                "original_start": session_state[timer_key],
                "paused_at": time.time(),
                "total_paused_time": 0
            }
            return True, "⏸️ Timer paused — you're away"
    
    # Resume if focused again
    elif focus_state == "focused":
        pause_key = f"{timer_key}_paused"
        if pause_key in session_state:
            # Calculate paused duration and adjust start time
            pause_info = session_state[pause_key]
            paused_duration = time.time() - pause_info["paused_at"]
            pause_info["total_paused_time"] += paused_duration
            
            # Adjust the timer start time forward by paused duration
            session_state[timer_key] = session_state[timer_key] + paused_duration
            
            del session_state[pause_key]
            return False, "▶️ Timer resumed"
    
    return False, None


def get_timer_elapsed_with_pauses(
    timer_key: str,
    session_state: Dict
) -> float:
    """
    Get elapsed time for a timer accounting for pauses.
    
    Args:
        timer_key: Key for the timer
        session_state: Streamlit session state
    
    Returns:
        Elapsed time in seconds
    """
    if timer_key not in session_state:
        return 0.0
    
    elapsed = time.time() - session_state[timer_key]
    
    # Subtract paused time if timer was paused
    pause_key = f"{timer_key}_paused"
    if pause_key in session_state:
        pause_info = session_state[pause_key]
        paused_duration = time.time() - pause_info["paused_at"]
        elapsed -= (pause_info["total_paused_time"] + paused_duration)
    
    return max(0.0, elapsed)


def compute_topic_focus_summary(
    topic_id: int,
    start_time: float,
    end_time: float,
    focus_history: List[Dict]
) -> Dict:
    """
    Compute focus summary for a study session.
    
    Args:
        topic_id: Topic ID
        start_time: Session start timestamp (Unix time)
        end_time: Session end timestamp (Unix time)
        focus_history: List of focus events with timestamps
    
    Returns:
        Dictionary with focus metrics
    """
    # Filter focus events within session timeframe
    session_events = [
        event for event in focus_history
        if start_time * 1000 <= event.get("timestamp", 0) <= end_time * 1000
    ]
    
    if not session_events:
        return {
            "topic_id": topic_id,
            "start_ts": start_time,
            "end_ts": end_time,
            "focus_seconds": 0,
            "total_seconds": end_time - start_time,
            "avg_focus": 0.0,
            "focus_percentage": 0.0,
            "events_count": 0
        }
    
    # Calculate time spent in each state
    total_time = end_time - start_time
    focused_time = 0.0
    partial_time = 0.0
    not_focused_time = 0.0
    
    # Sort events by timestamp
    session_events.sort(key=lambda x: x.get("timestamp", 0))
    
    # Calculate time in each state
    for i in range(len(session_events) - 1):
        event = session_events[i]
        next_event = session_events[i + 1]
        
        state = event.get("state", "not_focused")
        duration = (next_event.get("timestamp", 0) - event.get("timestamp", 0)) / 1000.0
        
        if state == "focused":
            focused_time += duration
        elif state == "partial":
            partial_time += duration
        else:
            not_focused_time += duration
    
    # Handle last event to end of session
    if session_events:
        last_event = session_events[-1]
        state = last_event.get("state", "not_focused")
        duration = (end_time * 1000 - last_event.get("timestamp", 0)) / 1000.0
        
        if state == "focused":
            focused_time += duration
        elif state == "partial":
            partial_time += duration
        else:
            not_focused_time += duration
    
    # Calculate weighted focus time (focused = 1.0, partial = 0.5, not_focused = 0.0)
    focus_seconds = focused_time + (partial_time * 0.5)
    avg_focus = sum(e.get("score", 0.0) for e in session_events) / len(session_events) if session_events else 0.0
    focus_percentage = (focus_seconds / total_time * 100) if total_time > 0 else 0.0
    
    return {
        "topic_id": topic_id,
        "start_ts": start_time,
        "end_ts": end_time,
        "focus_seconds": focus_seconds,
        "total_seconds": total_time,
        "avg_focus": avg_focus,
        "focus_percentage": focus_percentage,
        "events_count": len(session_events)
    }


def tag_ocr_session_with_focus(
    focus_state: str,
    focus_score: float,
    focus_history: List[Dict],
    session_start_time: Optional[float] = None
) -> Dict:
    """
    Tag an OCR/upload session with focus metadata.
    
    Args:
        focus_state: Current focus state
        focus_score: Current focus score
        focus_history: Focus history list
        session_start_time: When the upload session started (Unix time)
    
    Returns:
        Dictionary with focus metadata for the session
    """
    if session_start_time is None:
        session_start_time = time.time()
    
    # Get focus events during the session (last 30 seconds or since session start)
    cutoff_time = (session_start_time - 30) * 1000  # 30 seconds before
    session_events = [
        event for event in focus_history
        if event.get("timestamp", 0) >= cutoff_time
    ]
    
    if not session_events:
        return {
            "focus_during_upload": "N/A",
            "avg_focus_score": 0.0,
            "focus_percentage": 0.0
        }
    
    avg_score = sum(e.get("score", 0.0) for e in session_events) / len(session_events)
    focus_percentage = avg_score * 100
    
    # Determine focus level
    if avg_score >= 0.75:
        focus_level = "High"
    elif avg_score >= 0.45:
        focus_level = "Medium"
    else:
        focus_level = "Low"
    
    return {
        "focus_during_upload": f"{focus_percentage:.0f}% ({focus_level})",
        "avg_focus_score": avg_score,
        "focus_percentage": focus_percentage
    }


def save_focus_session(
    session_data: Dict,
    file_path: Optional[str] = None
) -> None:
    """
    Save focus session data to JSON file.
    
    Args:
        session_data: Dictionary with session focus data
        file_path: Path to save file (default: data/focus_sessions.json)
    """
    if file_path is None:
        os.makedirs("data", exist_ok=True)
        file_path = "data/focus_sessions.json"
    
    # Load existing sessions
    sessions = []
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                sessions = json.load(f)
        except:
            sessions = []
    
    # Add new session
    sessions.append({
        **session_data,
        "saved_at": datetime.now().isoformat()
    })
    
    # Keep only last 100 sessions
    if len(sessions) > 100:
        sessions = sessions[-100:]
    
    # Save back
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(sessions, f, indent=2, default=str)


def load_focus_sessions(
    file_path: Optional[str] = None,
    limit: int = 100
) -> List[Dict]:
    """
    Load focus session data from JSON file.
    
    Args:
        file_path: Path to load file (default: data/focus_sessions.json)
        limit: Maximum number of sessions to return
    
    Returns:
        List of session dictionaries
    """
    if file_path is None:
        file_path = "data/focus_sessions.json"
    
    if not os.path.exists(file_path):
        return []
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            sessions = json.load(f)
        return sessions[-limit:] if len(sessions) > limit else sessions
    except:
        return []


def compute_focus_distribution(focus_history: List[Dict]) -> Dict[str, int]:
    """
    Compute distribution of focus states from history.
    
    Args:
        focus_history: List of focus events
    
    Returns:
        Dictionary mapping state to counts
    """
    distribution = {"focused": 0, "partial": 0, "not_focused": 0, "away": 0}
    for event in focus_history or []:
        state = event.get("state", "not_focused")
        if state in distribution:
            distribution[state] += 1
        else:
            distribution["not_focused"] += 1
    return distribution
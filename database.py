import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import json

# Ensure data folder exists
os.makedirs("data", exist_ok=True)

DB_PATH = "data/learning_tracker.db"

# Connection pool for better performance (thread-safe for Streamlit)
import threading
_connection_pool = None
_connection_lock = threading.Lock()

def get_connection():
    """Get a database connection with thread-safe connection pooling."""
    global _connection_pool
    if _connection_pool is None:
        with _connection_lock:
            # Double-check pattern
            if _connection_pool is None:
                try:
                    _connection_pool = sqlite3.connect(DB_PATH, check_same_thread=False)
                    _connection_pool.row_factory = sqlite3.Row  # Enable column access by name
                    # Enable foreign keys
                    _connection_pool.execute("PRAGMA foreign_keys = ON")
                except sqlite3.Error as e:
                    print(f"❌ Database connection error: {e}")
                    raise
    return _connection_pool

def migrate_database():
    """Migrate existing database to new schema by adding missing columns."""
    conn = get_connection()
    c = conn.cursor()
    
    # Check if old schema exists
    c.execute("PRAGMA table_info(topics)")
    columns = [row[1] for row in c.fetchall()]
    
    # Add new columns if they don't exist
    new_columns = {
        'difficulty': "TEXT DEFAULT 'Medium'",
        'notes': 'TEXT',
        'tags': 'TEXT',
        'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
        'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
        'goal_time': 'INTEGER DEFAULT 0',
        'last_studied': 'TIMESTAMP'
    }
    
    for col_name, col_def in new_columns.items():
        if col_name not in columns:
            try:
                c.execute(f"ALTER TABLE topics ADD COLUMN {col_name} {col_def}")
                print(f"Added column {col_name} to topics table")
            except Exception as e:
                print(f"Could not add column {col_name}: {e}")
    
    conn.commit()

def init_db():
    """Initialize the database and create enhanced tables with indexes."""
    conn = get_connection()
    c = conn.cursor()
    
    # Enhanced topics table with more fields
    c.execute('''
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_name TEXT NOT NULL,
            time_spent INTEGER DEFAULT 0,
            status TEXT DEFAULT 'In Progress',
            difficulty TEXT DEFAULT 'Medium',
            notes TEXT,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            goal_time INTEGER DEFAULT 0,
            last_studied TIMESTAMP
        )
    ''')
    
    # Migrate existing database
    migrate_database()
    
    # Create indexes for better query performance
    c.execute('CREATE INDEX IF NOT EXISTS idx_status ON topics(status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON topics(created_at)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_topic_name ON topics(topic_name)')
    
    # Create study sessions table for detailed tracking
    c.execute('''
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER,
            session_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            duration_minutes INTEGER,
            notes TEXT,
            FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_topic_id ON study_sessions(topic_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_session_date ON study_sessions(session_date)')
    
    conn.commit()


def reset_database():
    """Delete all topics and sessions from the database."""
    init_db()  # Ensure the table exists before deleting
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM study_sessions")  # Delete sessions first (foreign key)
    c.execute("DELETE FROM topics")  # Delete topics
    conn.commit()


def add_topic(topic_name: str, difficulty: str = "Medium", notes: str = "", tags: List[str] = None, goal_time: int = 0) -> int:
    """Add a new topic with enhanced fields. Returns the topic ID."""
    conn = get_connection()
    c = conn.cursor()
    tags_str = json.dumps(tags) if tags else None
    c.execute(
        "INSERT INTO topics (topic_name, difficulty, notes, tags, goal_time, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (topic_name, difficulty, notes, tags_str, goal_time, datetime.now(), datetime.now())
    )
    topic_id = c.lastrowid
    conn.commit()
    return topic_id


def get_topics(status: Optional[str] = None, difficulty: Optional[str] = None, 
               sort_by: str = "created_at", order: str = "DESC") -> List[Dict]:
    """Get topics with filtering and sorting options."""
    conn = get_connection()
    c = conn.cursor()
    
    query = "SELECT * FROM topics WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    if difficulty:
        query += " AND difficulty = ?"
        params.append(difficulty)
    
    # Validate sort_by to prevent SQL injection
    valid_sort_fields = ["id", "topic_name", "time_spent", "status", "created_at", "updated_at", "difficulty"]
    if sort_by not in valid_sort_fields:
        sort_by = "created_at"
    
    order = "DESC" if order.upper() == "DESC" else "ASC"
    query += f" ORDER BY {sort_by} {order}"
    
    c.execute(query, params)
    rows = c.fetchall()
    
    # Convert to list of dicts for easier handling
    topics = []
    for row in rows:
        topic = dict(row)
        # Parse tags JSON
        if topic.get('tags'):
            try:
                topic['tags'] = json.loads(topic['tags'])
            except:
                topic['tags'] = []
        else:
            topic['tags'] = []
        topics.append(topic)
    
    return topics


def update_time(topic_id: int, minutes: int, session_notes: str = ""):
    """Update time spent on a topic and create a study session record."""
    if minutes <= 0:
        return  # Don't update if no time was spent
    
    conn = get_connection()
    c = conn.cursor()
    
    try:
        # Check if topic exists
        c.execute("SELECT id FROM topics WHERE id = ?", (topic_id,))
        if not c.fetchone():
            raise ValueError(f"Topic with id {topic_id} does not exist")
        
        # Update topic time
        c.execute(
            "UPDATE topics SET time_spent = time_spent + ?, updated_at = ?, last_studied = ? WHERE id = ?",
            (minutes, datetime.now(), datetime.now(), topic_id)
        )
        
        # Create study session record
        c.execute(
            "INSERT INTO study_sessions (topic_id, duration_minutes, notes, session_date) VALUES (?, ?, ?, ?)",
            (topic_id, minutes, session_notes, datetime.now())
        )
        
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error: {e}")


def update_status(topic_id: int, new_status: str):
    """Update topic status."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE topics SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, datetime.now(), topic_id)
    )
    conn.commit()

def update_topic(topic_id: int, topic_name: Optional[str] = None, difficulty: Optional[str] = None,
                 notes: Optional[str] = None, tags: Optional[List[str]] = None, goal_time: Optional[int] = None):
    """Update multiple topic fields at once."""
    conn = get_connection()
    c = conn.cursor()
    
    updates = []
    params = []
    
    if topic_name is not None:
        updates.append("topic_name = ?")
        params.append(topic_name)
    
    if difficulty is not None:
        updates.append("difficulty = ?")
        params.append(difficulty)
    
    if notes is not None:
        updates.append("notes = ?")
        params.append(notes)
    
    if tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(tags))
    
    if goal_time is not None:
        updates.append("goal_time = ?")
        params.append(goal_time)
    
    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now())
        params.append(topic_id)
        
        query = f"UPDATE topics SET {', '.join(updates)} WHERE id = ?"
        c.execute(query, params)
        conn.commit()


def delete_topic(topic_id: int):
    """Delete a topic and its associated study sessions."""
    conn = get_connection()
    c = conn.cursor()
    # Sessions will be deleted automatically due to CASCADE
    c.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
    conn.commit()

def get_topic_by_id(topic_id: int) -> Optional[Dict]:
    """Get a single topic by ID."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM topics WHERE id = ?", (topic_id,))
    row = c.fetchone()
    if row:
        topic = dict(row)
        if topic.get('tags'):
            try:
                topic['tags'] = json.loads(topic['tags'])
            except:
                topic['tags'] = []
        else:
            topic['tags'] = []
        return topic
    return None

def get_study_sessions(topic_id: Optional[int] = None, limit: int = 100) -> List[Dict]:
    """Get study sessions, optionally filtered by topic."""
    conn = get_connection()
    c = conn.cursor()
    
    if topic_id:
        c.execute(
            "SELECT * FROM study_sessions WHERE topic_id = ? ORDER BY session_date DESC LIMIT ?",
            (topic_id, limit)
        )
    else:
        c.execute(
            "SELECT * FROM study_sessions ORDER BY session_date DESC LIMIT ?",
            (limit,)
        )
    
    rows = c.fetchall()
    return [dict(row) for row in rows]

def get_statistics() -> Dict:
    """Get comprehensive learning statistics."""
    conn = get_connection()
    c = conn.cursor()
    
    stats = {}
    
    # Total topics
    c.execute("SELECT COUNT(*) FROM topics")
    stats['total_topics'] = c.fetchone()[0]
    
    # Topics by status
    c.execute("SELECT status, COUNT(*) FROM topics GROUP BY status")
    stats['by_status'] = dict(c.fetchall())
    
    # Total time spent
    c.execute("SELECT SUM(time_spent) FROM topics")
    stats['total_time'] = c.fetchone()[0] or 0
    
    # Average time per topic
    if stats['total_topics'] > 0:
        stats['avg_time'] = stats['total_time'] / stats['total_topics']
    else:
        stats['avg_time'] = 0
    
    # Topics by difficulty
    c.execute("SELECT difficulty, COUNT(*) FROM topics GROUP BY difficulty")
    stats['by_difficulty'] = dict(c.fetchall())
    
    # Recent study sessions (last 7 days)
    c.execute("""
        SELECT COUNT(*), SUM(duration_minutes) 
        FROM study_sessions 
        WHERE session_date >= datetime('now', '-7 days')
    """)
    result = c.fetchone()
    stats['recent_sessions'] = result[0] or 0
    stats['recent_time'] = result[1] or 0
    
    return stats

def export_data(format: str = "json") -> str:
    """Export all data to JSON or CSV format."""
    topics = get_topics()
    sessions = get_study_sessions(limit=10000)
    
    if format.lower() == "json":
        data = {
            "topics": topics,
            "sessions": sessions,
            "exported_at": datetime.now().isoformat()
        }
        return json.dumps(data, indent=2, default=str)
    else:
        # CSV format
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write topics
        writer.writerow(["Type", "ID", "Topic Name", "Time Spent", "Status", "Difficulty", "Created At"])
        for topic in topics:
            writer.writerow([
                "Topic", topic['id'], topic['topic_name'], topic['time_spent'],
                topic['status'], topic.get('difficulty', ''), topic.get('created_at', '')
            ])
        
        # Write sessions
        writer.writerow([])
        writer.writerow(["Type", "Session ID", "Topic ID", "Duration", "Date", "Notes"])
        for session in sessions:
            writer.writerow([
                "Session", session['id'], session['topic_id'], session['duration_minutes'],
                session['session_date'], session.get('notes', '')
            ])
        
        return output.getvalue()

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from database import get_topics, get_study_sessions, get_statistics
import random
from datetime import datetime, timedelta
import numpy as np
import os

# Set style for better-looking plots
try:
    if 'seaborn-v0_8-darkgrid' in plt.style.available:
        plt.style.use('seaborn-v0_8-darkgrid')
    elif 'seaborn-darkgrid' in plt.style.available:
        plt.style.use('seaborn-darkgrid')
    else:
        plt.style.use('default')
except:
    plt.style.use('default')

def generate_report():
    """Generate comprehensive learning report with multiple visualizations."""
    topics = get_topics()
    
    if not topics:
        return "No topics yet!", None, None, "You haven't added any topics yet. Start by setting a learning goal for today!"

    # Convert to DataFrame with all fields
    df = pd.DataFrame(topics)
    
    # Rename columns for display
    display_columns = {
        'id': 'ID',
        'topic_name': 'Topic',
        'time_spent': 'Time (min)',
        'status': 'Status',
        'difficulty': 'Difficulty',
        'created_at': 'Created',
        'goal_time': 'Goal (min)'
    }
    df_display = df.rename(columns=display_columns)
    
    # Select only columns that exist
    available_cols = [col for col in display_columns.values() if col in df_display.columns]
    df_display = df_display[available_cols]

    # Generate visualizations
    charts = generate_visualizations(df, topics)
    
    # Generate statistics
    stats = get_statistics()
    
    # Generate AI-style personalized feedback
    total_time = df['time_spent'].sum() if 'time_spent' in df.columns else 0
    avg_time = df['time_spent'].mean() if 'time_spent' in df.columns and len(df) > 0 else 0
    completed = len(df[df['status'].str.lower() == 'completed']) if 'status' in df.columns else 0
    in_progress = len(df[df['status'].str.lower() == 'in progress']) if 'status' in df.columns else 0

    feedback = generate_feedback(total_time, avg_time, completed, in_progress, len(df), stats)

    return df_display, charts, stats, feedback

def generate_visualizations(df: pd.DataFrame, topics: list) -> dict:
    """Generate multiple visualizations for learning analytics."""
    charts = {}
    os.makedirs('data', exist_ok=True)
    
    # 1. Bar chart: Time spent per topic
    if 'time_spent' in df.columns and 'topic_name' in df.columns:
        plt.figure(figsize=(10, 6))
        colors = plt.cm.viridis(np.linspace(0, 1, len(df)))
        bars = plt.bar(df['topic_name'], df['time_spent'], color=colors)
        plt.xticks(rotation=45, ha='right')
        plt.ylabel('Time Spent (minutes)')
        plt.title('Learning Time Tracker', fontsize=14, fontweight='bold')
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        plt.savefig('data/time_chart.png', dpi=150, bbox_inches='tight')
        plt.close()
        charts['time_chart'] = 'data/time_chart.png'
    
    # 2. Pie chart: Topics by status
    if 'status' in df.columns and len(df) > 0:
        try:
            plt.figure(figsize=(8, 6))
            status_counts = df['status'].value_counts()
            if len(status_counts) > 0:
                colors_pie = ['#66b3ff', '#99ff99', '#ffcc99', '#ff9999'][:len(status_counts)]
                plt.pie(status_counts.values, labels=status_counts.index, autopct='%1.1f%%', 
                        colors=colors_pie, startangle=90)
                plt.title('Topics by Status', fontsize=14, fontweight='bold')
                plt.tight_layout()
                plt.savefig('data/status_chart.png', dpi=150, bbox_inches='tight')
                plt.close()
                charts['status_chart'] = 'data/status_chart.png'
        except Exception as e:
            print(f"Could not generate status chart: {e}")
    
    # 3. Bar chart: Topics by difficulty
    if 'difficulty' in df.columns and len(df) > 0:
        try:
            plt.figure(figsize=(8, 5))
            difficulty_counts = df['difficulty'].value_counts()
            if len(difficulty_counts) > 0:
                difficulty_order = ['Easy', 'Medium', 'Hard']
                difficulty_counts = difficulty_counts.reindex([d for d in difficulty_order if d in difficulty_counts.index], fill_value=0)
                colors_diff = {'Easy': '#90EE90', 'Medium': '#FFD700', 'Hard': '#FF6347'}
                bar_colors = [colors_diff.get(d, '#808080') for d in difficulty_counts.index]
                plt.bar(difficulty_counts.index, difficulty_counts.values, color=bar_colors)
                plt.ylabel('Number of Topics')
                plt.title('Topics by Difficulty', fontsize=14, fontweight='bold')
                plt.grid(axis='y', alpha=0.3)
                plt.tight_layout()
                plt.savefig('data/difficulty_chart.png', dpi=150, bbox_inches='tight')
                plt.close()
                charts['difficulty_chart'] = 'data/difficulty_chart.png'
        except Exception as e:
            print(f"Could not generate difficulty chart: {e}")
    
    # 4. Progress chart: Goal vs Actual time
    if 'goal_time' in df.columns and 'time_spent' in df.columns:
        df_with_goals = df[df['goal_time'] > 0]
        if not df_with_goals.empty:
            plt.figure(figsize=(10, 6))
            x = range(len(df_with_goals))
            width = 0.35
            plt.bar([i - width/2 for i in x], df_with_goals['goal_time'], width, 
                   label='Goal', color='#FFA500', alpha=0.7)
            plt.bar([i + width/2 for i in x], df_with_goals['time_spent'], width,
                   label='Actual', color='#32CD32', alpha=0.7)
            plt.xlabel('Topics')
            plt.ylabel('Time (minutes)')
            plt.title('Goal vs Actual Study Time', fontsize=14, fontweight='bold')
            plt.xticks(x, df_with_goals['topic_name'], rotation=45, ha='right')
            plt.legend()
            plt.grid(axis='y', alpha=0.3)
            plt.tight_layout()
            plt.savefig('data/progress_chart.png', dpi=150, bbox_inches='tight')
            plt.close()
            charts['progress_chart'] = 'data/progress_chart.png'
    
    # 5. Study sessions timeline (if available)
    try:
        sessions = get_study_sessions(limit=100)
        if sessions:
            sessions_df = pd.DataFrame(sessions)
            if 'session_date' in sessions_df.columns and 'duration_minutes' in sessions_df.columns:
                sessions_df['session_date'] = pd.to_datetime(sessions_df['session_date'])
                sessions_df = sessions_df.sort_values('session_date')
                sessions_df['cumulative_time'] = sessions_df['duration_minutes'].cumsum()
                
                plt.figure(figsize=(12, 6))
                plt.plot(sessions_df['session_date'], sessions_df['cumulative_time'], 
                        marker='o', linewidth=2, markersize=4, color='#4169E1')
                plt.fill_between(sessions_df['session_date'], sessions_df['cumulative_time'], 
                               alpha=0.3, color='#4169E1')
                plt.xlabel('Date')
                plt.ylabel('Cumulative Study Time (minutes)')
                plt.title('Study Progress Over Time', fontsize=14, fontweight='bold')
                plt.grid(True, alpha=0.3)
                plt.xticks(rotation=45)
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                plt.tight_layout()
                plt.savefig('data/timeline_chart.png', dpi=150, bbox_inches='tight')
                plt.close()
                charts['timeline_chart'] = 'data/timeline_chart.png'
    except Exception as e:
        print(f"Could not generate timeline chart: {e}")
    
    return charts


def generate_feedback(total_time, avg_time, completed, in_progress, total_topics, stats=None):
    """Generate enhanced personalized AI-style feedback message based on user learning patterns."""
    
    if total_topics == 0:
        return "No learning data found. Start your first topic and I'll guide you along the way!"

    # Enhanced personalized feedback logic
    if total_time < 60:
        base_feedback = "It seems you're just getting started on your learning journey — that's great! 🌱"
    elif total_time < 200:
        base_feedback = "You've started building momentum. Try maintaining a steady pace every day! 📈"
    elif total_time < 500:
        base_feedback = "Impressive dedication! You've invested significant time — consistency is paying off. 💪"
    else:
        base_feedback = "Outstanding commitment! You're building a strong foundation of knowledge. 🏆"

    # Completion ratio feedback
    completion_rate = (completed / total_topics * 100) if total_topics > 0 else 0
    if completed == 0:
        progress_feedback = "You haven't completed any topics yet. Finishing one can give a big confidence boost! 🎯"
    elif completion_rate < 30:
        progress_feedback = f"Nice start! You've completed {completed} out of {total_topics} topics ({completion_rate:.1f}%) — keep pushing forward! 🚀"
    elif completion_rate < 70:
        progress_feedback = f"Great progress! You've completed {completed} out of {total_topics} topics ({completion_rate:.1f}%) — you're on track! 📊"
    else:
        progress_feedback = f"Excellent work! You've completed {completed} out of {total_topics} topics ({completion_rate:.1f}%) — you're nearing mastery! 🌟"

    # Learning speed and style
    if avg_time == 0:
        pace_feedback = "Start tracking your study time to get personalized insights! ⏱️"
    elif avg_time < 20:
        pace_feedback = "You seem to prefer quick learning bursts — try revisiting key concepts to reinforce memory. 🔄"
    elif avg_time < 50:
        pace_feedback = "Your learning pace looks balanced — just right for long-term retention. ⚖️"
    else:
        pace_feedback = "You spend deep focus time per topic — amazing discipline! Don't forget short reviews. 🧘"

    # Study streak analysis
    streak_info = ""
    if stats and 'recent_sessions' in stats:
        recent_sessions = stats.get('recent_sessions', 0)
        recent_time = stats.get('recent_time', 0)
        if recent_sessions > 0:
            avg_session_time = recent_time / recent_sessions if recent_sessions > 0 else 0
            streak_info = f"\n📅 **Recent Activity (Last 7 Days):**\n"
            streak_info += f"   • Study Sessions: {recent_sessions}\n"
            streak_info += f"   • Time Spent: {recent_time} minutes\n"
            streak_info += f"   • Avg Session: {avg_session_time:.1f} minutes\n"
            
            if recent_sessions >= 5:
                streak_info += "   🎉 You're maintaining a great study streak! Keep it up!\n"
            elif recent_sessions >= 3:
                streak_info += "   👍 Good consistency! Try to study a bit more frequently.\n"
            else:
                streak_info += "   💡 Consider studying more regularly for better retention.\n"

    # Difficulty distribution
    difficulty_info = ""
    if stats and 'by_difficulty' in stats:
        diff_stats = stats['by_difficulty']
        if diff_stats:
            difficulty_info = f"\n📊 **Difficulty Distribution:**\n"
            for diff, count in diff_stats.items():
                difficulty_info += f"   • {diff}: {count} topics\n"

    # Goal progress
    goal_info = ""
    if stats:
        # Calculate goal completion if we have goal data
        goal_info = "\n🎯 **Study Goals:**\n"
        goal_info += "   Set specific time goals for topics to track your progress better!\n"

    # Small motivational twist
    motivational_quotes = [
        "Remember, progress is progress — no matter how small. 🌱",
        "Consistency beats intensity — a little every day goes a long way. 📅",
        "You're not just learning, you're evolving. Keep going! 🚀",
        "Every topic mastered adds to your future strength — stay curious! 💡",
        "The expert in anything was once a beginner. Keep pushing! 💪",
        "Learning is a journey, not a destination. Enjoy the process! 🎓"
    ]

    return f"""
💡 **Personalized Learning Insights**
─────────────────────────────────────
📚 **Overview:**
   • Total Topics: {total_topics}
   • ✅ Completed: {completed} ({completion_rate:.1f}%)
   • 🔄 In Progress: {in_progress}
   • 🕒 Total Time Spent: {total_time} minutes ({total_time/60:.1f} hours)
   • ⚙️ Average Time per Topic: {avg_time:.1f} minutes

🧠 **Feedback:**
{base_feedback}
{progress_feedback}
{pace_feedback}
{streak_info}{difficulty_info}{goal_info}
✨ **Motivation:** {random.choice(motivational_quotes)}
"""


# You can test this locally by running:
# df, chart, feedback = generate_report()
# print(feedback)

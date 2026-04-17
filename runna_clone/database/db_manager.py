import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), 'runna_clone.db')

def get_connection():
    """Returns a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)

@contextmanager
def get_db():
    """Context manager for database connections.
    Auto-commits on success, rolls back on error, always closes."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Initializes the database schema."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                current_5k_time_sec INTEGER,
                current_10k_time_sec INTEGER,
                goal_distance_km REAL,
                goal_time_sec INTEGER,
                race_date TEXT,
                available_days TEXT,
                vdot REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create training_plans table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS training_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                start_date TEXT,
                end_date TEXT,
                total_weeks INTEGER,
                plan_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Create workouts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER,
                week_number INTEGER,
                day_of_week INTEGER,
                workout_date TEXT,
                workout_type TEXT,
                title TEXT,
                description TEXT,
                target_distance_km REAL,
                target_pace_sec_per_km INTEGER,
                status TEXT DEFAULT 'pending',
                completed_at TIMESTAMP,
                FOREIGN KEY (plan_id) REFERENCES training_plans (id)
            )
        ''')

        # Create gamification table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gamification (
                user_id INTEGER PRIMARY KEY,
                current_streak INTEGER DEFAULT 0,
                longest_streak INTEGER DEFAULT 0,
                total_workouts_completed INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

if __name__ == "__main__":
    init_db()
    print("Database initialized at:", DB_PATH)

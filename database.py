import sqlite3
import json
from datetime import datetime
from config import Config

def get_connection():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # User account sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT,
                session_string TEXT UNIQUE NOT NULL,
                label TEXT,
                is_active INTEGER DEFAULT 1,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Report logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS report_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT NOT NULL,
                report_type TEXT NOT NULL,
                reason TEXT NOT NULL,
                total_accounts INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()

def add_session(session_string, label=None, phone=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO user_sessions (session_string, label, phone, is_active)
                VALUES (?, ?, ?, 1)
            ''', (session_string.strip(), label or "Session", phone))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

def get_active_sessions():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM user_sessions WHERE is_active = 1 ORDER BY id DESC')
        return [dict(row) for row in cursor.fetchall()]

def get_all_sessions():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM user_sessions ORDER BY id DESC')
        return [dict(row) for row in cursor.fetchall()]

def delete_session(session_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM user_sessions WHERE id = ?', (session_id,))
        conn.commit()
        return cursor.rowcount > 0

def toggle_session_status(session_id, is_active):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE user_sessions SET is_active = ? WHERE id = ?', (1 if is_active else 0, session_id))
        conn.commit()
        return cursor.rowcount > 0

def log_report(target, report_type, reason, total_accounts, success_count, fail_count, details=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO report_logs (target, report_type, reason, total_accounts, success_count, fail_count, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            target,
            report_type,
            reason,
            total_accounts,
            success_count,
            fail_count,
            json.dumps(details) if details else None
        ))
        conn.commit()
        return cursor.lastrowid

def get_report_history(limit=20):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM report_logs ORDER BY created_at DESC LIMIT ?', (limit,))
        return [dict(row) for row in cursor.fetchall()]

def get_stats():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM user_sessions WHERE is_active = 1')
        active_sessions = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM user_sessions')
        total_sessions = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*), SUM(success_count) FROM report_logs')
        row = cursor.fetchone()
        total_reports = row[0] or 0
        total_successes = row[1] or 0
        
        return {
            'active_sessions': active_sessions,
            'total_sessions': total_sessions,
            'total_reports': total_reports,
            'total_successes': total_successes
        }

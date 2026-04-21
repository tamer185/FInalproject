from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
import secrets
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Allow requests from your Vercel frontend
CORS(app, resources={r"/api/*": {"origins": [
    "https://fypme.vercel.app",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5000",
    "http://127.0.0.1:5000"
]}})

DB_PATH = os.environ.get('DB_PATH', 'sports.db')

# ================================================================
# DATABASE SETUP
# ================================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        registration_id TEXT UNIQUE NOT NULL,
        event_id INTEGER NOT NULL,
        event_title TEXT,
        user_name TEXT NOT NULL,
        user_email TEXT NOT NULL,
        registration_date TEXT,
        status TEXT DEFAULT 'pending',
        approved_date TEXT,
        rejected_date TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT NOT NULL,
        event_id INTEGER NOT NULL,
        registration_id TEXT,
        status TEXT NOT NULL,
        notification_date TEXT,
        is_read INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()

init_db()

# ================================================================
# HOME
# ================================================================
@app.route('/', methods=['GET'])
def home():
    return jsonify({'message': 'Sports Events API is running!', 'status': 'online'})

# ================================================================
# CREATE REGISTRATION  (called from index.html when user registers)
# ================================================================
@app.route('/api/registrations', methods=['POST'])
def create_registration():
    data = request.json or {}
    reg_id       = data.get('registrationId', '')
    event_id     = data.get('eventId')
    event_title  = data.get('eventTitle', '')
    user_name    = data.get('userName', '')
    user_email   = data.get('userEmail', '')
    reg_date     = data.get('registrationDate', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    if not all([reg_id, event_id, user_name, user_email]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    conn = get_db()
    try:
        conn.execute(
            '''INSERT OR REPLACE INTO registrations
               (registration_id, event_id, event_title, user_name, user_email, registration_date, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')''',
            (reg_id, event_id, event_title, user_name, user_email, reg_date)
        )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

# ================================================================
# CANCEL REGISTRATION  (called from index.html when user cancels)
# ================================================================
@app.route('/api/registrations/<registration_id>/cancel', methods=['PUT'])
def cancel_registration(registration_id):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE registrations SET status='cancelled' WHERE registration_id=?",
            (registration_id,)
        )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

# ================================================================
# GET PENDING REGISTRATIONS  (for admin panel)
# ================================================================
@app.route('/api/registrations/pending', methods=['GET'])
def get_pending():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM registrations WHERE status='pending' ORDER BY created_at ASC"
    ).fetchall()
    conn.close()
    return jsonify({'success': True, 'pending': [dict(r) for r in rows]})

# ================================================================
# GET ALL REGISTRATIONS  (for admin panel)
# ================================================================
@app.route('/api/registrations/all', methods=['GET'])
def get_all():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM registrations ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify({'success': True, 'registrations': [dict(r) for r in rows]})

# ================================================================
# APPROVE REGISTRATION
# ================================================================
@app.route('/api/registrations/<registration_id>/approve', methods=['PUT'])
def approve_registration(registration_id):
    conn = get_db()
    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(
            "UPDATE registrations SET status='approved', approved_date=? WHERE registration_id=?",
            (now, registration_id)
        )
        reg = conn.execute(
            "SELECT * FROM registrations WHERE registration_id=?", (registration_id,)
        ).fetchone()
        if reg:
            conn.execute(
                "INSERT INTO notifications (user_email, event_id, registration_id, status, notification_date) VALUES (?,?,?,?,?)",
                (reg['user_email'], reg['event_id'], registration_id, 'approved', now)
            )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

# ================================================================
# REJECT REGISTRATION
# ================================================================
@app.route('/api/registrations/<registration_id>/reject', methods=['PUT'])
def reject_registration(registration_id):
    conn = get_db()
    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(
            "UPDATE registrations SET status='rejected', rejected_date=? WHERE registration_id=?",
            (now, registration_id)
        )
        reg = conn.execute(
            "SELECT * FROM registrations WHERE registration_id=?", (registration_id,)
        ).fetchone()
        if reg:
            conn.execute(
                "INSERT INTO notifications (user_email, event_id, registration_id, status, notification_date) VALUES (?,?,?,?,?)",
                (reg['user_email'], reg['event_id'], registration_id, 'rejected', now)
            )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

# ================================================================
# STATS  (for admin dashboard)
# ================================================================
@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = get_db()
    pending  = conn.execute("SELECT COUNT(*) FROM registrations WHERE status='pending'").fetchone()[0]
    approved = conn.execute("SELECT COUNT(*) FROM registrations WHERE status='approved'").fetchone()[0]
    rejected = conn.execute("SELECT COUNT(*) FROM registrations WHERE status='rejected'").fetchone()[0]
    total    = conn.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
    conn.close()
    return jsonify({
        'success': True,
        'stats': {
            'pending': pending, 'approved': approved,
            'rejected': rejected, 'total': total
        }
    })

# ================================================================
# GET NOTIFICATIONS FOR A USER  (called from index.html)
# ================================================================
@app.route('/api/notifications/<user_email>', methods=['GET'])
def get_notifications(user_email):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_email=? AND is_read=0 ORDER BY id DESC",
        (user_email,)
    ).fetchall()
    conn.close()
    return jsonify({'success': True, 'notifications': [dict(r) for r in rows]})

# ================================================================
# MARK NOTIFICATIONS AS READ
# ================================================================
@app.route('/api/notifications/<user_email>/read', methods=['POST'])
def mark_notifications_read(user_email):
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read=1 WHERE user_email=?", (user_email,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ================================================================
# RUN
# ================================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

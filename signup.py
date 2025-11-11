#!/usr/bin/env python3
"""
PyroSense Signup Page - Python Flask Application
Simple signup UI matching the login styling. Inserts hashed password into Users.
"""
from flask import Flask, render_template_string, request, redirect, url_for
import os
import sqlite3
from werkzeug.security import generate_password_hash
import sys
import traceback

app = Flask(__name__)
app.secret_key = os.environ.get('PYROSENSE_SECRET', 'pyrosense_shared_secret_key')

DB_PATH = os.path.join(os.path.dirname(__file__), 'pyrosense_db.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Signup template - keeps the same look as the login page (trimmed for brevity)
SIGNUP_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PyroSense - Sign Up</title>
    <link rel="stylesheet" href="/static/css/signup.css">
</head>
<body>
    <div class="login-container">
        <h1 class="brand-header">PyroSense</h1>
        <p class="subtitle">Create an account</p>
        {% if error %}<div class="flash-message">{{ error }}</div>{% endif %}
        {% if success %}<div class="success-message">{{ success }}</div>{% endif %}
        <form method="post">
            <label for="username">Username</label>
            <input id="username" name="username" type="text" required>
            <label for="email">Email</label>
            <input id="email" name="email" type="email" required>
            <label for="password">Password</label>
            <input id="password" name="password" type="password" required>
            <label for="password2">Confirm Password</label>
            <input id="password2" name="password2" type="password" required>
            <button class="login-button" type="submit">Sign Up</button>
        </form>
        <div class="small-link"><a href="/login">← Back to Sign In</a></div>
    </div>
</body>
</html>
"""

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    success = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        if not username or not email or not password:
            error = "Please fill all required fields."
            return render_template_string(SIGNUP_TEMPLATE, error=error)
        if password != password2:
            error = "Passwords do not match."
            return render_template_string(SIGNUP_TEMPLATE, error=error)
        if len(password) < 6:
            error = "Password must be at least 6 characters."
            return render_template_string(SIGNUP_TEMPLATE, error=error)
        try:
            conn = get_db_connection()
            c = conn.cursor()
            hashed = generate_password_hash(password)
            c.execute("INSERT INTO Users (Username, Password, Email) VALUES (?, ?, ?)",
                      (username, hashed, email))
            conn.commit()
            conn.close()
            success = "Account created. Please sign in."
            return redirect(url_for('login', success=success))
        except sqlite3.IntegrityError as e:
            # username or email collision
            msg = str(e).lower()
            if 'username' in msg:
                error = "Username already exists."
            elif 'email' in msg:
                error = "Email already registered."
            else:
                error = "An account with that information already exists."
            return render_template_string(SIGNUP_TEMPLATE, error=error)
        except Exception as e:
            print("Signup error:", e, file=sys.stderr)
            traceback.print_exc()
            error = "Internal error. Contact admin."
            return render_template_string(SIGNUP_TEMPLATE, error=error)

    return render_template_string(SIGNUP_TEMPLATE, error=error, success=success)

if __name__ == '__main__':
    # ensure DB tables exist (init_db from login.py could be reused; minimal safeguard here)
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS Users (
            UserID INTEGER PRIMARY KEY AUTOINCREMENT,
            Username TEXT UNIQUE NOT NULL,
            Password TEXT NOT NULL,
            Email TEXT UNIQUE
        )""")
        conn.commit()
        conn.close()
    except Exception as e:
        print("DB init failed in signup.py:", e, file=sys.stderr)
    app.run(host='127.0.0.1', port=5001, debug=True)

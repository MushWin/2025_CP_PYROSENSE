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
import re
import traceback

app = Flask(__name__)
app.secret_key = os.environ.get('PYROSENSE_SECRET', 'pyrosense_shared_secret_key')

DB_PATH = os.path.join(os.path.dirname(__file__), 'pyrosense_db.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Signup template
SIGNUP_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PyroSense - Sign Up</title>
    <link rel="stylesheet" href="/static/css/login.css">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <style>
        .signup-card {
            background: rgba(255,255,255,0.97);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px 44px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.12);
            width: 100%;
            max-width: 780px;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 1;
        }
        .signup-card .brand-header { font-size: 2.2rem; color: #7C0000; font-weight: 700; margin-bottom: 4px; letter-spacing: -1px; }
        .signup-card .subtitle { color: #3E0000; margin-bottom: 28px; font-size: 15px; }
        .signup-grid {
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            gap: 0;
        }
        .signup-grid .form-col { display: flex; flex-direction: column; }
        .signup-grid label {
            display: block;
            margin-bottom: 6px;
            font-weight: 600;
            color: #7C0000;
            font-size: 14px;
        }
        .signup-grid input {
            width: 100%;
            padding: 11px 14px;
            border-radius: 10px;
            border: 2px solid #e2e8f0;
            background: white;
            font-size: 15px;
            transition: all 0.2s ease;
            margin-bottom: 16px;
            box-sizing: border-box;
        }
        .signup-grid input:focus {
            outline: none;
            border-color: #7C0000;
            box-shadow: 0 0 0 3px rgba(124,0,0,0.1);
        }
        .divider {
            width: 1px;
            background: #f0e4e4;
            margin: 0 14px;
            border-radius: 999px;
            align-self: stretch;
        }
        .signup-footer { margin-top: 6px; display: flex; flex-direction: column; gap: 14px; }
        .signup-btn {
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 12px;
            background: linear-gradient(135deg, #7C0000 0%, #3E0000 50%, #2b2b2b 100%);
            color: white;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-shadow: 0 1px 2px rgba(0,0,0,0.2);
        }
        .signup-btn:hover { transform: translateY(-2px); box-shadow: 0 10px 25px rgba(124,0,0,0.35); }
        .signup-back { text-align: center; font-size: 14px; color: #718096; }
        .signup-back a { color: #7C0000; text-decoration: none; font-weight: 600; }
        .signup-back a:hover { text-decoration: underline; }
        .pw-rules { list-style: none; padding: 0; margin: -6px 0 14px; font-size: 12px; color: #a0aec0; }
        .pw-rules li { padding: 2px 0 2px 18px; position: relative; }
        .pw-rules li::before { content: '✗'; position: absolute; left: 0; color: #e53e3e; font-size: 11px; }
        .pw-rules li.valid::before { content: '✓'; color: #38a169; }
        .pw-rules li.valid { color: #38a169; }
        .pw-match-hint { font-size: 12px; margin: -6px 0 14px; min-height: 18px; }
        .pw-match-hint.match { color: #38a169; }
        .pw-match-hint.no-match { color: #e53e3e; }
        @media (max-width: 640px) {
            .signup-card { padding: 30px 20px; max-width: calc(100% - 32px); position: relative; top: auto; left: auto; transform: none; margin: 24px auto; }
            .signup-grid { grid-template-columns: 1fr; }
            .divider { display: none; }
        }
    </style>
</head>
<body>
    <div class="signup-card">
        <h1 class="brand-header">PyroSense</h1>
        <p class="subtitle">Create an account</p>

        {% if error %}<div class="flash-message">{{ error }}</div>{% endif %}
        {% if success %}<div class="success-message">{{ success }}</div>{% endif %}

        <form method="post" autocomplete="off" id="signupForm">
            <div class="signup-grid">
                <!-- Left column -->
                <div class="form-col">
                    <label for="full_name">Full Name</label>
                    <input id="full_name" name="full_name" type="text" required placeholder="e.g. Juan Dela Cruz" autofocus>

                    <label for="username">Username</label>
                    <input id="username" name="username" type="text" required placeholder="Choose a username">

                    <label for="phone">Phone Number</label>
                    <input id="phone" name="phone" type="tel" placeholder="Type 9 for PH number">
                </div>

                <div class="divider"></div>

                <!-- Right column -->
                <div class="form-col">
                    <label for="email">Email</label>
                    <input id="email" name="email" type="email" required placeholder="your@email.com">

                    <label for="password">Password</label>
                    <input id="password" name="password" type="password" required placeholder="Min. 8 characters" autocomplete="new-password">
                    <ul class="pw-rules" id="pwRules">
                        <li id="r-len">At least 8 characters</li>
                        <li id="r-upper">One uppercase letter (A–Z)</li>
                        <li id="r-num">One number (0–9)</li>
                        <li id="r-special">One special character (@$!%*?&#)</li>
                    </ul>

                    <label for="password2">Confirm Password</label>
                    <input id="password2" name="password2" type="password" required placeholder="Repeat your password" autocomplete="new-password">
                    <p class="pw-match-hint" id="pwMatchHint"></p>
                </div>
            </div>

            <div class="signup-footer">
                <button class="signup-btn" type="submit">Create Account</button>
                <div class="signup-back"><a href="/login">← Back to Sign In</a></div>
            </div>
        </form>
    </div>

    <script>
        // Phone auto-formatting for Philippine numbers (+63)
        document.getElementById('phone').addEventListener('input', function () {
            let digits = this.value.replace(/\D/g, '');
            if (!digits) { this.value = ''; return; }
            if (digits.startsWith('9')) digits = '63' + digits;
            if (digits.startsWith('63')) {
                let local = digits.slice(2, 12);
                let fmt = '+63';
                if (local.length > 0) fmt += ' ' + local.slice(0, 4);
                if (local.length > 4) fmt += ' ' + local.slice(4, 7);
                if (local.length > 7) fmt += ' ' + local.slice(7, 10);
                this.value = fmt;
            }
        });

        // Password strength rules
        const pwInput = document.getElementById('password');
        const pw2Input = document.getElementById('password2');
        const pwMatchHint = document.getElementById('pwMatchHint');
        const rules = {
            'r-len':     v => v.length >= 8,
            'r-upper':   v => /[A-Z]/.test(v),
            'r-num':     v => /[0-9]/.test(v),
            'r-special': v => /[@$!%*?&#]/.test(v)
        };

        pwInput.addEventListener('input', function () {
            for (const [id, fn] of Object.entries(rules))
                document.getElementById(id).classList.toggle('valid', fn(this.value));
            checkMatch();
        });

        function checkMatch() {
            if (!pw2Input.value) { pwMatchHint.textContent = ''; pwMatchHint.className = 'pw-match-hint'; return; }
            const ok = pw2Input.value === pwInput.value;
            pwMatchHint.textContent = ok ? 'Passwords match ✓' : 'Passwords do not match';
            pwMatchHint.className = 'pw-match-hint ' + (ok ? 'match' : 'no-match');
        }
        pw2Input.addEventListener('input', checkMatch);

        // Pre-submit validation
        document.getElementById('signupForm').addEventListener('submit', function (e) {
            const pw = pwInput.value;
            const allRulesPass = Object.values(rules).every(fn => fn(pw));
            if (!allRulesPass) {
                e.preventDefault();
                Swal.fire({
                    icon: 'error', title: 'Weak Password',
                    text: 'Password must be at least 8 characters and include an uppercase letter, a number, and a special character (@$!%*?&#).',
                    confirmButtonText: 'OK', buttonsStyling: false,
                    didOpen: () => { const b = document.querySelector('.swal2-confirm'); b.style.cssText = 'background:linear-gradient(135deg,#7C0000,#3E0000,#2b2b2b);color:white;border:none;border-radius:12px;padding:12px 30px;font-weight:600;cursor:pointer;'; }
                });
                return;
            }
            if (pw2Input.value !== pw) {
                e.preventDefault();
                Swal.fire({
                    icon: 'error', title: 'Passwords Do Not Match',
                    text: 'Please make sure both passwords are the same.',
                    confirmButtonText: 'OK', buttonsStyling: false,
                    didOpen: () => { const b = document.querySelector('.swal2-confirm'); b.style.cssText = 'background:linear-gradient(135deg,#7C0000,#3E0000,#2b2b2b);color:white;border:none;border-radius:12px;padding:12px 30px;font-weight:600;cursor:pointer;'; }
                });
            }
        });
    </script>

    {% if success %}
    <script>
        document.addEventListener('DOMContentLoaded', function () {
            Swal.fire({
                icon: 'success',
                title: 'Account Created!',
                text: '{{ success }}',
                confirmButtonText: 'Go to Sign In',
                background: '#ffffff',
                customClass: { popup: 'swal2-border-radius' },
                buttonsStyling: false,
                didOpen: () => {
                    const btn = document.querySelector('.swal2-confirm');
                    btn.style.background = 'linear-gradient(135deg, #7C0000 0%, #3E0000 50%, #2b2b2b 100%)';
                    btn.style.color = 'white';
                    btn.style.border = 'none';
                    btn.style.borderRadius = '12px';
                    btn.style.padding = '12px 30px';
                    btn.style.fontWeight = '600';
                }
            }).then(function () {
                window.location.href = '/login';
            });
        });
    </script>
    {% endif %}
</body>
</html>
"""

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    success = None
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username  = request.form.get('username', '').strip()
        phone     = request.form.get('phone', '').strip()
        email     = request.form.get('email', '').strip()
        password  = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        # Role is always 'user' from public signup
        role = 'user'

        if not full_name or not username or not email or not password:
            error = "Please fill all required fields."
            return render_template_string(SIGNUP_TEMPLATE, error=error, success=None)
        if password != password2:
            error = "Passwords do not match."
            return render_template_string(SIGNUP_TEMPLATE, error=error, success=None)
        if len(password) < 8:
            error = "Password must be at least 8 characters."
            return render_template_string(SIGNUP_TEMPLATE, error=error, success=None)
        if not re.search(r'[A-Z]', password):
            error = "Password must contain at least one uppercase letter."
            return render_template_string(SIGNUP_TEMPLATE, error=error, success=None)
        if not re.search(r'[0-9]', password):
            error = "Password must contain at least one number."
            return render_template_string(SIGNUP_TEMPLATE, error=error, success=None)
        if not re.search(r'[@$!%*?&#]', password):
            error = "Password must contain at least one special character (@$!%*?&#)."
            return render_template_string(SIGNUP_TEMPLATE, error=error, success=None)
        try:
            conn = get_db_connection()
            c = conn.cursor()
            hashed = generate_password_hash(password)
            c.execute(
                "INSERT INTO Users (Username, Password, Email, UserRole, FullName, PhoneNumber) VALUES (?, ?, ?, ?, ?, ?)",
                (username, hashed, email or None, role, full_name, phone)
            )
            conn.commit()
            conn.close()
            success = "Your account was created successfully. Please sign in."
            return render_template_string(SIGNUP_TEMPLATE, error=None, success=success)
        except sqlite3.IntegrityError as e:
            msg = str(e).lower()
            if 'username' in msg:
                error = "Username already exists."
            elif 'email' in msg:
                error = "Email already registered."
            else:
                error = "An account with that information already exists."
            return render_template_string(SIGNUP_TEMPLATE, error=error, success=None)
        except Exception as e:
            print("Signup error:", e, file=sys.stderr)
            traceback.print_exc()
            error = f"Database error: {e}. Please restart the server and try again."
            return render_template_string(SIGNUP_TEMPLATE, error=error, success=None)
    return render_template_string(SIGNUP_TEMPLATE, error=error, success=success)

if __name__ == '__main__':
    # ensure DB tables exist with all required columns
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS Users (
            UserID INTEGER PRIMARY KEY AUTOINCREMENT,
            Username TEXT UNIQUE NOT NULL,
            Password TEXT NOT NULL,
            Email TEXT UNIQUE,
            UserRole TEXT DEFAULT 'user',
            FullName TEXT DEFAULT '',
            PhoneNumber TEXT DEFAULT ''
        )""")
        existing_cols = [row[1] for row in c.execute("PRAGMA table_info(Users)").fetchall()]
        for col, definition in [
            ('Email',       'TEXT'),
            ('UserRole',    "TEXT DEFAULT 'user'"),
            ('FullName',    "TEXT DEFAULT ''"),
            ('PhoneNumber', "TEXT DEFAULT ''"),
        ]:
            if col not in existing_cols:
                c.execute(f"ALTER TABLE Users ADD COLUMN {col} {definition}")
                print(f"DB migration: added column '{col}' to Users table", file=sys.stderr)
        conn.commit()
        conn.close()
    except Exception as e:
        print("DB init failed in signup.py:", e, file=sys.stderr)
    app.run(host='127.0.0.1', port=5001, debug=True)

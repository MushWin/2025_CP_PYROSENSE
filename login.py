#!/usr/bin/env python3
"""
PyroSense Login Page - Python Flask Application
Handles user authentication for the PyroSense web application, including login, password reset, and session management.
"""

from flask import Flask, render_template_string, request, redirect, session, url_for, send_from_directory
import os
import smtplib
import ssl
import sqlite3
from email.message import EmailMessage
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import sys
import re
import traceback
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get('PYROSENSE_SECRET', 'pyrosense_shared_secret_key')  # Use env var if available

# Admin credentials - UI only, not actually used for verification
ADMIN_USERNAME = "admin"

# Admin / dashboard base URLs (env can override). Redirect will prefer the host used to reach the login page
ADMIN_BASE = os.environ.get('PYROSENSE_ADMIN_BASE', None)
DASHBOARD_BASE = os.environ.get('PYROSENSE_DASHBOARD_BASE', None)
app.config['SESSION_COOKIE_SAMESITE'] = os.environ.get('PYROSENSE_SESSION_SAMESITE', 'Lax')

# SMTP configuration for password reset emails
# Credentials from the PyroSense detection system
_SMTP_USER_DEFAULT = 'pyrosense260@gmail.com'
_SMTP_PASS_DEFAULT = 'tejoeivuecxcgxhf'
# ─────────────────────────────────────────────────────────────────────────────
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT   = int(os.environ.get('SMTP_PORT', '465'))   # SSL port, matches pi_main_detection
SMTP_USER   = os.environ.get('SMTP_USER', _SMTP_USER_DEFAULT)
SMTP_PASS   = os.environ.get('SMTP_PASS', _SMTP_PASS_DEFAULT)

# Camera control endpoint
CAMERA_CONTROL_URL = os.environ.get('CAMERA_CONTROL_URL', '')

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), 'pyrosense_db.db')

# Login template with external CSS
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PyroSense - Login</title>
    <link rel="stylesheet" href="/static/css/login.css">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
</head>
<body>
    <div class="login-container">
        <h1 class="brand-header">PyroSense</h1>
        <p class="subtitle">Sign in to your account</p>
        <form method="post" action="/login">
            <label for="username">Username</label>
            <input type="text" id="username" name="username" required autofocus>
            <label for="password">Password</label>
            <div style="position:relative;margin-bottom:18px;">
                <input type="password" id="password" name="password" required style="padding-right:44px;width:100%;box-sizing:border-box;margin-bottom:0;">
                <button type="button" onclick="togglePw('password','eyeLogin')" tabindex="-1" style="position:absolute;right:12px;top:0;bottom:0;margin:auto;height:20px;display:flex;align-items:center;background:none;border:none;cursor:pointer;padding:0;color:#7C0000;">
                    <svg id="eyeLogin" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                </button>
            </div>
            <button class="login-button" type="submit">Sign In</button>
        </form>
        <div class="small-link">
            <a href="/forgot-password">Forgot password?</a> | <a href="/signup">Create account</a>
        </div>
    </div>

    {% if error %}
    <script>
        Swal.fire({
            icon: 'error',
            title: 'Login Failed',
            text: '{{ error }}',
            confirmButtonText: 'Try Again',
            background: '#ffffff',
            backdrop: 'rgba(0, 0, 0, 0.6)',
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
                btn.style.cursor = 'pointer';
                btn.style.transition = 'all 0.3s ease';
            }
        });
    </script>
    {% endif %}

    {% if success %}
    <script>
        const successText = {{ success|tojson }};
        const isAccountCreated = successText.toLowerCase().includes('account created');
        Swal.fire({
            icon: 'success',
            iconColor: '#7C0000',
            title: isAccountCreated ? 'Account Created!' : 'Success',
            text: successText,
            confirmButtonText: 'Continue',
            background: '#ffffff',
            backdrop: 'rgba(0, 0, 0, 0.6)',
            customClass: { popup: 'swal2-border-radius' },
            buttonsStyling: false,
            timer: 3000,
            timerProgressBar: true,
            didOpen: () => {
                const btn = document.querySelector('.swal2-confirm');
                btn.style.background = 'linear-gradient(135deg, #7C0000 0%, #3E0000 50%, #2b2b2b 100%)';
                btn.style.color = 'white';
                btn.style.border = 'none';
                btn.style.borderRadius = '12px';
                btn.style.padding = '12px 30px';
                btn.style.fontWeight = '600';
                btn.style.cursor = 'pointer';
                btn.style.transition = 'all 0.3s ease';
            }
        });
    </script>
    {% endif %}
    <script>
        function togglePw(inputId, iconId) {
            const inp = document.getElementById(inputId);
            const ico = document.getElementById(iconId);
            if (inp.type === 'password') {
                inp.type = 'text';
                ico.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/>';
            } else {
                inp.type = 'password';
                ico.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
            }
        }
    </script>
</body>
</html>
"""

# Forgot password template with external CSS
FORGOT_PASSWORD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PyroSense - Forgot Password</title>
    <link rel="stylesheet" href="/static/css/login.css">
</head>
<body>
    <div class="login-container">
        <h1 class="brand-header">PyroSense</h1>
        <p class="subtitle">Reset your password</p>
        {% if error %}
        <div class="flash-message">{{ error }}</div>
        {% endif %}
        {% if not_found %}
        <div class="flash-message">Email not found in our records. <a href="/signup" style="color:#7C0000;font-weight:700;">Create an account?</a></div>
        {% endif %}
        {% if success %}
        <div class="success-message">{{ success }}</div>
        {% endif %}
        {% if reset_link %}
        <div class="success-message" style="word-break:break-all;">
            Email service is not configured. Copy this reset link and open it in your browser:<br><br>
            <a href="{{ reset_link }}" style="color:#7C0000;font-weight:700;font-size:13px;">{{ reset_link }}</a>
        </div>
        {% endif %}
        <form method="post">
            <label for="email">Email</label>
            <input type="email" id="email" name="email" required>
            <button class="login-button" type="submit">Send Reset Link</button>
        </form>
        <div class="small-link">
            <a href="/login">← Back to Sign In</a>
        </div>
    </div>
</body>
</html>
"""

# Helper function to get database connection
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Helper function to initialize database
def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    # Create Users table with all columns
    c.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            UserID INTEGER PRIMARY KEY AUTOINCREMENT,
            Username TEXT UNIQUE NOT NULL,
            Password TEXT NOT NULL,
            Email TEXT UNIQUE,
            UserRole TEXT DEFAULT 'user',
            FullName TEXT DEFAULT '',
            PhoneNumber TEXT DEFAULT ''
        )
    """)

    # Migrate existing DB: add any missing columns to Users table
    existing_cols = [row[1] for row in c.execute("PRAGMA table_info(Users)").fetchall()]
    migrations = [
        ('Email',       'TEXT'),                  # UNIQUE enforced on new tables; ALTER TABLE can't add UNIQUE in SQLite
        ('UserRole',    "TEXT DEFAULT 'user'"),
        ('FullName',    "TEXT DEFAULT ''"),
        ('PhoneNumber', "TEXT DEFAULT ''"),
    ]
    for col, definition in migrations:
        if col not in existing_cols:
            c.execute(f"ALTER TABLE Users ADD COLUMN {col} {definition}")
            print(f"DB migration: added column '{col}' to Users table", file=sys.stderr)

    # Create PasswordResets table
    c.execute("""
        CREATE TABLE IF NOT EXISTS PasswordResets (
            Token TEXT PRIMARY KEY,
            UserID INTEGER NOT NULL,
            ExpiresAt TEXT NOT NULL,
            FOREIGN KEY (UserID) REFERENCES Users(UserID)
        )
    """)

    # Seed default admin user if no admin exists
    c.execute("SELECT UserID FROM Users WHERE UserRole = 'admin' LIMIT 1")
    if not c.fetchone():
        c.execute(
            "INSERT OR IGNORE INTO Users (Username, Password, Email, UserRole, FullName, PhoneNumber) VALUES (?, ?, ?, ?, ?, ?)",
            ('admin', generate_password_hash('dwin111'), 'admin@pyrosense.local', 'admin', 'System Administrator', '')
        )

    conn.commit()
    conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = request.args.get('error')
    success = request.args.get('success')
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            error = "Please provide both username and password."
            return render_template_string(LOGIN_TEMPLATE, error=error, success=None)

        user = None
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT UserID, Username, Password, Email, UserRole FROM Users WHERE Username = ?", (username,))
            user = c.fetchone()
        except Exception as e:
            print("Database error on login lookup:", e, file=sys.stderr)
            traceback.print_exc()
            error = "Internal server error. Check server logs."
            if conn:
                conn.close()
            return render_template_string(LOGIN_TEMPLATE, error=error, success=None)

        authenticated = False
        # If user found, check password. Support hashed and plain-text legacy entries.
        if user:
            stored_pw = user['Password'] or ""
            try:
                # Try secure hash check first
                if check_password_hash(stored_pw, password):
                    authenticated = True
                else:
                    # Fallback: plaintext equality (legacy). If it matches, upgrade DB to hashed password.
                    if stored_pw == password:
                        authenticated = True
                        try:
                            new_hash = generate_password_hash(password)
                            c.execute("UPDATE Users SET Password = ? WHERE UserID = ?", (new_hash, user['UserID']))
                            conn.commit()
                            print(f"Upgraded plaintext password to hashed for user '{username}'", file=sys.stderr)
                        except Exception as e:
                            # log upgrade failure but do not block login
                            print("Password upgrade failed:", e, file=sys.stderr)
                            traceback.print_exc()
            except Exception as e:
                # Some malformed hash or unexpected error — fallback to direct compare
                print("Password check error:", e, file=sys.stderr)
                traceback.print_exc()
                if stored_pw == password:
                    authenticated = True

        # close connection if open
        if conn:
            conn.close()

        if authenticated:
            # set session and redirect to appropriate service
            session['user'] = user['UserID']
            session['name'] = user['Username']
            # sqlite3.Row does not have .get(), use mapping access
            try:
                role = (user['UserRole'] or 'user').lower()
            except Exception:
                role = 'user'
            session['role'] = role
            print(f"User '{username}' logged in successfully.", file=sys.stderr)
            
            # Build redirect host using the hostname the user used to reach login (keeps cookie domain consistent).
            # Allow env vars to override if explicitly set.
            req_host = (request.host.split(':')[0] if request and request.host else None)
            # prefer explicit env-based base, otherwise derive from req_host
            # Both admin and regular users go to the dashboard first.
            # Admin users will see an Admin Panel button on the dashboard.
            if DASHBOARD_BASE:
                target = DASHBOARD_BASE.rstrip('/') + '/'
            else:
                h = req_host or '127.0.0.1'
                target = f"http://{h}:5002/"
            return redirect(target)
        else:
            # avoid leaking details to UI
            error = "Login error, please type the correct username and password."
            return render_template_string(LOGIN_TEMPLATE, error=error, success=None)
 
    return render_template_string(LOGIN_TEMPLATE, error=error, success=success)

# --- Added: redirect root to /login so visiting localhost:5000 works ---
@app.route('/')
def index():
    return redirect(url_for('login'))

# --- Added: forgot-password route so the link in the template is handled ---
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    error = None
    success = None
    not_found = False
    reset_link = None

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            error = "Please provide an email address."
            return render_template_string(FORGOT_PASSWORD_TEMPLATE, error=error, success=None, not_found=False, reset_link=None)

        user = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT UserID, Username FROM Users WHERE LOWER(TRIM(Email)) = LOWER(TRIM(?))", (email,))
            user = c.fetchone()
            conn.close()
        except Exception as e:
            print("Database error on forgot-password lookup:", e, file=sys.stderr)
            traceback.print_exc()
            error = "Internal server error. Check server logs."
            return render_template_string(FORGOT_PASSWORD_TEMPLATE, error=error, success=None, not_found=False, reset_link=None)

        if not user:
            return render_template_string(FORGOT_PASSWORD_TEMPLATE, error=None, success=None, not_found=True, reset_link=None)

        # Build a secure token stored with 1-hour expiry
        token = os.urandom(24).hex()
        expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        link = url_for('reset_password', token=token, _external=True)
        try:
            conn2 = get_db_connection()
            c2 = conn2.cursor()
            c2.execute("INSERT INTO PasswordResets (Token, UserID, ExpiresAt) VALUES (?, ?, ?)",
                       (token, user['UserID'], expires_at))
            conn2.commit()
            conn2.close()
        except Exception as e:
            print("Failed to store reset token:", e, file=sys.stderr)
            traceback.print_exc()

        if not SMTP_PASS:
            # SMTP password not set — show link directly on page
            reset_link = link
            return render_template_string(FORGOT_PASSWORD_TEMPLATE, error=None, success=None, not_found=False, reset_link=reset_link)

        try:
            html_body = _build_reset_email_html(user['Username'], link)
            msg = EmailMessage()
            msg['From']    = f'PyroSense System <{SMTP_USER}>'
            msg['To']      = email
            msg['Subject'] = '\U0001f525 PyroSense — Password Reset Request'
            msg.set_content(
                f'Hi {user["Username"]},\n\nTo reset your PyroSense password visit:\n{link}\n\nThis link expires in 1 hour.\nIf you did not request this, ignore this message.\n\n— PyroSense System'
            )
            msg.add_alternative(html_body, subtype='html')
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=ctx) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
            success = 'A reset link has been sent to your account. Please check your email or spam folder.'
        except Exception as e:
            print('SMTP send error:', e, file=sys.stderr)
            traceback.print_exc()
            # Email failed — fall back to showing the link on-page
            reset_link = link
            error = 'Could not send email. Use the link below to reset your password:'

    return render_template_string(FORGOT_PASSWORD_TEMPLATE, error=error, success=success, not_found=not_found, reset_link=reset_link)

# Simple reset password form template (matches login UI styling)

def _build_reset_email_html(username, reset_link):
    """Returns a branded HTML email body for the password reset message."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PyroSense Password Reset</title>
</head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:32px 0;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.10);max-width:560px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#7C0000 0%,#3E0000 55%,#2b2b2b 100%);padding:32px 40px;text-align:left;">
              <table cellpadding="0" cellspacing="0">
                <tr>
                  <td style="width:48px;height:48px;background:rgba(255,255,255,0.18);border-radius:12px;text-align:center;vertical-align:middle;border:2px solid rgba(255,255,255,0.3);">
                    <span style="font-size:24px;line-height:1;">&#128293;</span>
                  </td>
                  <td style="padding-left:14px;">
                    <div style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.5px;font-family:'Segoe UI',Arial,sans-serif;">PYROSENSE</div>
                    <div style="color:rgba(255,255,255,0.75);font-size:12px;font-weight:400;margin-top:2px;">Advanced Fire Detection System</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 28px;">
              <p style="margin:0 0 6px;font-size:20px;font-weight:700;color:#1a1a1a;">Password Reset Request</p>
              <p style="margin:0 0 24px;font-size:14px;color:#718096;">Hi <strong style="color:#7C0000;">{username}</strong>, we received a request to reset your password.</p>

              <table width="100%" cellpadding="0" cellspacing="0" style="background:#fff5f5;border-radius:10px;border:1px solid #f0c0c0;margin-bottom:24px;">
                <tr>
                  <td style="padding:18px 20px;text-align:center;">
                    <p style="margin:0 0 10px;font-size:12px;font-weight:700;color:#7C0000;text-transform:uppercase;letter-spacing:0.5px;">Reset Password</p>
                    <a href="{reset_link}" style="font-size:14px;font-weight:700;color:#7C0000;text-decoration:underline;">&#128279;&nbsp; Reset Password &mdash; Click Here</a>
                    <p style="margin:8px 0 0;font-size:11px;color:#a0aec0;">If the link above does not work, copy and paste the URL from the button below into your browser.</p>
                  </td>
                </tr>
              </table>

              <div style="text-align:center;margin-bottom:28px;">
                <a href="{reset_link}" style="display:inline-block;padding:14px 36px;background:linear-gradient(135deg,#7C0000,#3E0000,#2b2b2b);color:#ffffff;text-decoration:none;border-radius:10px;font-size:15px;font-weight:700;letter-spacing:0.3px;">&#128273;&nbsp; Reset My Password</a>
              </div>

              <p style="margin:0 0 6px;font-size:13px;color:#a0aec0;text-align:center;">This link expires in <strong>1 hour</strong>.</p>
              <p style="margin:0;font-size:13px;color:#718096;text-align:center;">If you did not request a password reset, you can safely <strong>ignore this email</strong> &mdash; your account has not been changed.</p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#1a1a1a;padding:18px 40px;text-align:center;">
              <p style="margin:0;font-size:12px;color:#718096;">This is an automated message from <strong style="color:#e2e8f0;">PyroSense</strong>. Do not reply to this email.</p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

RESET_PASSWORD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PyroSense - Reset Password</title>
    <link rel="stylesheet" href="/static/css/login.css">
</head>
<body>
    <div class="login-container">
        <h1 class="brand-header">PyroSense</h1>
        <p class="subtitle">Reset Password</p>
        {% if error %}<div class="flash-message">{{ error }}</div>{% endif %}
        {% if success %}<div class="success-message">{{ success }}</div>{% endif %}
        <form method="post">
            <input type="hidden" name="token" value="{{ token }}">
            <label for="password">New Password</label>
            <input type="password" id="password" name="password" required>
            <label for="password2">Confirm Password</label>
            <input type="password" id="password2" name="password2" required>
            <button class="login-button" type="submit">Set New Password</button>
        </form>
        <div class="small-link">
            <a href="/login">← Back to Sign In</a>
        </div>
    </div>
</body>
</html>
"""

# Endpoint to consume a password reset token and set a new password
@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    error = None
    success = None
    token = request.values.get('token', '').strip()
    if not token:
        error = "Invalid or missing token."
        return render_template_string(RESET_PASSWORD_TEMPLATE, error=error, success=None, token='')

    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT Token, UserID, ExpiresAt FROM PasswordResets WHERE Token = ?", (token,))
        row = c.fetchone()
        conn.close()
    except Exception as e:
        print("DB error checking reset token:", e, file=sys.stderr)
        traceback.print_exc()
        row = None

    valid = False
    if row:
        try:
            expires_at = datetime.fromisoformat(row['ExpiresAt'])
            if datetime.utcnow() <= expires_at:
                valid = True
        except Exception as e:
            print("Token expiry parse error:", e, file=sys.stderr)

    if request.method == 'POST':
        if not valid:
            error = "Reset token is invalid or has expired."
            return render_template_string(RESET_PASSWORD_TEMPLATE, error=error, token=token)
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        if not password or password != password2:
            error = "Passwords must match and not be empty."
            return render_template_string(RESET_PASSWORD_TEMPLATE, error=error, token=token)
        if len(password) < 6:
            error = "Password must be at least 6 characters."
            return render_template_string(RESET_PASSWORD_TEMPLATE, error=error, token=token)
        # Apply new hashed password
        try:
            conn = get_db_connection()
            c = conn.cursor()
            new_hash = generate_password_hash(password)
            c.execute("UPDATE Users SET Password = ? WHERE UserID = ?", (new_hash, row['UserID']))
            c.execute("DELETE FROM PasswordResets WHERE Token = ?", (token,))
            conn.commit()
            conn.close()
            success = "Password updated. You may now sign in."
            # redirect to login and show success
            return redirect(url_for('login', success=success))
        except Exception as e:
            print("Error updating password:", e, file=sys.stderr)
            traceback.print_exc()
            error = "Failed to update password. Contact admin."
            return render_template_string(RESET_PASSWORD_TEMPLATE, error=error, token=token)

    # GET path: show form if valid
    if not valid:
        error = "Reset token is invalid or has expired."
    return render_template_string(RESET_PASSWORD_TEMPLATE, error=error, success=success, token=token)

# Signup template
SIGNUP_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PyroSense - Create Account</title>
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
        .pw-match-hint { font-size: 12px; margin: 6px 0 10px; min-height: 18px; }
        .pw-match-hint.match { color: #38a169; }
        .pw-match-hint.no-match { color: #e53e3e; }
        .field-hint { font-size: 12px; color: #a0aec0; margin: -4px 0 16px; line-height: 1.5; }
        .pw-wrap { position: relative; margin-bottom: 0; }
        .pw-wrap input { padding-right: 44px !important; width: 100%; box-sizing: border-box; margin-bottom: 0; }
        .pw-toggle { position:absolute; right:12px; top:0; bottom:0; margin:auto; height:20px; display:flex; align-items:center; background:none; border:none; cursor:pointer; padding:0; color:#7C0000; }
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

        <form method="post" action="/signup" autocomplete="off" id="signupForm">
            <div class="signup-grid">
                <!-- Left column -->
                <div class="form-col">
                    <label for="full_name">Full Name</label>
                    <input id="full_name" name="full_name" type="text" required placeholder="e.g. Juan Dela Cruz" autofocus>

                    <label for="username">Username</label>
                    <input id="username" name="username" type="text" required placeholder="Choose a username">

                    <label for="email">Email</label>
                    <input id="email" name="email" type="email" required placeholder="your@email.com">
                </div>

                <div class="divider"></div>

                <!-- Right column -->
                <div class="form-col">
                    <label for="password">Password</label>
                    <div class="pw-wrap">
                        <input id="password" name="password" type="password" required placeholder="Min. 8 characters" autocomplete="new-password">
                        <button type="button" class="pw-toggle" onclick="togglePw('password','eyePw1')" tabindex="-1">
                            <svg id="eyePw1" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                        </button>
                    </div>
                    <ul class="pw-rules" id="pwRules" style="margin-top:8px;">
                        <li id="r-len">At least 8 characters</li>
                        <li id="r-upper">One uppercase letter (A–Z)</li>
                        <li id="r-num">One number (0–9)</li>
                        <li id="r-special">One special character (@$!%*?&#)</li>
                    </ul>

                    <label for="password2">Confirm Password</label>
                    <div class="pw-wrap">
                        <input id="password2" name="password2" type="password" required placeholder="Repeat your password" autocomplete="new-password">
                        <button type="button" class="pw-toggle" onclick="togglePw('password2','eyePw2')" tabindex="-1">
                            <svg id="eyePw2" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                        </button>
                    </div>
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
        function togglePw(inputId, iconId) {
            const inp = document.getElementById(inputId);
            const ico = document.getElementById(iconId);
            if (inp.type === 'password') {
                inp.type = 'text';
                ico.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/>';
            } else {
                inp.type = 'password';
                ico.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
            }
        }

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

</body>
</html>
"""

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    success = None
    if request.method == 'POST':
        full_name  = request.form.get('full_name', '').strip()
        username   = request.form.get('username', '').strip()
        phone      = request.form.get('phone', '').strip()
        email      = request.form.get('email', '').strip()
        password   = request.form.get('password', '')
        password2  = request.form.get('password2', '')
        # Role is always 'user' from public signup — admins set roles via admin panel
        role = 'user'

        if not full_name or not username or not email or not password:
            error = "Please fill in all required fields."
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
            return redirect('/login?success=Account created successfully. You can now sign in.')
        except sqlite3.IntegrityError as e:
            msg = str(e).lower()
            if 'username' in msg:
                error = "Username already exists."
            elif 'email' in msg:
                error = "Email is already registered."
            else:
                error = "An account with that information already exists."
            return render_template_string(SIGNUP_TEMPLATE, error=error, success=None)
        except Exception as e:
            print("Signup error:", e, file=sys.stderr)
            traceback.print_exc()
            error = f"Database error: {e}. Please restart the server and try again."
            return render_template_string(SIGNUP_TEMPLATE, error=error, success=None)
    return render_template_string(SIGNUP_TEMPLATE, error=error, success=success)

# Add logout route that attempts to stop the camera service, clears session, and redirects to login
@app.route('/logout', methods=['GET'])
def logout():
    user_id = session.pop('user', None)
    session.pop('name', None)
    session.pop('role', None)

    camera_msg = ""
    if CAMERA_CONTROL_URL:
        try:
            # send stop command to camera control endpoint (best-effort)
            requests.post(CAMERA_CONTROL_URL, json={"action": "stop", "user_id": user_id}, timeout=5)
        except Exception as e:
            print("Camera stop request failed during logout:", e, file=sys.stderr)
            camera_msg = " (camera stop request failed)"

    msg = "You have been logged out." + camera_msg
    return redirect(url_for('login', success=msg))

if __name__ == '__main__':
    # ensure DB/tables before starting the server
    try:
        init_db()
    except Exception as e:
        print("init_db() failed:", e, file=sys.stderr)
        traceback.print_exc()

    # Allow configuring host/port/debug via environment for easier testing.
    # Binding to 0.0.0.0 accepts connections from localhost, 127.0.0.1 and other interfaces.
    host = os.environ.get('PYROSENSE_HOST', '0.0.0.0')
    port = int(os.environ.get('PYROSENSE_PORT', '5000'))
    debug_env = os.environ.get('PYROSENSE_DEBUG', '1').lower()
    debug = debug_env in ('1', 'true', 'yes', 'on')

    print(f"Starting PyroSense login app on http://{host}:{port} (debug={debug})", file=sys.stderr)
    # Also print common local URLs to help troubleshooting
    print(f"Try: http://127.0.0.1:{port} and http://localhost:{port}", file=sys.stderr)

    # Run the Flask app
    app.run(host=host, port=port, debug=debug)

#!/usr/bin/env python3
"""
PyroSense Login Page - Python Flask Application
Simple login redirect for demonstration purposes - UI ONLY
"""

from flask import Flask, render_template_string, request, redirect, session, url_for, send_from_directory
import os
import smtplib
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import sys
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
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')

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
            <input type="password" id="password" name="password" required>
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
            confirmButtonColor: '#ff6b6b',
            background: '#ffffff',
            backdrop: 'rgba(0, 0, 0, 0.6)',
            customClass: { 
                popup: 'swal2-border-radius'
            },
            buttonsStyling: false,
            didOpen: () => {
                const btn = document.querySelector('.swal2-confirm');
                btn.style.background = 'linear-gradient(135deg, #ff6b6b 0%, #ffa500 50%, #ffeb3b 100%)';
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
        Swal.fire({
            icon: 'success',
            title: 'Success',
            text: '{{ success }}',
            confirmButtonText: 'OK',
            confirmButtonColor: '#48bb78',
            background: '#ffffff',
            backdrop: 'rgba(0, 0, 0, 0.6)',
            customClass: { 
                popup: 'swal2-border-radius'
            },
            buttonsStyling: false,
            timer: 3000,
            timerProgressBar: true,
            didOpen: () => {
                const btn = document.querySelector('.swal2-confirm');
                btn.style.background = '#48bb78';
                btn.style.color = 'white';
                btn.style.border = 'none';
                btn.style.borderRadius = '12px';
                btn.style.padding = '12px 30px';
                btn.style.fontWeight = '600';
                btn.style.cursor = 'pointer';
            }
        });
    </script>
    {% endif %}
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
        {% if success %}
        <div class="success-message">{{ success }}</div>
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
    
    # Create Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            UserID INTEGER PRIMARY KEY AUTOINCREMENT,
            Username TEXT UNIQUE NOT NULL,
            Password TEXT NOT NULL,
            Email TEXT UNIQUE NOT NULL,
            UserRole TEXT DEFAULT 'user'
        )
    """)
    
    # Create PasswordResets table
    c.execute("""
        CREATE TABLE IF NOT EXISTS PasswordResets (
            Token TEXT PRIMARY KEY,
            UserID INTEGER NOT NULL,
            ExpiresAt TEXT NOT NULL,
            FOREIGN KEY (UserID) REFERENCES Users(UserID)
        )
    """)
    
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
            if role == 'admin':
                if ADMIN_BASE:
                    target = ADMIN_BASE.rstrip('/') + '/admin'
                else:
                    h = req_host or '127.0.0.1'
                    target = f"http://{h}:5003/admin"
            else:
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

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            error = "Please provide an email address."
            return render_template_string(FORGOT_PASSWORD_TEMPLATE, error=error)

        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT UserID, Username FROM Users WHERE Email = ?", (email,))
            user = c.fetchone()
        except Exception as e:
            print("Database error on forgot-password lookup:", e, file=sys.stderr)
            traceback.print_exc()
            error = "Internal server error. Check server logs."
            return render_template_string(FORGOT_PASSWORD_TEMPLATE, error=error)

        # Always show a generic success message to avoid account enumeration.
        if user:
            # build a secure token and store it with expiry (1 hour)
            token = os.urandom(24).hex()
            expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
            reset_link = url_for('reset_password', token=token, _external=True)
            try:
                # store token in DB
                try:
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("INSERT INTO PasswordResets (Token, UserID, ExpiresAt) VALUES (?, ?, ?)",
                              (token, user['UserID'], expires_at))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print("Failed to store reset token:", e, file=sys.stderr)
                    traceback.print_exc()
                # Try to send email if SMTP creds are present (won't fail the flow if sending fails)
                if SMTP_USER and SMTP_PASS:
                    msg = MIMEMultipart()
                    msg['From'] = SMTP_USER
                    msg['To'] = email
                    msg['Subject'] = "PyroSense Password Reset"
                    body = f"To reset your PyroSense password, visit:\n\n{reset_link}\n\nThis link will expire in 1 hour. If you did not request this, ignore this message."
                    msg.attach(MIMEText(body, 'plain'))
                    s = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
                    s.starttls()
                    s.login(SMTP_USER, SMTP_PASS)
                    s.send_message(msg)
                    s.quit()
                success = "If an account exists for that email, a reset link has been sent."
            except Exception as e:
                print("SMTP send error:", e, file=sys.stderr)
                traceback.print_exc()
                success = "If an account exists for that email, a reset link has been sent (email delivery may have failed)."
        else:
            success = "If an account exists for that email, a reset link has been sent."

    return render_template_string(FORGOT_PASSWORD_TEMPLATE, error=error, success=success)

# Simple reset password form template (matches login UI styling)
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

# Add SIGNUP_TEMPLATE (UI matches LOGIN_TEMPLATE) — updated: tabindex, autofocus, SweetAlert2 success modal
SIGNUP_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PyroSense - Sign Up</title>
    <link rel="stylesheet" href="/static/css/login.css">
</head>
<body>
    <div class="login-container" role="main" aria-labelledby="signup-title">
        <h1 class="brand-header" id="signup-title">PyroSense</h1>
        <p class="subtitle">Create account</p>

        {% if error %}
        <div class="flash-message">{{ error }}</div>
        {% endif %}
        {% if success %}
        <div class="success-message">{{ success }}</div>
        {% endif %}

        <form method="post" action="/signup" autocomplete="off" novalidate>
            <label for="username">Username</label>
            <input id="username" name="username" type="text" required tabindex="1" autofocus>

            <label for="email">Email</label>
            <input id="email" name="email" type="email" required tabindex="2">

            <label for="password">Password</label>
            <input id="password" name="password" type="password" required tabindex="3">

            <label for="password2">Confirm Password</label>
            <input id="password2" name="password2" type="password" required tabindex="4">

            <button class="login-button" type="submit" tabindex="5">Sign Up</button>
        </form>

        <div class="small-link">
            <a href="/login">← Back to Sign In</a>
        </div>
    </div>

    <!-- SweetAlert2: show success modal client-side and then redirect to /login -->
    {% if success %}
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function () {
            Swal.fire({
                icon: 'success',
                title: 'Account created!',
                text: '{{ success }}',
                showConfirmButton: true,
                confirmButtonText: 'Go to Sign In',
                background: '#ffffff',
                customClass: { popup: 'swal2-border-radius' }
            }).then(function () {
                window.location.href = '/login';
            });
        });
    </script>
    {% endif %}
</body>
</html>
"""

# Add /signup route that creates a user in the same DB (hashed password)
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
             error = "Please fill in all required fields."
             return render_template_string(SIGNUP_TEMPLATE, error=error, success=None)
         if password != password2:
             error = "Passwords do not match."
             return render_template_string(SIGNUP_TEMPLATE, error=error, success=None)
         if len(password) < 6:
             error = "Password must be at least 6 characters."
             return render_template_string(SIGNUP_TEMPLATE, error=error, success=None)
         try:
             conn = get_db_connection()
             c = conn.cursor()
             hashed = generate_password_hash(password)
             c.execute("INSERT INTO Users (Username, Password, Email, UserRole) VALUES (?, ?, ?, ?)",
                       (username, hashed, email, 'user'))
             conn.commit()
             conn.close()
             success = "Your account was created successfully."
             # Render signup page with success so SweetAlert shows on the client, then redirect to /login
             return render_template_string(SIGNUP_TEMPLATE, error=None, success=success)
         except sqlite3.IntegrityError as e:
             # username or email collision
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
             error = "Internal error. Contact admin."
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

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

app = Flask(__name__)
app.secret_key = os.environ.get('PYROSENSE_SECRET', 'pyrosense_shared_secret_key')  # Use env var if available

# Admin credentials - UI only, not actually used for verification
ADMIN_USERNAME = "admin"

# Clean Login page HTML template with geometric background image
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PyroSense - Login</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-image: url('/static/login background.jpg');
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
            color: #333;
            height: 100vh;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .login-container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 50px 40px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 420px;
            text-align: center;
        }
        
        .brand-header {
            font-size: 2.8rem;
            font-weight: 700;
            color: #4a5568;
            margin-bottom: 10px;
            letter-spacing: -1px;
        }
        
        .subtitle {
            color: #718096;
            margin-bottom: 40px;
            font-size: 16px;
        }
        
        .form-group {
            margin-bottom: 25px;
            text-align: left;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #4a5568;
            font-size: 14px;
        }
        
        input[type="text"], input[type="password"] {
            width: 100%;
            padding: 15px 20px;
            border-radius: 12px;
            border: 2px solid #e2e8f0;
            background-color: white;
            font-size: 16px;
            transition: all 0.3s ease;
        }
        
        input[type="text"]:focus, input[type="password"]:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .forgot-password {
            text-align: right;
            margin-top: 10px;
            margin-bottom: 30px;
        }
        
        .forgot-password a {
            color: #718096;
            text-decoration: none;
            font-size: 14px;
            transition: color 0.3s ease;
        }
        
        .forgot-password a:hover {
            color: #667eea;
            text-decoration: underline;
        }
        
        .login-button {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 12px;
            background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 50%, #ffeb3b 100%);
            color: white;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
        }
        
        .login-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(255, 107, 107, 0.4);
            background: linear-gradient(135deg, #ff5252 0%, #ff9500 50%, #fdd835 100%);
        }
        
        .flash-message {
            padding: 15px 20px;
            margin-bottom: 25px;
            border-radius: 12px;
            background-color: #fed7d7;
            color: #c53030;
            font-weight: 500;
            border: 1px solid #feb2b2;
        }
        
        .success-message {
            padding: 15px 20px;
            margin-bottom: 25px;
            border-radius: 12px;
            background-color: #c6f6d5;
            color: #22543d;
            font-weight: 500;
            border: 1px solid #9ae6b4;
        }
        
        .attribution {
            position: fixed;
            bottom: 20px;
            left: 20px;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.7);
        }
        
        .attribution a {
            color: rgba(255, 255, 255, 0.8);
            text-decoration: none;
        }
        
        .attribution a:hover {
            text-decoration: underline;
        }
        
        @media (max-width: 768px) {
            .login-container {
                margin: 20px;
                padding: 40px 30px;
            }
            
            .brand-header {
                font-size: 2.2rem;
            }
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1 class="brand-header">PyroSense</h1>
        <p class="subtitle">Fire Detection & Management System</p>
        
        {% if error %}
        <div class="flash-message">{{ error }}</div>
        {% endif %}

        {% if success %}
        <div class="success-message">{{ success }}</div>
        {% endif %}
        
        <form action="/login" method="post">
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            
            <div class="forgot-password">
                <a href="/forgot-password">Forgot your password?</a>
            </div>
            
            <button type="submit" class="login-button">Sign In</button>
        </form>
    </div>
    
    <div class="attribution">
        <a href="https://www.freepik.com/free-vector/minimalist-background-gradient-design-style_34345006.htm">Background by AndreaCharlesta on Freepik</a>
    </div>
</body>
</html>
"""

# Forgot Password HTML template with matching background
FORGOT_PASSWORD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PyroSense - Forgot Password</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-image: url('/static/login background.jpg');
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
            color: #333;
            height: 100vh;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .login-container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 50px 40px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 420px;
            text-align: center;
        }
        
        .brand-header {
            font-size: 2.8rem;
            font-weight: 700;
            color: #4a5568;
            margin-bottom: 10px;
            letter-spacing: -1px;
        }
        
        .subtitle {
            color: #718096;
            margin-bottom: 30px;
            font-size: 16px;
        }
        
        .description {
            text-align: center;
            margin-bottom: 30px;
            color: #718096;
            font-size: 14px;
            line-height: 1.5;
        }
        
        .form-group {
            margin-bottom: 25px;
            text-align: left;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #4a5568;
            font-size: 14px;
        }
        
        input[type="email"] {
            width: 100%;
            padding: 15px 20px;
            border-radius: 12px;
            border: 2px solid #e2e8f0;
            background-color: white;
            font-size: 16px;
            transition: all 0.3s ease;
        }
        
        input[type="email"]:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .login-button {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 12px;
            background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 50%, #ffeb3b 100%);
            color: white;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-bottom: 25px;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
        }
        
        .login-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(255, 107, 107, 0.4);
            background: linear-gradient(135deg, #ff5252 0%, #ff9500 50%, #fdd835 100%);
        }
        
        .flash-message {
            padding: 15px 20px;
            margin-bottom: 25px;
            border-radius: 12px;
            background-color: #fed7d7;
            color: #c53030;
            font-weight: 500;
            border: 1px solid #feb2b2;
        }
        
        .success-message {
            padding: 15px 20px;
            margin-bottom: 25px;
            border-radius: 12px;
            background-color: #c6f6d5;
            color: #22543d;
            font-weight: 500;
            border: 1px solid #9ae6b4;
        }
        
        .back-link {
            text-align: center;
        }
        
        .back-link a {
            color: #718096;
            text-decoration: none;
            font-size: 14px;
            transition: color 0.3s ease;
        }
        
        .back-link a:hover {
            color: #667eea;
            text-decoration: underline;
        }
        
        .attribution {
            position: fixed;
            bottom: 20px;
            left: 20px;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.7);
        }
        
        .attribution a {
            color: rgba(255, 255, 255, 0.8);
            text-decoration: none;
        }
        
        .attribution a:hover {
            text-decoration: underline;
        }
        
        @media (max-width: 768px) {
            .login-container {
                margin: 20px;
                padding: 40px 30px;
            }
            
            .brand-header {
                font-size: 2.2rem;
            }
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1 class="brand-header">PyroSense</h1>
        <p class="subtitle">Password Reset</p>
        <p class="description">Enter your admin email address and we'll send you a link to reset your password.</p>
        
        {% if error %}
        <div class="flash-message">{{ error }}</div>
        {% endif %}
        
        {% if success %}
        <div class="success-message">{{ success }}</div>
        {% endif %}
        
        <form action="/forgot-password" method="post">
            <div class="form-group">
                <label for="email">Admin Email:</label>
                <input type="email" id="email" name="email" required>
            </div>
            
            <button type="submit" class="login-button">Send Reset Link</button>
        </form>
        
        <div class="back-link">
            <a href="/login">← Back to Sign In</a>
        </div>
    </div>
    
    <div class="attribution">
        <a href="https://www.freepik.com/free-vector/minimalist-background-gradient-design-style_34345006.htm">Background by AndreaCharlesta on Freepik</a>
    </div>
</body>
</html>
"""

# SMTP configuration (set these as environment variables for security)
SMTP_SERVER = os.environ.get('PYROSENSE_SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('PYROSENSE_SMTP_PORT', 587))
SMTP_USER = os.environ.get('PYROSENSE_SMTP_USER', 'your_email@gmail.com')
SMTP_PASS = os.environ.get('PYROSENSE_SMTP_PASS', 'your_password')
# Optional camera control endpoint (set PYROSENSE_CAMERA_CONTROL_URL to enable); leave empty to disable camera control
CAMERA_CONTROL_URL = os.environ.get('PYROSENSE_CAMERA_CONTROL_URL', '')

# Path to SQLite DB file
DB_PATH = os.path.join(os.path.dirname(__file__), 'pyrosense_db.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create tables only. Do NOT create any demo admin user."""
    conn = get_db_connection()
    c = conn.cursor()
    # Create users table (no demo account creation)
    c.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            UserID INTEGER PRIMARY KEY AUTOINCREMENT,
            Username TEXT UNIQUE NOT NULL,
            Password TEXT NOT NULL,
            Email TEXT UNIQUE
        )
    """)
    conn.commit()
    conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
	"""Handle login page display and form submission (SQLite-backed)"""
	error = None
	# read optional success message passed via query string
	success = request.args.get('success')

	if request.method == 'POST':
		username = request.form.get('username', '').strip()
		password = request.form.get('password', '').strip()

		if not username or not password:
			error = "Please provide both username and password."
			return render_template_string(LOGIN_TEMPLATE, error=error)

		user = None
		conn = None
		try:
			conn = get_db_connection()
			c = conn.cursor()
			c.execute("SELECT UserID, Username, Password, Email FROM Users WHERE Username = ?", (username,))
			user = c.fetchone()
		except Exception as e:
			# log full traceback to server console for debugging
			print("Database error on login lookup:", e, file=sys.stderr)
			traceback.print_exc()
			error = "Internal server error. Check server logs."
			if conn:
				conn.close()
			return render_template_string(LOGIN_TEMPLATE, error=error)

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
			# set session and redirect to dashboard
			session['user'] = user['UserID']
			session['name'] = user['Username']
			print(f"User '{username}' logged in successfully.", file=sys.stderr)
			return redirect('http://localhost:5002/')
		else:
			# avoid leaking details to UI
			error = "Invalid username or password."

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
            conn.close()
        except Exception as e:
            print("Database error on forgot-password lookup:", e, file=sys.stderr)
            traceback.print_exc()
            error = "Internal server error. Check server logs."
            return render_template_string(FORGOT_PASSWORD_TEMPLATE, error=error)

        # Always show a generic success message to avoid account enumeration.
        if user:
            # build a simple token and a reset link (token storage/verification not implemented here)
            token = os.urandom(16).hex()
            reset_link = url_for('login', _external=True) + f"?reset={token}"
            try:
                # Try to send email if SMTP creds are present (won't fail the flow if sending fails)
                if SMTP_USER and SMTP_PASS:
                    msg = MIMEMultipart()
                    msg['From'] = SMTP_USER
                    msg['To'] = email
                    msg['Subject'] = "PyroSense Password Reset"
                    body = f"To reset your PyroSense password, visit:\n\n{reset_link}\n\nIf you did not request this, ignore this message."
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

# --- Added: logout route to clear session and attempt to stop camera ---
@app.route('/logout', methods=['GET'])
def logout():
    user_id = session.pop('user', None)
    session.pop('name', None)

    camera_result_msg = ""
    if CAMERA_CONTROL_URL:
        try:
            # POST a simple JSON instructing the camera service to stop streaming
            requests.post(CAMERA_CONTROL_URL, json={"action": "stop", "user_id": user_id}, timeout=5)
            camera_result_msg = ""
        except Exception as e:
            print("Camera stop request failed:", e, file=sys.stderr)
            camera_result_msg = " (camera stop request failed)"

    msg = "You have been logged out." + camera_result_msg
    # redirect back to login and show confirmation
    return redirect(url_for('login', success=msg))

# --- Added: ensure DB is initialized and app runs when executed directly ---
if __name__ == '__main__':
    # create DB/tables and demo admin (if needed) before starting the server
    try:
        init_db()
    except Exception as e:
        print("init_db() failed:", e, file=sys.stderr)
        traceback.print_exc()
    # Run the Flask dev server on localhost:5000 (matches your screenshot URL)
    app.run(host='127.0.0.1', port=5000, debug=True)

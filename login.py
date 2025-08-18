#!/usr/bin/env python3
"""
PyroSense Login Page - Python Flask Application
Simple login redirect for demonstration purposes - UI ONLY
"""

from flask import Flask, render_template_string, request, redirect, session, url_for, send_from_directory
import os

app = Flask(__name__)
app.secret_key = 'pyrosense_shared_secret_key'  # Use the same key in both apps

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

@app.route('/static/<filename>')
def static_files(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

@app.route('/')
def index():
    """Redirect root to login page"""
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle login page display and form submission - UI ONLY DEMO"""
    error = None
    
    if request.method == 'POST':
        # No actual verification - this is UI only demo
        # Get username just to store it in session
        username = request.form.get('username', 'admin')
        
        # Set user session
        session['user'] = username
        session['name'] = 'Administrator'
        
        # Redirect to dashboard (dashboard.py) on port 5002
        return redirect('http://localhost:5002/')
    
    return render_template_string(LOGIN_TEMPLATE, error=error)

@app.route('/logout')
def logout():
    """Handle user logout"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle password reset requests - UI ONLY DEMO"""
    error = None
    success = None
    
    if request.method == 'POST':
        # Accept any email - this is UI only
        success = "Password reset email sent! Please check your inbox."
    
    return render_template_string(FORGOT_PASSWORD_TEMPLATE, error=error, success=success)

# Route to history page - just a placeholder to redirect to the actual history application
@app.route('/history')
def history():
    """Redirect to the history application"""
    if not session.get('user'):
        return redirect(url_for('login'))
    
    try:
        import requests
        # Check if history app is running on port 5003 instead of 5001
        requests.get('http://localhost:5003', timeout=0.5)
        return redirect('http://localhost:5003')
    except:
        # History app not running
        return render_template_string("""
            <html>
                <head><title>History App Not Available</title></head>
                <body style="background: #121212; color: white; text-align: center; padding-top: 100px; font-family: Arial;">
                    <h1>History Application Not Running</h1>
                    <p>The history application is not currently running on port 5003.</p>
                    <p>Please start the history.py application on port 5003 and try again.</p>
                    <p><a href="/logout" style="color: #f77f00;">Logout</a></p>
                </body>
            </html>
        """)

if __name__ == '__main__':
    print("🔐 Starting PyroSense Login System...")
    print("🔥 Authentication Portal - Python Edition - UI ONLY DEMO")
    print("=" * 60)
    print("Login Page URL: http://localhost:5000")
    print("This is a UI-only demo - any username/password will work")
    print("NOTE: You must also run dashboard.py on port 5002 for redirection to work")
    print("NOTE: History app should run on port 5003 to avoid conflicts")
    print("NOTE: Background image should be saved as 'static/login background.jpg'")
    print("To stop server: Press Ctrl+C")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
    print("To stop server: Press Ctrl+C")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)

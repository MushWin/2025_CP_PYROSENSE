#!/usr/bin/env python3
"""
PyroSense Admin Panel - User Management System
Handles CRUD operations for users and system monitoring
"""

from flask import Flask, render_template_string, request, redirect, session, url_for, jsonify
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import sys
import traceback
from datetime import datetime

# REPLACE the app init with an explicit static folder mapping
STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')
app.secret_key = os.environ.get('PYROSENSE_SECRET', 'pyrosense_shared_secret_key')
# Use a single host consistently (avoid localhost vs 127.0.0.1 cookie split)
LOGIN_BASE = os.environ.get('PYROSENSE_LOGIN_BASE', 'http://127.0.0.1:5000')
# Mildly tighten session behavior
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Admin Panel HTML Template
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <!-- Restore required CDNs (must be before any inline scripts) -->
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PyroSense Admin Panel</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <script>
      // Fallback to prevent crashes if CDN fails
      if (typeof window.Swal === 'undefined') {
        window.Swal = { fire: ({title,text}) => alert((title?title+': ':'') + (text||'')) };
        console.warn('SweetAlert2 CDN failed. Using alert() fallback.');
      }
    </script>
    <style>
        :root{
            --bg:#f5f7fb;
            --card:#ffffff;
            --primary:#6c63ff;
            --primary-600:#584ff2;
            --accent:#ffb347;
            --danger:#ff6b6b;
            --text:#1f2937;
            --muted:#6b7280;
            --ring:rgba(108,99,255,.35);
            --shadow:0 12px 32px rgba(24,24,50,.08);
            --radius:22px;
            --pad:24px;
            --gap:16px;
        }

        * { box-sizing: border-box; }
        html, body { height: 100%; }
        body {
            font-family: Inter, "Segoe UI", Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
        }

        /* Header */
        .header {
            background: var(--card);
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        }
        .header-content {
            max-width: 1120px;
            margin: 0 auto;
            height: 72px;
            padding: 0 var(--pad);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .logo-box { display:flex; align-items:center; gap:12px; }
        .logo-icon img { width: 34px; height: 34px; }
        .logo-emoji {
            width: 34px; height: 34px;
            display: grid; place-items: center;
            font-size: 28px; line-height: 1;
        }
        .brand-title { font-weight: 800; font-size: 1.8rem; color: var(--primary); letter-spacing: .3px; }
        .brand-subtitle { font-weight: 600; color: #666; }
        .user-info { display:flex; align-items:center; gap:14px; }
        .user-info span { display:flex; align-items:center; gap:8px; color:#1f2937; font-weight:600; }
        .logout-btn {
            display:inline-flex; align-items:center; gap:8px;
            position: relative;
            padding: 10px 18px 10px 38px;
            border-radius: 999px;
            background: var(--danger); color:#fff; text-decoration:none;
            box-shadow: 0 6px 16px rgba(255,107,107,.18);
            transition: transform .05s ease, filter .2s ease;
        }
        .logout-btn i { position:absolute; left:12px; font-size: 16px; }
        .logout-btn:hover { filter: brightness(.95); }

        /* Page container */
        .page {
            max-width: 1120px;
            margin: 0 auto;
            padding: 32px var(--pad) 64px;
        }

        /* Tabs */
        .nav-card {
            background: var(--card);
            border-radius: calc(var(--radius) + 4px);
            box-shadow: var(--shadow);
            padding: 14px;
            display:flex; gap:12px; justify-content:center;
            margin: 16px auto 28px;
            width: fit-content;
        }
        .nav-btn {
            border: none; cursor: pointer;
            display:flex; align-items:center; gap:10px;
            padding: 12px 20px;
            border-radius: 999px;
            font-weight: 700;
            background: #f1f3fb;
            color: var(--primary);
            transition: background .2s, color .2s, transform .05s;
        }
        .nav-btn i { font-size: 18px; }
        .nav-btn.active {
            background: var(--primary);
            color: #fff;
            box-shadow: 0 8px 18px rgba(108,99,255,.25);
        }
        .nav-btn:active { transform: translateY(1px); }

        /* Cards */
        .content-card {
            background: var(--card);
            border-radius: 28px;
            box-shadow: var(--shadow);
            padding: 8px 0 28px;
            margin: 0 auto 28px;
        }
        .section-title {
            display:flex; gap:12px; align-items:center; justify-content:center;
            font-size: 1.9rem; font-weight: 800; padding-top: 22px;
        }
        .section-title i, .section-title svg { color: var(--primary); }
        .section-underline {
            width: 140px; height: 4px; border-radius: 999px;
            background: var(--primary);
            margin: 8px auto 16px;
            opacity: .15;
        }

        /* Table wrapper for responsiveness */
        .table-wrap {
            width: 100%;
            padding: 0 var(--pad);
            overflow-x: auto;
        }
        .users-table {
            width: 100%;
            border-collapse: collapse;
            min-width: 720px;
        }
        .users-table thead th {
            text-align: left;
            padding: 14px 16px;
            background:#f6f7ff;
            color: var(--primary);
            font-weight: 800;
            border-bottom: 1px solid #eceef8;
        }
        .users-table tbody td {
            padding: 14px 16px;
            border-bottom: 1px solid #f1f2f6;
            color:#1f2937;
        }
        .users-table tbody tr:hover { background: #fafbff; }
        .col-actions { width: 280px; }

        /* Badges */
        .role-badge {
            display:inline-block; padding: 6px 14px; border-radius: 999px;
            font-size:.85rem; font-weight:800; letter-spacing:.6px;
        }
        .role-admin { background: #ffd4d4; color: #d12f2f; }
        .role-user  { background: #d5f2e0; color: #1f7e49; }

        /* Buttons */
        .actions { display:flex; gap:10px; flex-wrap: wrap; }
        .btn {
            display:inline-flex; align-items:center; gap:8px;
            border:none; cursor:pointer; border-radius: 12px;
            padding: 10px 14px;
            font-weight:700; transition: filter .15s, transform .05s;
        }
        .btn i { font-size: 14px; }
        .btn:active { transform: translateY(1px); }
        .btn-primary { background: var(--primary); color:#fff; }
        .btn-primary:hover { filter: brightness(.95); }
        .btn-warning { background: var(--accent); color:#fff; }
        .btn-warning:hover { filter: brightness(.95); }
        .btn-danger { background: var(--danger); color:#fff; }
        .btn-danger:hover { filter: brightness(.95); }

        /* Forms */
        .form-grid {
            display:grid; grid-template-columns: repeat(2, minmax(220px, 1fr));
            gap: 18px 28px; padding: 0 var(--pad);
        }
        .form-group { display:flex; flex-direction:column; gap:8px; }
        .form-group label { font-weight:700; color:#344054; }
        .input, select {
            width: 100%;
            padding: 12px 14px;
            border-radius: 12px;
            border:1px solid #e5e7ef;
            background:#fbfbfe;
            font-size: 1rem;
            outline: none;
            transition: box-shadow .15s, border-color .15s;
        }
        .input:focus, select:focus { border-color:var(--primary); box-shadow: 0 0 0 4px var(--ring); }
        .form-actions { padding: 6px var(--pad) 0; }

        /* Modal + overlay */
        .overlay {
            position:fixed; inset:0; background: rgba(6,9,31,.35);
            opacity:0; pointer-events:none; transition: opacity .2s;
            z-index: 999;
        }
        .overlay.show { opacity:1; pointer-events:auto; }
        .modal {
            position: fixed; inset: 0; display:flex; align-items:center; justify-content:center;
            z-index: 1000; pointer-events:none;
        }
        .modal-card {
            width: min(94vw, 460px);
            background: var(--card);
            border-radius: 18px;
            box-shadow: var(--shadow);
            padding: 18px var(--pad) var(--pad);
            transform: translateY(12px) scale(.98);
            opacity: 0;
            transition: transform .2s, opacity .2s;
        }
        .modal.show { pointer-events:auto; }
        .modal.show .modal-card { transform: translateY(0) scale(1); opacity:1; }
        .modal-title { margin: 6px 0 10px; font-weight: 800; color: var(--primary); text-align:center; }

        /* Ensure overlay never blocks clicks when hidden */
        .overlay { pointer-events: none; }
        .overlay.show { pointer-events: auto; }
        /* Ensure modal never blocks clicks when hidden */
        .modal { pointer-events: none; }
        .modal.show { pointer-events: auto; }

        @media (max-width: 720px) {
            .form-grid { grid-template-columns: 1fr; }
            .nav-card { width: calc(100% - 32px); }
            .brand-subtitle { display:none; }
            .col-actions { width: 220px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div class="logo-box">
                <div class="logo-icon">
                    {% if fire_icon %}
                    <img src="{{ url_for('static', filename=fire_icon) }}"
                         alt="Fire Logo"
                         onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'logo-emoji',textContent:'🔥'}));">
                    {% else %}
                    <span class="logo-emoji">🔥</span>
                    {% endif %}
                </div>
                <span class="brand-title">PyroSense</span>
                <span class="brand-subtitle">Admin Panel</span>
            </div>
            <div class="user-info">
                <span><i class="fa-solid fa-user"></i> Welcome, {{ session.name }}!</span>
                <a href="/logout" class="logout-btn"><i class="fa-solid fa-right-from-bracket"></i>Logout</a>
            </div>
        </div>
    </div>

    <div class="page">
        <div class="nav-card">
            <button class="nav-btn active" id="nav-users"><i class="fa-solid fa-users"></i> User Management</button>
            <button class="nav-btn" id="nav-create"><i class="fa-solid fa-plus"></i> Create User</button>
        </div>

        <!-- Users -->
        <section id="users-section" class="content-card">
            <div class="section-title"><i class="fa-solid fa-users"></i> User Management</div>
            <div class="section-underline"></div>
            <div class="table-wrap">
                <table class="users-table">
                    <thead>
                        <tr>
                            <th style="width:80px"># ID</th>
                            <th>Username</th>
                            <th style="width:160px">Role</th>
                            <th class="col-actions">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for user in users %}
                        <tr>
                            <td>{{ user.UserID }}</td>
                            <td>{{ user.Username }}</td>
                            <td><span class="role-badge role-{{ user.UserRole|lower }}">{{ user.UserRole|upper }}</span></td>
                            <td>
                                <div class="actions">
                                    <button
                                        class="btn btn-warning edit-btn"
                                        data-id="{{ user.UserID }}"
                                        data-username="{{ user.Username|e }}"
                                        data-role="{{ user.UserRole|e }}">
                                        <i class="fa-solid fa-pen"></i> Edit
                                    </button>
                                    {% if user.Username != 'admin' %}
                                    <button
                                        class="btn btn-danger delete-btn"
                                        data-id="{{ user.UserID }}"
                                        data-username="{{ user.Username|e }}">
                                        <i class="fa-solid fa-trash"></i> Delete
                                    </button>
                                    {% endif %}
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Create -->
        <section id="create-section" class="content-card" style="display:none;">
            <div class="section-title">
                <svg fill="currentColor" viewBox="0 0 20 20" width="28" height="28"><path d="M8 9V5a1 1 0 112 0v4h4a1 1 0 110 2h-4v4a1 1 0 11-2 0v-4H4a1 1 0 110-2h4z"/></svg>
                Create New User
            </div>
            <div class="section-underline"></div>
            <form method="post" action="/admin/create-user">
                <div class="form-grid">
                    <div class="form-group">
                        <label for="username">Username</label>
                        <input class="input" type="text" id="username" name="username" required>
                    </div>
                    <div class="form-group">
                        <label for="role">Role</label>
                        <select class="input" id="role" name="role" required>
                            <option value="user">User</option>
                            <option value="admin">Admin</option>
                        </select>
                    </div>
                    <div class="form-group" style="grid-column: 1 / -1;">
                        <label for="password">Password</label>
                        <input class="input" type="password" id="password" name="password" required>
                    </div>
                </div>
                <div class="form-actions">
                    <button type="submit" class="btn btn-primary"><i class="fa-solid fa-user-plus"></i> Create User</button>
                </div>
            </form>
        </section>
    </div>

    <!-- Modal + overlay -->
    <div class="overlay" id="overlay"></div>
    <div class="modal" id="edit-modal" aria-hidden="true">
        <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="edit-title">
            <h3 class="modal-title" id="edit-title">Edit User</h3>
            <form method="post" action="/admin/edit-user" id="edit-form">
                <input type="hidden" id="edit-user-id" name="user_id">
                <div class="form-group">
                    <label for="edit-username">Username</label>
                    <input class="input" type="text" id="edit-username" name="username" required>
                </div>
                <div class="form-group">
                    <label for="edit-role">Role</label>
                    <select class="input" id="edit-role" name="role" required>
                        <option value="user">User</option>
                        <option value="admin">Admin</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="edit-password">New Password (optional)</label>
                    <input class="input" type="password" id="edit-password" name="password" placeholder="Leave blank to keep current">
                </div>
                <div class="actions" style="margin-top:10px;">
                    <button type="submit" class="btn btn-primary"><i class="fa-solid fa-floppy-disk"></i> Update</button>
                    <button type="button" class="btn btn-danger" id="btn-cancel"><i class="fa-solid fa-xmark"></i> Cancel</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        // Flash via SweetAlert2 (safe JSON)
        {% if error %} Swal.fire({icon:'error', title:'Error', text: {{ error|tojson }}, confirmButtonColor:'#ff6b6b'}); {% endif %}
        {% if success %} Swal.fire({icon:'success', title:'Success', text: {{ success|tojson }}, confirmButtonColor:'#48bb78'}); {% endif %}
        {% if warning %} Swal.fire({icon:'warning', title:'Warning', text: {{ warning|tojson }}, confirmButtonColor:'#ffa500'}); {% endif %}
        {% if notice %} Swal.fire({icon:'info', title:'Notice', text: {{ notice|tojson }}, confirmButtonColor:'#667eea'}); {% endif %}

        // Tabs
        const navUsers = document.getElementById('nav-users');
        const navCreate = document.getElementById('nav-create');
        const usersSection = document.getElementById('users-section');
        const createSection = document.getElementById('create-section');
        function showSection(which) {
            const users = which === 'users';
            usersSection.style.display = users ? '' : 'none';
            createSection.style.display = users ? 'none' : '';
            navUsers.classList.toggle('active', users);
            navCreate.classList.toggle('active', !users);
            (users ? usersSection : createSection).scrollIntoView({behavior:'smooth', block:'start'});
        }
        navUsers.addEventListener('click', () => showSection('users'));
        navCreate.addEventListener('click', () => showSection('create'));

        // Modal helpers
        const overlay = document.getElementById('overlay');
        const modal = document.getElementById('edit-modal');
        const form = document.getElementById('edit-form');
        const idInput = document.getElementById('edit-user-id');
        const nameInput = document.getElementById('edit-username');
        const roleInput = document.getElementById('edit-role');
        const passInput = document.getElementById('edit-password');
        const btnCancel = document.getElementById('btn-cancel');
        const submitBtn = form.querySelector('button[type="submit"]');

        function openModal() {
            overlay.classList.add('show');
            modal.classList.add('show');
            document.body.style.overflow = 'hidden';
            setTimeout(() => nameInput?.focus(), 50);
        }
        function closeModal() {
            overlay.classList.remove('show');
            modal.classList.remove('show');
            document.body.style.overflow = '';
        }
        // Hard reset to avoid stuck overlay after navigation or errors
        function hardResetUI() {
            overlay?.classList.remove('show');
            modal?.classList.remove('show');
            document.body.style.overflow = '';
        }
        // Run on load and when page is restored from bfcache
        hardResetUI();
        window.addEventListener('pageshow', hardResetUI);

        overlay.addEventListener('click', closeModal);
        btnCancel.addEventListener('click', closeModal);
        document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

        // Ensure modal closes and buttons aren't left disabled after submit
        form.addEventListener('submit', () => {
            // prevent accidental double submit and "stuck" overlay on slow network
            submitBtn.disabled = true;
            submitBtn.style.opacity = '0.7';
            closeModal();
            hardResetUI();
        });

        // Event delegation for Edit/Delete
        document.addEventListener('click', (e) => {
            const editBtn = e.target.closest('.edit-btn');
            if (editBtn) {
                idInput.value = editBtn.dataset.id || '';
                nameInput.value = editBtn.dataset.username || '';
                roleInput.value = (editBtn.dataset.role || 'user').toLowerCase();
                passInput.value = '';
                submitBtn.disabled = false;
                submitBtn.style.opacity = '';
                openModal();
                return;
            }
            const delBtn = e.target.closest('.delete-btn');
            if (delBtn) {
                const uid = delBtn.dataset.id;
                const uname = delBtn.dataset.username || 'this user';
                Swal.fire({
                    title: 'Delete User',
                    text: 'Are you sure you want to delete "' + uname + '"?',
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonColor: '#ff6b6b',
                    cancelButtonColor: '#667eea',
                    confirmButtonText: 'Delete'
                }).then((r)=>{
                    if (r.isConfirmed) window.location.href = '/admin/delete-user/' + uid;
                });
            }
        });
    </script>
</body>
</html>
"""

# Path to SQLite DB file
DB_PATH = os.path.join(os.path.dirname(__file__), 'pyrosense_db.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def check_admin_auth():
    """Check if user is logged in as admin"""
    return session.get('role') == 'admin'

@app.route('/admin')
def admin_panel():
    """Main admin panel dashboard"""
    if not check_admin_auth():
        return redirect(f'{LOGIN_BASE}/login')
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get all users (remove Email)
        c.execute("SELECT UserID, Username, UserRole FROM Users ORDER BY UserID")
        users = c.fetchall()
        
        # Get stats
        c.execute("SELECT COUNT(*) as total FROM Users")
        total_users = c.fetchone()['total']
        
        c.execute("SELECT COUNT(*) as admin_count FROM Users WHERE UserRole = 'admin'")
        admin_users = c.fetchone()['admin_count']
        
        regular_users = total_users - admin_users
        
        stats = {
            'total_users': total_users,
            'admin_users': admin_users,
            'regular_users': regular_users
        }
        
        conn.close()

        # Resolve fire.svg path for header
        fire_icon = None
        try:
            candidates = ['icon/fire.svg', 'icons/fire.svg', 'fire.svg']
            for rel in candidates:
                if os.path.exists(os.path.join(app.static_folder, *rel.split('/'))):
                    fire_icon = rel
                    break
        except Exception:
            fire_icon = None

        # Pull query-string messages so SweetAlert can render
        return render_template_string(
            ADMIN_TEMPLATE,
            users=users,
            stats=stats,
            current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            session=session,
            success=request.args.get('success'),
            error=request.args.get('error'),
            warning=request.args.get('warning'),
            notice=request.args.get('notice'),
            fire_icon=fire_icon
        )
    except Exception as e:
        print("Admin panel error:", e, file=sys.stderr)
        traceback.print_exc()
        return f"Database error: {e}", 500

@app.route('/admin/create-user', methods=['POST'])
def create_user():
    """Create a new user"""
    if not check_admin_auth():
        return redirect(f'{LOGIN_BASE}/login')
    
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', 'user')
    
    if not username or not password:
        return redirect('/admin?error=Username and password are required')
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Check if username already exists
        c.execute("SELECT UserID FROM Users WHERE Username = ?", (username,))
        if c.fetchone():
            conn.close()
            return redirect('/admin?error=Username already exists')
        
        # Insert new user (no Email)
        c.execute("INSERT INTO Users (Username, Password, UserRole) VALUES (?, ?, ?)",
                 (username, password, role))
        conn.commit()
        conn.close()
        
        return redirect('/admin?success=User created successfully')
    except Exception as e:
        print("Create user error:", e, file=sys.stderr)
        traceback.print_exc()
        return redirect('/admin?error=Failed to create user')

@app.route('/admin/edit-user', methods=['POST'])
def edit_user():
    """Edit an existing user"""
    if not check_admin_auth():
        return redirect(f'{LOGIN_BASE}/login')
    
    user_id = request.form.get('user_id')
    username = request.form.get('username', '').strip()
    role = request.form.get('role', 'user')
    password = request.form.get('password', '').strip()
    
    if not user_id or not username:
        return redirect('/admin?error=User ID and username are required')
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Update user (no Email)
        if password:
            c.execute("UPDATE Users SET Username = ?, UserRole = ?, Password = ? WHERE UserID = ?",
                     (username, role, password, user_id))
        else:
            c.execute("UPDATE Users SET Username = ?, UserRole = ? WHERE UserID = ?",
                     (username, role, user_id))
        
        conn.commit();
        conn.close();
        
        return redirect('/admin?success=User updated successfully')
    except Exception as e:
        print("Edit user error:", e, file=sys.stderr)
        traceback.print_exc()
        return redirect('/admin?error=Failed to update user')

@app.route('/admin/delete-user/<int:user_id>')
def delete_user(user_id):
    """Delete a user"""
    if not check_admin_auth():
        return redirect(f'{LOGIN_BASE}/login')
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Don't allow deleting the admin user
        c.execute("SELECT Username FROM Users WHERE UserID = ?", (user_id,))
        user = c.fetchone()
        if user and user['Username'] == 'admin':
            conn.close()
            return redirect('/admin?error=Cannot delete admin user')
        
        # Delete user
        c.execute("DELETE FROM Users WHERE UserID = ?", (user_id,))
        conn.commit()
        conn.close()
        
        return redirect('/admin?success=User deleted successfully')
    except Exception as e:
        print("Delete user error:", e, file=sys.stderr)
        traceback.print_exc()
        return redirect('/admin?error=Failed to delete user')

@app.route('/logout')
def logout():
    """Logout and redirect to main login"""
    session.clear()
    resp = redirect(f'{LOGIN_BASE}/login')
    # Explicitly drop the session cookie for this host
    resp.delete_cookie(app.config.get('SESSION_COOKIE_NAME', 'session'), path='/')
    return resp

# Disable caching so back button won't show stale authenticated pages
@app.after_request
def add_no_cache_headers(resp):
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5003, debug=True)

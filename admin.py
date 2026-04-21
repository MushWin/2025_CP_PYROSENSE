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
LOGIN_BASE = os.environ.get('PYROSENSE_LOGIN_BASE', 'http://192.168.1.110:5000')
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
        @font-face {
            font-family: 'Source Sans 3';
            src: url('/static/fonts/Source_Sans_3/static/SourceSans3-Bold.ttf') format('truetype');
            font-weight: 700;
            font-style: normal;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        html, body { height: 100%; }
        body {
            font-family: 'Source Sans 3', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-image: url('/static/login background.jpg');
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
            color: #333;
            min-height: 100vh;
        }

        .admin-overlay {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            min-height: 100vh;
        }

        /* Header */
        header {
            background: linear-gradient(135deg, #7C0000 0%, #3E0000 50%, #2b2b2b 100%);
            color: white;
            padding: 20px 0;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        .header-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            width: 100%;
            padding: 0 32px;
        }
        .header-left { display: flex; align-items: center; gap: 16px; }
        .header-logo {
            width: 50px; height: 50px;
            background: rgba(255,255,255,0.2);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.8rem;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            border: 2px solid rgba(255,255,255,0.3);
        }
        .header-title { font-size: 1.8rem; font-weight: 700; color: white; letter-spacing: -0.5px; text-shadow: 0 2px 4px rgba(0,0,0,0.3); }
        .header-subtitle { font-size: 0.85rem; opacity: 0.85; font-weight: 300; color: white; }
        .header-right { display: flex; align-items: center; gap: 14px; }
        .user-info-text { color: white; font-weight: 600; font-size: 0.95rem; }
        .logout-btn {
            display: inline-flex; align-items: center; gap: 8px;
            padding: 10px 20px;
            border-radius: 999px;
            background: rgba(214, 40, 40, 0.4);
            color: white; text-decoration: none;
            font-weight: 600; font-size: 0.9rem;
            border: 1px solid rgba(255,255,255,0.3);
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
        }
        .logout-btn:hover { background: rgba(255,255,255,0.2); transform: translateY(-1px); }

        /* Page */
        .page { max-width: 1180px; margin: 0 auto; padding: 32px 24px 64px; }

        .page-title {
            text-align: center;
            font-size: 1.6rem; font-weight: 700;
            color: #7C0000;
            margin-bottom: 20px;
        }

        /* Stats */
        .stats-row { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
        .stat-card {
            flex: 1; min-width: 140px;
            background: white;
            border-radius: 16px;
            padding: 18px 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            border-left: 4px solid #7C0000;
        }
        .stat-value { font-size: 2rem; font-weight: 700; color: #7C0000; }
        .stat-label { font-size: 0.85rem; color: #666; font-weight: 600; margin-top: 4px; }

        /* Tabs */
        .nav-card {
            background: white;
            border-radius: 999px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            padding: 8px;
            display: flex; gap: 8px; justify-content: center;
            margin: 0 auto 28px;
            width: fit-content;
            border: 1px solid rgba(124,0,0,0.15);
        }
        .nav-btn {
            border: none; cursor: pointer;
            display: flex; align-items: center; gap: 8px;
            padding: 11px 22px;
            border-radius: 999px;
            font-weight: 700;
            font-family: 'Source Sans 3', 'Segoe UI', sans-serif;
            font-size: 0.95rem;
            background: transparent;
            color: #7C0000;
            transition: background 0.2s, color 0.2s;
        }
        .nav-btn.active {
            background: linear-gradient(135deg, #7C0000 0%, #3E0000 100%);
            color: white;
            box-shadow: 0 4px 12px rgba(124,0,0,0.3);
        }

        /* Cards */
        .content-card {
            background: white;
            border-radius: 20px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
            overflow: hidden;
            margin-bottom: 28px;
        }
        .card-header {
            background: #1a1a1a;
            padding: 16px 24px;
            display: flex; align-items: center; gap: 10px;
        }
        .card-header-title {
            font-size: 1.05rem; font-weight: 700;
            color: white;
            font-family: 'Source Sans 3', 'Segoe UI', sans-serif;
        }
        .card-body { padding: 24px; }

        /* Table */
        .table-wrap { width: 100%; overflow-x: auto; }
        .users-table { width: 100%; border-collapse: collapse; min-width: 820px; }
        .users-table thead th {
            text-align: left; padding: 12px 14px;
            background: #f9f9f9;
            color: #7C0000;
            font-weight: 700;
            border-bottom: 2px solid #f0e4e4;
            font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.5px;
        }
        .users-table tbody td {
            padding: 12px 14px;
            border-bottom: 1px solid #f5f5f5;
            color: #333;
            font-size: 0.92rem;
        }
        .users-table tbody tr:hover { background: #fdf8f8; }

        /* Badges */
        .role-badge {
            display: inline-block; padding: 4px 12px; border-radius: 999px;
            font-size: 0.78rem; font-weight: 700; letter-spacing: 0.5px;
        }
        .role-admin { background: #ffd4d4; color: #7C0000; }
        .role-user  { background: #d5f2e0; color: #1f7e49; }

        /* Buttons */
        .actions { display: flex; gap: 8px; flex-wrap: wrap; }
        .btn {
            display: inline-flex; align-items: center; gap: 6px;
            border: none; cursor: pointer; border-radius: 10px;
            padding: 8px 14px;
            font-weight: 700; font-size: 0.85rem;
            font-family: 'Source Sans 3', 'Segoe UI', sans-serif;
            transition: all 0.2s ease;
        }
        .btn:hover { transform: translateY(-1px); box-shadow: 0 4px 10px rgba(0,0,0,0.15); }
        .btn-primary { background: linear-gradient(135deg, #7C0000, #3E0000); color: white; }
        .btn-warning { background: #e67e22; color: white; }
        .btn-danger  { background: #c0392b; color: white; }

        /* Forms */
        .form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px 24px; }
        .form-group { display: flex; flex-direction: column; gap: 6px; }
        .form-group label { font-weight: 700; color: #7C0000; font-size: 0.9rem; }
        .input, select {
            width: 100%; padding: 11px 14px;
            border-radius: 10px;
            border: 2px solid #e8d5d5;
            background: #fdfafa;
            font-size: 0.95rem;
            font-family: 'Source Sans 3', 'Segoe UI', sans-serif;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }
        .input:focus, select:focus {
            border-color: #7C0000;
            box-shadow: 0 0 0 3px rgba(124,0,0,0.12);
        }

        /* Modal */
        .overlay {
            position: fixed; inset: 0;
            background: rgba(6,9,31,0.45);
            opacity: 0; pointer-events: none;
            transition: opacity 0.2s; z-index: 999;
        }
        .overlay.show { opacity: 1; pointer-events: auto; }
        .modal {
            position: fixed; inset: 0;
            display: flex; align-items: center; justify-content: center;
            z-index: 1000; pointer-events: none;
        }
        .modal-card {
            width: min(95vw, 540px);
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.2);
            overflow: hidden;
            transform: translateY(14px) scale(.97);
            opacity: 0;
            transition: transform 0.2s, opacity 0.2s;
        }
        .modal-header {
            background: #1a1a1a;
            padding: 16px 20px;
            display: flex; align-items: center; justify-content: space-between;
        }
        .modal-title { font-weight: 700; color: white; font-size: 1.05rem; }
        .modal-body { padding: 20px; }
        .modal.show { pointer-events: auto; }
        .modal.show .modal-card { transform: translateY(0) scale(1); opacity: 1; }

        @media (max-width: 720px) {
            .form-grid { grid-template-columns: 1fr; }
            .stats-row { flex-direction: column; }
            .header-container { flex-wrap: wrap; gap: 10px; }
        }



.header-center {
    display: flex;
    justify-content: center;
    flex: 1;
}

.top-nav {
    display: inline-flex;
    align-items: center;
    gap: 14px;
    padding: 8px 14px;
    border-radius: 999px;
    background: rgba(255,255,255,0.10);
    border: 1px solid rgba(255,255,255,0.22);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
    backdrop-filter: blur(10px);
}

.top-nav-link {
    text-decoration: none;
    color: rgba(255,255,255,0.75);
    font-weight: 700;
    font-size: 0.95rem;
    padding: 12px 26px;
    border-radius: 999px;
    transition: all 0.25s ease;
    letter-spacing: 0.3px;
}

.top-nav-link:hover {
    color: white;
}

.top-nav-link.active {
    background: linear-gradient(180deg, #f4f4f4 0%, #dcdcdc 100%);
    color: #1d1d1d;
    box-shadow: 0 4px 12px rgba(0,0,0,0.20);
}

.top-nav-sep {
    width: 1px;
    height: 28px;
    background: rgba(255,255,255,0.25);
}

@media (max-width: 900px) {
    .header-container {
        gap: 12px;
    }

    .header-center {
        order: 3;
        width: 100%;
        justify-content: center;
        margin-top: 8px;
    }

    .top-nav-link {
        padding: 10px 18px;
        font-size: 0.9rem;
    }
}


    </style>
</head>
<body>
<div class="admin-overlay">
    <header>
        <div class="header-container">
            <div class="header-left">
                <div class="header-logo">🔥</div>
                <div>
                    <div class="header-title">PYROSENSE</div>
                    <div class="header-subtitle">Admin Control Panel</div>
                </div>
            </div>


<div class="header-center">
    <nav class="top-nav">
        <a href="http://192.168.1.110:5002/" class="top-nav-link">DASHBOARD</a>
        <span class="top-nav-sep" aria-hidden="true"></span>
        <a href="http://192.168.1.110:5001/history" class="top-nav-link">HISTORY</a>
    </nav>
</div>

            <div class="header-right">
                <span class="user-info-text"><i class="fa-solid fa-user" style="margin-right:6px;"></i>Welcome, {{ session.name }}!</span>
               <a href="/logout" class="logout-btn" id="logoutBtn"><i class="fa-solid fa-right-from-bracket"></i> Logout</a>            </div>
        </div>
    </header>

    <div class="page">
        <div class="page-title"><i class="fa-solid fa-shield-halved" style="margin-right:8px;"></i>User Management</div>

        <!-- Stats -->
        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-value">{{ stats.total_users }}</div>
                <div class="stat-label"><i class="fa-solid fa-users" style="margin-right:4px;"></i>Total Users</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.admin_users }}</div>
                <div class="stat-label"><i class="fa-solid fa-user-shield" style="margin-right:4px;"></i>Admins</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.regular_users }}</div>
                <div class="stat-label"><i class="fa-solid fa-user" style="margin-right:4px;"></i>Regular Users</div>
            </div>
        </div>

        <div class="nav-card">
            <button class="nav-btn active" id="nav-users"><i class="fa-solid fa-users"></i> View Users</button>
            <button class="nav-btn" id="nav-create"><i class="fa-solid fa-user-plus"></i> Add New User</button>
        </div>

        <!-- Users Table -->
        <section id="users-section" class="content-card">
            <div class="card-header">
                <i class="fa-solid fa-users" style="color:rgba(255,255,255,0.85);"></i>
                <span class="card-header-title">Registered Users</span>
            </div>
            <div class="card-body">
                <div class="table-wrap">
                    <table class="users-table">
                        <thead>
                            <tr>
                                <th style="width:50px">#</th>
                                <th>Full Name</th>
                                <th>Username</th>
                                <th>Email</th>
                                <th>Phone</th>
                                <th style="width:90px">Role</th>
                                <th style="width:190px">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for user in users %}
                            <tr>
                                <td>{{ user.UserID }}</td>
                                <td>{{ user.FullName or '—' }}</td>
                                <td>{{ user.Username }}</td>
                                <td>{{ user.Email or '—' }}</td>
                                <td>{{ user.PhoneNumber or '—' }}</td>
                                <td><span class="role-badge role-{{ user.UserRole|lower }}">{{ user.UserRole|upper }}</span></td>
                                <td>
                                    <div class="actions">
                                        <button
                                            class="btn btn-warning edit-btn"
                                            data-id="{{ user.UserID }}"
                                            data-username="{{ user.Username|e }}"
                                            data-fullname="{{ (user.FullName or '')|e }}"
                                            data-email="{{ (user.Email or '')|e }}"
                                            data-phone="{{ (user.PhoneNumber or '')|e }}"
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
            </div>
        </section>

        <!-- Create User -->
        <section id="create-section" class="content-card" style="display:none;">
            <div class="card-header">
                <i class="fa-solid fa-user-plus" style="color:rgba(255,255,255,0.85);"></i>
                <span class="card-header-title">Add New User</span>
            </div>
            <div class="card-body">
                <form method="post" action="/admin/create-user">
                    <div class="form-grid">
                        <div class="form-group">
                            <label for="full_name">Full Name</label>
                            <input class="input" type="text" id="full_name" name="full_name" placeholder="e.g. Juan Dela Cruz">
                        </div>
                        <div class="form-group">
                            <label for="username">Username <span style="color:#c0392b">*</span></label>
                            <input class="input" type="text" id="username" name="username" required>
                        </div>
                        <div class="form-group">
                            <label for="email">Email</label>
                            <input class="input" type="email" id="email" name="email" placeholder="user@example.com">
                        </div>
                        <div class="form-group">
                            <label for="password">Password <span style="color:#c0392b">*</span></label>
                            <input class="input" type="password" id="password" name="password" required>
                        </div>
                        <input type="hidden" name="role" value="user">
                    </div>
                    <div style="margin-top:20px;">
                        <button type="submit" class="btn btn-primary"><i class="fa-solid fa-user-plus"></i> Create User</button>
                    </div>
                </form>
            </div>
        </section>
    </div>

    <!-- Edit Modal -->
    <div class="overlay" id="overlay"></div>
    <div class="modal" id="edit-modal" aria-hidden="true">
        <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="edit-title">
            <div class="modal-header">
                <span class="modal-title" id="edit-title"><i class="fa-solid fa-pen" style="margin-right:8px;"></i>Edit User</span>
                <button type="button" id="btn-cancel-x" style="background:none;border:none;color:rgba(255,255,255,0.7);cursor:pointer;font-size:1.2rem;"><i class="fa-solid fa-xmark"></i></button>
            </div>
            <div class="modal-body">
                <form method="post" action="/admin/edit-user" id="edit-form">
                    <input type="hidden" id="edit-user-id" name="user_id">
                    <div class="form-grid" style="gap:14px 20px;">
                        <div class="form-group">
                            <label for="edit-fullname">Full Name</label>
                            <input class="input" type="text" id="edit-fullname" name="full_name">
                        </div>
                        <div class="form-group">
                            <label for="edit-username">Username <span style="color:#c0392b">*</span></label>
                            <input class="input" type="text" id="edit-username" name="username" required>
                        </div>
                        <div class="form-group">
                            <label for="edit-email">Email</label>
                            <input class="input" type="email" id="edit-email" name="email">
                        </div>
                        <input type="hidden" name="role" value="user">
                    </div>
                    <div class="actions" style="margin-top:16px;">
                        <button type="submit" class="btn btn-primary"><i class="fa-solid fa-floppy-disk"></i> Save Changes</button>
                        <button type="button" class="btn btn-danger" id="btn-cancel"><i class="fa-solid fa-xmark"></i> Cancel</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>

    <script>
        // SweetAlert flashes
        {% if error %} Swal.fire({icon:'error', title:'Error', text: {{ error|tojson }}, confirmButtonColor:'#7C0000'}); {% endif %}
        {% if success %} Swal.fire({icon:'success', title:'Success', text: {{ success|tojson }}, confirmButtonColor:'#7C0000'}); {% endif %}
        {% if warning %} Swal.fire({icon:'warning', title:'Warning', text: {{ warning|tojson }}, confirmButtonColor:'#7C0000'}); {% endif %}
        {% if notice %} Swal.fire({icon:'info', title:'Notice', text: {{ notice|tojson }}, confirmButtonColor:'#7C0000'}); {% endif %}

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
        }
        navUsers.addEventListener('click', () => showSection('users'));
        navCreate.addEventListener('click', () => showSection('create'));

        // Modal helpers
        const overlay = document.getElementById('overlay');
        const modal = document.getElementById('edit-modal');
        const form = document.getElementById('edit-form');
        const submitBtn = form.querySelector('button[type="submit"]');
        function openModal() {
            overlay.classList.add('show');
            modal.classList.add('show');
            document.body.style.overflow = 'hidden';
        }
        function closeModal() {
            overlay.classList.remove('show');
            modal.classList.remove('show');
            document.body.style.overflow = '';
        }
        function hardResetUI() {
            overlay?.classList.remove('show');
            modal?.classList.remove('show');
            document.body.style.overflow = '';
        }
        hardResetUI();
        window.addEventListener('pageshow', hardResetUI);
        overlay.addEventListener('click', closeModal);
        document.getElementById('btn-cancel').addEventListener('click', closeModal);
        document.getElementById('btn-cancel-x').addEventListener('click', closeModal);
        document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
        form.addEventListener('submit', () => {
            submitBtn.disabled = true;
            submitBtn.style.opacity = '0.7';
            closeModal();
            hardResetUI();
        });

        // Edit/Delete event delegation
        document.addEventListener('click', (e) => {
            const editBtn = e.target.closest('.edit-btn');
            if (editBtn) {
                document.getElementById('edit-user-id').value = editBtn.dataset.id || '';
                document.getElementById('edit-username').value = editBtn.dataset.username || '';
                document.getElementById('edit-fullname').value = editBtn.dataset.fullname || '';
                document.getElementById('edit-email').value = editBtn.dataset.email || '';
                // role is preserved server-side; no UI field needed
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
                    confirmButtonColor: '#7C0000',
                    cancelButtonColor: '#333',
                    confirmButtonText: 'Yes, Delete'
                }).then((r) => {
                    if (r.isConfirmed) window.location.href = '/admin/delete-user/' + uid;
                });
            }
        });

const logoutBtn = document.getElementById('logoutBtn');

if (logoutBtn) {
    logoutBtn.addEventListener('click', function (e) {
        e.preventDefault();

        Swal.fire({
            title: 'Logout?',
            text: 'Are you sure you want to logout?',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#7C0000',
            cancelButtonColor: '#333',
            confirmButtonText: 'Yes, Logout',
            cancelButtonText: 'Cancel'
        }).then((result) => {
            if (result.isConfirmed) {
                window.location.href = '/logout';
            }
        });
    });
}

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
        
        # Get all users
        c.execute("SELECT UserID, Username, Email, UserRole, FullName, PhoneNumber FROM Users ORDER BY UserID")
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
    role = 'user'
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip() or None
    phone = request.form.get('phone', '').strip()

    if not username or not password:
        return redirect('/admin?error=Username and password are required')
    if len(password) < 6:
        return redirect('/admin?error=Password must be at least 6 characters')

    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT UserID FROM Users WHERE Username = ?", (username,))
        if c.fetchone():
            conn.close()
            return redirect('/admin?error=Username already exists')
        hashed = generate_password_hash(password)
        c.execute(
            "INSERT INTO Users (Username, Password, Email, UserRole, FullName, PhoneNumber) VALUES (?, ?, ?, ?, ?, ?)",
            (username, hashed, email, role, full_name, phone)
        )
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
    password = request.form.get('password', '').strip()
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip() or None
    phone = request.form.get('phone', '').strip()

    if not user_id or not username:
        return redirect('/admin?error=User ID and username are required')
    if False:
        role = 'user'

    try:
        conn = get_db_connection()
        c = conn.cursor()
        # Fetch the user's current role to preserve it (role cannot be changed from UI)
        c.execute("SELECT UserRole FROM Users WHERE UserID = ?", (user_id,))
        existing = c.fetchone()
        preserved_role = existing['UserRole'] if existing else 'user'
        if password:
            if len(password) < 6:
                conn.close()
                return redirect('/admin?error=Password must be at least 6 characters')
            hashed = generate_password_hash(password)
            c.execute(
                "UPDATE Users SET Username = ?, UserRole = ?, Password = ?, Email = ?, FullName = ?, PhoneNumber = ? WHERE UserID = ?",
                (username, preserved_role, hashed, email, full_name, phone, user_id)
            )
        else:
            c.execute(
                "UPDATE Users SET Username = ?, UserRole = ?, Email = ?, FullName = ?, PhoneNumber = ? WHERE UserID = ?",
                (username, preserved_role, email, full_name, phone, user_id)
            )
        conn.commit()
        conn.close()
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
    # Ensure DB tables exist and columns are migrated; seed default admin if none exists
    try:
        conn = get_db_connection()
        c = conn.cursor()
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
        existing_cols = [row[1] for row in c.execute("PRAGMA table_info(Users)").fetchall()]
        for col, definition in [('FullName', "TEXT DEFAULT ''"), ('PhoneNumber', "TEXT DEFAULT ''")]:
            if col not in existing_cols:
                c.execute(f"ALTER TABLE Users ADD COLUMN {col} {definition}")
        c.execute("SELECT UserID FROM Users WHERE UserRole = 'admin' LIMIT 1")
        if not c.fetchone():
            c.execute(
                "INSERT OR IGNORE INTO Users (Username, Password, Email, UserRole, FullName, PhoneNumber) VALUES (?, ?, ?, ?, ?, ?)",
                ('admin', generate_password_hash('dwin111'), 'admin@pyrosense.local', 'admin', 'System Administrator', '')
            )
        conn.commit()
        conn.close()
    except Exception as e:
        print("admin.py DB init failed:", e, file=sys.stderr)
    app.run(host='0.0.0.0', port=5003, debug=True)

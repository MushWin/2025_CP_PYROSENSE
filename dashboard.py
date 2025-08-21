#!/usr/bin/env python3
"""
PyroSense Dashboard - Python Flask Application
Advanced Fire Detection System Dashboard
"""

from flask import Flask, render_template_string, jsonify, request, redirect, session
from datetime import datetime
import random
import time
import threading
import json

app = Flask(__name__)
# Add the same secret key as login.py for shared sessions
app.secret_key = 'pyrosense_shared_secret_key'

# Global variables for dashboard state
dashboard_state = {
    'current_temperature': 34.6,
    'threshold': 70,
    'is_recording': False,
    'night_vision': False,
    'alerts_active': True,
    'auto_mode': True,
    'fire_status': 'No fire detected',
    'system_status': {
        'camera': 'Online',
        'thermal': 'OK', 
        'edge': 'Running',
        'internet': 'Connected'
    },
    'log_entries': [
        f"[{datetime.now().strftime('%m/%d/%Y %H:%M:%S')}] System initialized",
        f"[{datetime.now().strftime('%m/%d/%Y %H:%M:%S')}] Sensors online",
        f"[{datetime.now().strftime('%m/%d/%Y %H:%M:%S')}] No fire detected"
    ]
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PyroSense Dashboard - Python Edition</title>
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
      min-height: 100vh;
    }
    
    .dashboard-overlay {
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(10px);
      min-height: 100vh;
    }
    
    .dashboard-title {
      padding: 12px 20px;
      background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%);
      color: #fff;
      font-size: 14px;
      font-weight: 600;
      letter-spacing: 1px;
      text-align: center;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    header {
      background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 50%, #ffeb3b 100%);
      color: white;
      padding: 20px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.2);
      position: relative;
    }
    
    .header-container {
      display: flex;
      align-items: center;
      justify-content: space-between;
      max-width: 1200px;
      margin: 0 auto;
    }
    
    .header-left {
      display: flex;
      align-items: center;
      gap: 20px;
    }
    
    .header-logo {
      width: 50px;
      height: 50px;
      background: rgba(255, 255, 255, 0.2);
      backdrop-filter: blur(10px);
      border-radius: 15px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 2rem;
      box-shadow: 0 4px 15px rgba(0,0,0,0.2);
      border: 2px solid rgba(255, 255, 255, 0.3);
    }
    
    .header-title-section {
      text-align: left;
    }
    
    .header-title {
      margin: 0;
      font-size: 2rem;
      font-weight: 700;
      letter-spacing: -1px;
      color: white;
      text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
    
    .header-subtitle {
      margin: 0;
      font-size: 0.9rem;
      opacity: 0.9;
      font-weight: 300;
    }
    
    .header-right {
      display: flex;
      align-items: center;
      gap: 15px;
    }
    
    .badge {
      padding: 8px 16px;
      border-radius: 25px;
      font-size: 0.8rem;
      display: inline-block;
      font-weight: 600;
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255, 255, 255, 0.3);
    }
    
    .python-badge {
      background: rgba(255,255,255,0.2);
      color: white;
    }
    
    .system-badge {
      background: rgba(76, 175, 80, 0.3);
      color: white;
    }
    
    .history-button, .logout-button {
      padding: 8px 20px;
      border-radius: 25px;
      font-size: 0.85rem;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: all 0.3s ease;
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255, 255, 255, 0.3);
      font-weight: 600;
    }
    
    .history-button {
      background: rgba(255,255,255,0.2);
      color: white;
    }
    
    .logout-button {
      background: rgba(214, 40, 40, 0.3);
      color: white;
    }
    
    .history-button:hover, .logout-button:hover {
      background: rgba(255,255,255,0.3);
      transform: translateY(-2px);
      box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    
    main {
      max-width: 1200px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 25px;
      padding: 30px 20px;
    }
    
    .card {
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(15px);
      border-radius: 20px;
      overflow: hidden;
      box-shadow: 0 8px 25px rgba(0,0,0,0.15);
      border: 1px solid rgba(255, 255, 255, 0.2);
      transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    .card:hover {
      transform: translateY(-5px);
      box-shadow: 0 15px 35px rgba(0,0,0,0.2);
    }
    
    .card-header {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 20px;
      background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
      border-bottom: 1px solid rgba(0,0,0,0.1);
    }
    
    .card-icon {
      width: 28px;
      height: 28px;
      display: flex;
      align-items: center;
      justify-content: center;
      opacity: 0.8;
      font-size: 1.2rem;
    }
    
    .card-title {
      margin: 0;
      font-size: 1.2rem;
      font-weight: 700;
      color: #2d3748;
    }
    
    .card-content {
      padding: 25px;
      text-align: center;
    }
    
    .video-feed {
      width: 100%;
      height: 180px;
      border-radius: 15px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-size: 1rem;
      margin-bottom: 20px;
      text-align: center;
      font-weight: 600;
      box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    .status-line {
      display: flex;
      justify-content: center;
      margin-bottom: 20px;
      font-size: 1rem;
      align-items: center;
      gap: 8px;
    }
    
    .status-label {
      font-weight: 600;
      color: #4a5568;
    }
    
    .button-group {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      justify-content: center;
    }
    
    .action-button {
      background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 50%, #ffeb3b 100%);
      color: white;
      border: none;
      padding: 10px 18px;
      border-radius: 25px;
      font-size: 0.85rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.3s ease;
      font-weight: 600;
      text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
      box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3);
    }
    
    .action-button:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(255, 107, 107, 0.4);
      background: linear-gradient(135deg, #ff5252 0%, #ff9500 50%, #fdd835 100%);
    }
    
    .action-button.red {
      background: linear-gradient(135deg, #d62828 0%, #f77f00 100%);
      box-shadow: 0 4px 15px rgba(214, 40, 40, 0.3);
    }
    
    .action-button.red:hover {
      background: linear-gradient(135deg, #c52222 0%, #e67300 100%);
      box-shadow: 0 8px 25px rgba(214, 40, 40, 0.4);
    }
    
    .action-button.green {
      background: linear-gradient(135deg, #4CAF50 0%, #66bb6a 100%);
      box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);
    }
    
    .action-button.green:hover {
      background: linear-gradient(135deg, #43a047 0%, #5cb85c 100%);
      box-shadow: 0 8px 25px rgba(76, 175, 80, 0.4);
    }
    
    .temperature-display {
      font-size: 3rem;
      font-weight: 700;
      background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      text-align: center;
      margin: 15px 0;
      text-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .slider-container {
      padding: 0 15px;
      margin: 20px 0;
    }
    
    .slider {
      -webkit-appearance: none;
      width: 100%;
      height: 10px;
      background: linear-gradient(to right, #4CAF50, #ffeb3b, #ff6b6b);
      border-radius: 8px;
      cursor: pointer;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    .slider::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 24px;
      height: 24px;
      background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 100%);
      border-radius: 50%;
      border: 3px solid white;
      cursor: pointer;
      box-shadow: 0 4px 15px rgba(0,0,0,0.2);
      transition: all 0.3s ease;
    }
    
    .slider::-webkit-slider-thumb:hover {
      transform: scale(1.1);
      box-shadow: 0 6px 20px rgba(0,0,0,0.3);
    }
    
    .threshold-info {
      font-size: 1rem;
      margin-bottom: 20px;
      text-align: center;
      font-weight: 600;
      color: #4a5568;
    }
    
    .log-container {
      border: 1px solid rgba(0,0,0,0.1);
      border-radius: 15px;
      height: 180px;
      overflow-y: auto;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 0.85rem;
      background: rgba(248, 249, 250, 0.8);
      margin-bottom: 20px;
      backdrop-filter: blur(10px);
    }
    
    .log-entry {
      padding: 8px 15px;
      border-bottom: 1px solid rgba(0,0,0,0.05);
      line-height: 1.4;
      transition: background-color 0.2s ease;
    }
    
    .log-entry:hover {
      background-color: rgba(255, 255, 255, 0.5);
    }
    
    .log-entry:last-child {
      border-bottom: none;
    }
    
    .alert-panel {
      background: linear-gradient(135deg, #ff6b6b, #ffa500);
      color: white;
      padding: 20px;
      border-radius: 15px;
      text-align: center;
      font-weight: 700;
      margin-bottom: 20px;
      display: none;
      font-size: 1.2rem;
      box-shadow: 0 8px 25px rgba(255,107,107,0.4);
      text-shadow: 0 2px 4px rgba(0,0,0,0.3);
      animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
      0% { transform: scale(1); }
      50% { transform: scale(1.02); }
      100% { transform: scale(1); }
    }
    
    .alert-panel.active {
      display: block;
    }
    
    .device-status-list {
      list-style: none;
      padding: 0;
      margin: 0 0 20px 0;
    }
    
    .device-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 15px;
      padding: 12px 15px;
      border-radius: 12px;
      transition: all 0.3s ease;
      background: rgba(248, 249, 250, 0.8);
      backdrop-filter: blur(10px);
    }
    
    .device-row:hover {
      background: rgba(255, 255, 255, 0.9);
      transform: translateX(5px);
      box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .device-name {
      display: flex;
      align-items: center;
      font-weight: 600;
      color: #2d3748;
    }
    
    .status-indicator {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      display: inline-block;
      margin-right: 12px;
      box-shadow: 0 2px 8px rgba(76, 175, 80, 0.3);
    }
    
    .status-indicator.green {
      background: linear-gradient(135deg, #4CAF50 0%, #66bb6a 100%);
    }
    
    .status-value {
      font-weight: 600;
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 0.85rem;
    }
    
    .status-value.ok, .status-value.running, .status-value.connected {
      background: linear-gradient(135deg, rgba(76, 175, 80, 0.2) 0%, rgba(102, 187, 106, 0.2) 100%);
      color: #2e7d32;
    }
    
    footer {
      text-align: center;
      padding: 20px;
      font-size: 0.85rem;
      color: #6c757d;
      background: rgba(255, 255, 255, 0.8);
      backdrop-filter: blur(10px);
      margin-top: 20px;
      font-weight: 500;
    }
    
    .attribution {
      position: fixed;
      bottom: 20px;
      right: 20px;
      font-size: 12px;
      color: rgba(0, 0, 0, 0.6);
      background: rgba(255, 255, 255, 0.9);
      padding: 8px 12px;
      border-radius: 20px;
      backdrop-filter: blur(10px);
    }
    
    .attribution a {
      color: rgba(0, 0, 0, 0.7);
      text-decoration: none;
    }
    
    .attribution a:hover {
      text-decoration: underline;
    }
    
    /* Better spacing between elements */
    .card-content > *:not(:last-child) {
      margin-bottom: 15px;
    }
    
    /* Responsive design improvements */
    @media (max-width: 768px) {
      main {
        grid-template-columns: 1fr;
        padding: 20px 15px;
        gap: 20px;
      }
      
      .header-container {
        flex-direction: column;
        gap: 15px;
        text-align: center;
      }
      
      .header-right {
        flex-wrap: wrap;
        justify-content: center;
      }
      
      .card[style*="grid-column: span 2"] {
        grid-column: span 1;
      }
    }
  </style>
</head>
<body>
  <div class="dashboard-overlay">
    <div class="dashboard-title">DASHBOARD</div>
    <header>
      <div class="header-container">
        <div class="header-left">
          <div class="header-logo">🔥</div>
          <div class="header-title-section">
            <h1 class="header-title">PYROSENSE</h1>
            <p class="header-subtitle">Advanced Fire Detection System - Python Edition</p>
          </div>
        </div>
        <div class="header-right">
          <span class="badge python-badge">Made with Python Flask</span>
          <span class="badge system-badge">System Online</span>
          <a href="/history" class="history-button">📊 HISTORY</a>
          <a href="/logout" class="logout-button">🚪 LOGOUT</a>
        </div>
      </div>
    </header>
    
    <main>
      <!-- Live Camera Feed -->
      <div class="card">
        <div class="card-header">
          <div class="card-icon">📹</div>
          <h2 class="card-title">Live Camera Feed</h2>
        </div>
        <div class="card-content">
          <div class="video-feed" id="videoFeed">
            Pyrosense is scanning for fire...
          </div>
          <div class="status-line">
            <span class="status-label">Status:</span>
            <strong id="fireStatus">{{ fire_status }}</strong>
          </div>
          <div class="button-group">
            <button class="action-button" onclick="toggleRecording()" id="recordButton">
              <span>Start Recording</span>
            </button>
            <button class="action-button" onclick="takeSnapshot()">
              <span>Snapshot</span>
            </button>
            <button class="action-button" onclick="toggleNightVision()">
              <span>Thermal/RGB</span>
            </button>
          </div>
        </div>
      </div>
      
      <!-- Thermal Reading -->
      <div class="card">
        <div class="card-header">
          <div class="card-icon">🌡️</div>
          <h2 class="card-title">Thermal Reading</h2>
        </div>
        <div class="card-content">
          <div class="temperature-display" id="currentTemp">{{ current_temperature }}°C</div>
          <div class="threshold-info">Heat Threshold: <strong id="thresholdValue">{{ threshold }}°C</strong></div>
          <div class="slider-container">
            <input type="range" min="30" max="100" value="{{ threshold }}" class="slider" id="thresholdSlider" oninput="updateThreshold(this.value)">
          </div>
          <div class="button-group">
            <button class="action-button" onclick="calibrateSensor()">
              <span>Calibrate</span>
            </button>
            <button class="action-button" onclick="resetThreshold()">
              <span>Reset</span>
            </button>
          </div>
        </div>
      </div>
      
      <!-- Fire Detection Log -->
      <div class="card">
        <div class="card-header">
          <div class="card-icon">📋</div>
          <h2 class="card-title">Fire Detection Log</h2>
        </div>
        <div class="card-content">
          <div class="log-container" id="logContainer">
            {% for entry in log_entries %}
            <div class="log-entry">{{ entry }}</div>
            {% endfor %}
          </div>
          <div class="button-group">
            <button class="action-button red" onclick="clearLog()">
              <span>Clear Log</span>
            </button>
            <button class="action-button" onclick="exportLog()">
              <span>Export</span>
            </button>
          </div>
        </div>
      </div>
      
      <!-- Alert Control -->
      <div class="card">
        <div class="card-header">
          <div class="card-icon">🚨</div>
          <h2 class="card-title">Alert Control</h2>
        </div>
        <div class="card-content">
          <div class="alert-panel" id="alertPanel">⚠️ FIRE DETECTED!</div>
          <div class="button-group">
            <button class="action-button red" onclick="simulateAlert()">
              <span>Test Alert</span>
            </button>
            <button class="action-button" onclick="acknowledgeAlert()">
              <span>Acknowledge</span>
            </button>
            <button class="action-button" onclick="muteAlerts()">
              <span>Mute (5min)</span>
            </button>
          </div>
        </div>
      </div>
      
      <!-- Device Status -->
      <div class="card" style="grid-column: span 2;">
        <div class="card-header">
          <div class="card-icon">💻</div>
          <h2 class="card-title">Device Status</h2>
        </div>
        <div class="card-content">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
            <div class="device-row">
              <div class="device-name">
                <span class="status-indicator green"></span>
                <span>RGB Camera:</span>
              </div>
              <span class="status-value" id="cameraStatus">{{ system_status.camera }}</span>
            </div>
            <div class="device-row">
              <div class="device-name">
                <span class="status-indicator green"></span>
                <span>Thermal Sensor:</span>
              </div>
              <span class="status-value ok" id="thermalStatus">{{ system_status.thermal }}</span>
            </div>
            <div class="device-row">
              <div class="device-name">
                <span class="status-indicator green"></span>
                <span>Edge System:</span>
              </div>
              <span class="status-value running" id="edgeStatus">{{ system_status.edge }}</span>
            </div>
            <div class="device-row">
              <div class="device-name">
                <span class="status-indicator green"></span>
                <span>Internet:</span>
              </div>
              <span class="status-value connected" id="internetStatus">{{ system_status.internet }}</span>
            </div>
          </div>
          <div class="button-group" style="margin-top: 15px;">
            <button class="action-button red" onclick="restartSystem()">
              <span>Restart</span>
            </button>
          </div>
        </div>
      </div>
    </main>
    
    <footer>
      PyroSense 2025 © All rights reserved - Python Flask Edition
    </footer>
    
    <div class="attribution">
      <a href="https://www.freepik.com/free-vector/minimalist-background-gradient-design-style_34345006.htm">Background by AndreaCharlesta on Freepik</a>
    </div>
  </div>

  <script>
    // Dashboard state management
    let dashboardState = {
      currentTemperature: {{ current_temperature }},
      threshold: {{ threshold }},
      isRecording: {{ is_recording|lower }},
      nightVision: {{ night_vision|lower }},
      alertsActive: {{ alerts_active|lower }},
      autoMode: {{ auto_mode|lower }}
    };

    // API communication functions
    function makeRequest(endpoint, method = 'GET', data = null) {
      const options = {
        method: method,
        headers: {
          'Content-Type': 'application/json',
        }
      };
      
      if (data) {
        options.body = JSON.stringify(data);
      }
      
      return fetch(endpoint, options)
        .then(response => response.json())
        .catch(error => {
          console.error('API Error:', error);
          alert('Connection to Python server failed!');
        });
    }

    // Temperature and time updates
    function updateDashboard() {
      makeRequest('/api/status')
        .then(data => {
          if (data) {
            document.getElementById('currentTemp').textContent = data.temperature + '°C';
            document.getElementById('fireStatus').textContent = data.fire_status;
            
            // Update temperature color
            const tempElement = document.getElementById('currentTemp');
            if (data.temperature > data.threshold) {
              tempElement.style.color = '#ff0000';
              triggerFireAlert();
            } else if (data.temperature > data.threshold * 0.8) {
              tempElement.style.color = '#ff8800';
            } else {
              tempElement.style.color = '#d62828';
            }
            
            dashboardState.currentTemperature = data.temperature;
          }
        });
    }

    // Interactive functions
    function toggleRecording() {
      makeRequest('/api/toggle_recording', 'POST')
        .then(data => {
          if (data.success) {
            const button = document.getElementById('recordButton');
            if (data.is_recording) {
              button.textContent = 'Stop Recording';
              button.classList.add('red');
            } else {
              button.textContent = 'Start Recording';
              button.classList.remove('red');
            }
            addLogEntry(data.message);
          }
        });
    }

    function takeSnapshot() {
      makeRequest('/api/snapshot', 'POST')
        .then(data => {
          if (data.success) {
            addLogEntry(data.message);
            alert('📸 ' + data.message);
          }
        });
    }

    function toggleNightVision() {
      makeRequest('/api/toggle_night_vision', 'POST')
        .then(data => {
          if (data.success) {
            const videoFeed = document.getElementById('videoFeed');
            const button = event.target;
            
            if (data.night_vision) {
              videoFeed.style.background = '#1f3a1d';
              videoFeed.innerHTML = 'Python Night Vision Active';
              button.textContent = 'RGB Mode';
            } else {
              videoFeed.style.background = '#666';
              videoFeed.innerHTML = 'Pyrosense is scanning for fire...';
              button.textContent = 'Thermal/RGB';
            }
            addLogEntry(data.message);
          }
        });
    }

    function updateThreshold(value) {
      makeRequest('/api/update_threshold', 'POST', { threshold: parseInt(value) })
        .then(data => {
          if (data.success) {
            document.getElementById('thresholdValue').textContent = value + '°C';
            dashboardState.threshold = parseInt(value);
            addLogEntry(data.message);
          }
        });
    }

    function calibrateSensor() {
      makeRequest('/api/calibrate_sensor', 'POST')
        .then(data => {
          if (data.success) {
            addLogEntry(data.message);
            setTimeout(() => {
              addLogEntry('Python sensor calibration completed');
            }, 2000);
          }
        });
    }

    function resetThreshold() {
      makeRequest('/api/reset_threshold', 'POST')
        .then(data => {
          if (data.success) {
            document.getElementById('thresholdSlider').value = 70;
            document.getElementById('thresholdValue').textContent = '70°C';
            dashboardState.threshold = 70;
            addLogEntry(data.message);
          }
        });
    }

    function simulateAlert() {
      makeRequest('/api/simulate_alert', 'POST')
        .then(data => {
          if (data.success) {
            triggerFireAlert();
            addLogEntry(data.message);
          }
        });
    }

    function triggerFireAlert() {
      if (!dashboardState.alertsActive) return;
      
      const alertPanel = document.getElementById('alertPanel');
      const fireStatus = document.getElementById('fireStatus');
      
      alertPanel.style.display = 'block';
      alertPanel.classList.add('active');
      fireStatus.textContent = 'FIRE DETECTED!';
      fireStatus.style.color = '#ff0000';
      
      // Update the dashboard title
      document.querySelector('.dashboard-title').textContent = 'DASHBOARD (Test alert)';
    }

    function acknowledgeAlert() {
      makeRequest('/api/acknowledge_alert', 'POST')
        .then(data => {
          if (data.success) {
            const alertPanel = document.getElementById('alertPanel');
            const fireStatus = document.getElementById('fireStatus');
            
            alertPanel.style.display = 'none';
            alertPanel.classList.remove('active');
            fireStatus.textContent = 'Alert Acknowledged';
            fireStatus.style.color = '#ffa500';
            
            // Update the dashboard title
            document.querySelector('.dashboard-title').textContent = 'DASHBOARD (Acknowledge)';
            
            addLogEntry(data.message);
          }
        });
    }

    function muteAlerts() {
      makeRequest('/api/mute_alerts', 'POST')
        .then(data => {
          if (data.success) {
            dashboardState.alertsActive = false;
            addLogEntry(data.message);
            setTimeout(() => {
              dashboardState.alertsActive = true;
              addLogEntry('Python alerts reactivated');
            }, 300000); // 5 minutes
          }
        });
    }

    function restartSystem() {
      if (confirm('Are you sure you want to restart the system?')) {
        makeRequest('/api/restart_system', 'POST')
          .then(data => {
            if (data.success) {
              addLogEntry('System restart initiated...');
              setTimeout(() => {
                addLogEntry('System restarted successfully');
                location.reload();
              }, 3000);
            }
          });
      }
    }

    function clearLog() {
      makeRequest('/api/clear_log', 'POST')
        .then(data => {
          if (data.success) {
            document.getElementById('logContainer').innerHTML = '<div class="log-entry">' + data.message + '</div>';
            
            // Update the dashboard title
            document.querySelector('.dashboard-title').textContent = 'DASHBOARD (Clear log)';
          }
        });
    }

    function exportLog() {
      makeRequest('/api/export_log', 'POST')
        .then(data => {
          if (data.success) {
            addLogEntry(data.message);
            alert('💾 ' + data.message);
          }
        });
    }

    function addLogEntry(message) {
      const logContainer = document.getElementById('logContainer');
      const newEntry = document.createElement('div');
      newEntry.className = 'log-entry';
      newEntry.textContent = `[${new Date().toLocaleString()}] ${message}`;
      logContainer.insertBefore(newEntry, logContainer.firstChild);
      
      // Keep only last 20 entries
      while (logContainer.children.length > 20) {
        logContainer.removeChild(logContainer.lastChild);
      }
    }

    // Initialize the dashboard
    function initDashboard() {
      addLogEntry('PyroSense Dashboard initialized');
      
      // Update dashboard every 3 seconds
      setInterval(updateDashboard, 3000);
    }

    // Start the dashboard when page loads
    window.addEventListener('load', initDashboard);
  </script>
</body>
</html>
"""

# Add the forgot password template
FORGOT_PASSWORD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PyroSense - Forgot Password</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
            background-color: #121212;
            color: #f0f0f0;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .login-container {
            display: flex;
            flex: 1;
            overflow: hidden;
        }
        
        .graphic-section {
            flex: 1;
            background-color: #f2f2e6;
            overflow: hidden;
            position: relative;
        }
        
        .flames-graphic {
            height: 100%;
            width: 100%;
            background: linear-gradient(to bottom right, #f77f00, #d62828, #fcbf49);
            position: relative;
            overflow: hidden;
        }
        
        .flame-shape {
            position: absolute;
            background: #2b2d2f;
            clip-path: polygon(30% 0%, 70% 0%, 100% 30%, 100% 70%, 70% 100%, 30% 100%, 0% 70%, 0% 30%);
        }
        
        .flame-1 {
            width: 300px;
            height: 600px;
            top: -100px;
            left: 50px;
            transform: rotate(45deg);
        }
        
        .flame-2 {
            width: 400px;
            height: 400px;
            bottom: -100px;
            left: -100px;
            transform: rotate(25deg);
        }
        
        .flame-3 {
            width: 200px;
            height: 600px;
            bottom: 50px;
            right: 100px;
            transform: rotate(-15deg);
        }
        
        .login-form-section {
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .login-form {
            width: 100%;
            max-width: 400px;
            padding: 20px;
        }
        
        .login-title {
            font-size: 3rem;
            font-weight: bold;
            margin-bottom: 40px;
            color: #f0f0f0;
        }
        
        .form-group {
            margin-bottom: 25px;
        }
        
        label {
            display: block;
            margin-bottom: 10px;
            font-weight: 500;
        }
        
        input[type="email"] {
            width: 100%;
            padding: 12px;
            border-radius: 5px;
            border: 1px solid #555;
            background-color: #1e1e1e;
            color: #f0f0f0;
            font-size: 16px;
            box-sizing: border-box;
        }
        
        .login-button {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 5px;
            background-color: #f77f00;
            color: white;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        
        .login-button:hover {
            background-color: #d62828;
        }
        
        .login-header {
            position: absolute;
            top: 10px;
            left: 10px;
            font-size: 14px;
            color: #888;
        }
        
        .flash-message {
            padding: 10px 15px;
            margin-bottom: 20px;
            border-radius: 5px;
            background-color: #d62828;
            color: white;
            font-weight: 500;
        }
        
        .success-message {
            padding: 10px 15px;
            margin-bottom: 20px;
            border-radius: 5px;
            background-color: #2e7d32;
            color: white;
            font-weight: 500;
        }
        
        .back-link {
            margin-top: 15px;
            text-align: center;
        }
        
        .back-link a {
            color: #888;
            text-decoration: none;
        }
        
        .back-link a:hover {
            color: #f77f00;
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="login-header">FORGOT PASSWORD</div>
    
    <div class="login-container">
        <div class="graphic-section">
            <div class="flames-graphic">
                <div class="flame-shape flame-1"></div>
                <div class="flame-shape flame-2"></div>
                <div class="flame-shape flame-3"></div>
            </div>
        </div>
        
        <div class="login-form-section">
            <div class="login-form">
                <h1 class="login-title">Pyrosense</h1>
                <p>Enter your admin email to reset your password.</p>
                
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
                    
                    <button type="submit" class="login-button">Reset Password</button>
                </form>
                
                <div class="back-link">
                    <a href="/login">Back to login</a>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

def simulate_temperature_variation():
    """Simulate realistic temperature changes"""
    variation = (random.random() - 0.5) * 2  # ±1 degree variation
    dashboard_state['current_temperature'] = max(20, min(100, 
        dashboard_state['current_temperature'] + variation))
    
    # Check for fire conditions
    if dashboard_state['current_temperature'] > dashboard_state['threshold']:
        dashboard_state['fire_status'] = 'FIRE DETECTED!'
        add_log_entry('🚨 FIRE ALERT: High temperature detected!')
    else:
        dashboard_state['fire_status'] = 'No fire detected'

def add_log_entry(message):
    """Add a new log entry to the system"""
    timestamp = datetime.now().strftime('[%m/%d/%Y %H:%M:%S]')
    new_entry = f"{timestamp} {message}"
    dashboard_state['log_entries'].insert(0, new_entry)
    
    # Keep only last 20 entries
    if len(dashboard_state['log_entries']) > 20:
        dashboard_state['log_entries'] = dashboard_state['log_entries'][:20]

def background_temperature_monitor():
    """Background thread for temperature monitoring"""
    while True:
        simulate_temperature_variation()
        time.sleep(3)  # Update every 3 seconds

# Start background monitoring
temperature_thread = threading.Thread(target=background_temperature_monitor, daemon=True)
temperature_thread.start()

@app.route('/')
def dashboard():
    """Main dashboard page"""
    # Check if user is authenticated
    if not session.get('user'):
        # If no user in session, redirect to login page
        return redirect('http://localhost:5000/login')
    
    template_data = {
        'current_temperature': round(dashboard_state['current_temperature'], 1),
        'threshold': dashboard_state['threshold'],
        'is_recording': dashboard_state['is_recording'],
        'night_vision': dashboard_state['night_vision'],
        'alerts_active': dashboard_state['alerts_active'],
        'auto_mode': dashboard_state['auto_mode'],
        'fire_status': dashboard_state['fire_status'],
        'system_status': dashboard_state['system_status'],
        'log_entries': dashboard_state['log_entries'][:10],  # Show only recent 10
        'last_update': datetime.now().strftime('%m/%d/%Y %H:%M:%S'),
        'username': session.get('name', 'User')  # Add username from session
    }
    return render_template_string(HTML_TEMPLATE, **template_data)

@app.route('/api/status')
def get_status():
    """Get current system status"""
    # Check if user is authenticated for API calls too
    if not session.get('user'):
        return jsonify({'error': 'Authentication required'}), 401
        
    return jsonify({
        'temperature': round(dashboard_state['current_temperature'], 1),
        'threshold': dashboard_state['threshold'],
        'fire_status': dashboard_state['fire_status'],
        'system_status': dashboard_state['system_status'],
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/toggle_recording', methods=['POST'])
def toggle_recording():
    """Toggle recording state"""
    dashboard_state['is_recording'] = not dashboard_state['is_recording']
    message = 'Python recording started' if dashboard_state['is_recording'] else 'Python recording stopped'
    add_log_entry(message)
    
    return jsonify({
        'success': True,
        'is_recording': dashboard_state['is_recording'],
        'message': message
    })

@app.route('/api/snapshot', methods=['POST'])
def take_snapshot():
    """Take a snapshot"""
    add_log_entry('Python snapshot captured')
    return jsonify({
        'success': True,
        'message': 'Snapshot saved to Python gallery!'
    })

@app.route('/api/toggle_night_vision', methods=['POST'])
def toggle_night_vision():
    """Toggle night vision mode"""
    dashboard_state['night_vision'] = not dashboard_state['night_vision']
    message = 'Python night vision enabled' if dashboard_state['night_vision'] else 'Python day vision enabled'
    add_log_entry(message)
    
    return jsonify({
        'success': True,
        'night_vision': dashboard_state['night_vision'],
        'message': message
    })

@app.route('/api/update_threshold', methods=['POST'])
def update_threshold():
    """Update temperature threshold"""
    data = request.get_json()
    threshold = data.get('threshold', 70)
    dashboard_state['threshold'] = threshold
    message = f'Python threshold updated to {threshold}°C'
    add_log_entry(message)
    
    return jsonify({
        'success': True,
        'threshold': threshold,
        'message': message
    })

@app.route('/api/calibrate_sensor', methods=['POST'])
def calibrate_sensor():
    """Start sensor calibration"""
    add_log_entry('Python sensor calibration started...')
    return jsonify({
        'success': True,
        'message': 'Python sensor calibration started...'
    })

@app.route('/api/reset_threshold', methods=['POST'])
def reset_threshold():
    """Reset threshold to default"""
    dashboard_state['threshold'] = 70
    message = 'Python threshold reset to default (70°C)'
    add_log_entry(message)
    
    return jsonify({
        'success': True,
        'threshold': 70,
        'message': message
    })

@app.route('/api/simulate_alert', methods=['POST'])
def simulate_alert():
    """Simulate fire alert"""
    message = 'Python test alert triggered'
    add_log_entry(message)
    
    return jsonify({
        'success': True,
        'message': message
    })

@app.route('/api/acknowledge_alert', methods=['POST'])
def acknowledge_alert():
    """Acknowledge fire alert"""
    message = 'Python alert acknowledged by user'
    add_log_entry(message)
    
    return jsonify({
        'success': True,
        'message': message
    })

@app.route('/api/mute_alerts', methods=['POST'])
def mute_alerts():
    """Mute alerts for 5 minutes"""
    dashboard_state['alerts_active'] = False
    message = 'Python alerts muted for 5 minutes'
    add_log_entry(message)
    
    return jsonify({
        'success': True,
        'message': message
    })

@app.route('/api/run_diagnostics', methods=['POST'])
def run_diagnostics():
    """Run system diagnostics"""
    return jsonify({
        'success': True,
        'checks': ['Python Camera module', 'Python Thermal sensor', 'Python Network connection', 'Python Storage space']
    })

@app.route('/api/restart_system', methods=['POST'])
def restart_system():
    """Restart system"""
    message = 'Python system restart initiated...'
    add_log_entry(message)
    
    return jsonify({
        'success': True,
        'message': message
    })

@app.route('/api/toggle_auto_mode', methods=['POST'])
def toggle_auto_mode():
    """Toggle auto mode"""
    dashboard_state['auto_mode'] = not dashboard_state['auto_mode']
    message = 'Python auto mode enabled' if dashboard_state['auto_mode'] else 'Python manual mode enabled'
    add_log_entry(message)
    
    return jsonify({
        'success': True,
        'auto_mode': dashboard_state['auto_mode'],
        'message': message
    })

@app.route('/api/clear_log', methods=['POST'])
def clear_log():
    """Clear system log"""
    dashboard_state['log_entries'] = []
    message = f'[{datetime.now().strftime("%m/%d/%Y %H:%M:%S")}] Python log cleared by user'
    dashboard_state['log_entries'].append(message)
    
    return jsonify({
        'success': True,
        'message': message
    })

@app.route('/api/export_log', methods=['POST'])
def export_log():
    """Export system log"""
    message = 'Python log export requested'
    add_log_entry(message)
    
    return jsonify({
        'success': True,
        'message': 'Python log exported to downloads folder!'
    })

@app.route('/api/emergency_shutdown', methods=['POST'])
def emergency_shutdown():
    """Emergency system shutdown"""
    message = '🛑 PYTHON EMERGENCY SHUTDOWN INITIATED'
    add_log_entry(message)
    
    return jsonify({
        'success': True,
        'message': message
    })

@app.route('/logout')
def logout():
    """Handle user logout"""
    # Clear the session
    session.clear()
    # Redirect to login page
    return redirect('http://localhost:5000/login')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle forgot password page display and form submission"""
    error = None
    success = None
    
    if request.method == 'POST':
        # No actual email sending - this is UI only demo
        email = request.form.get('email')
        
        # Simulate email sending
        add_log_entry(f'Password reset email sent to {email}')
        success = 'Password reset email sent!'
    
    return render_template_string(FORGOT_PASSWORD_TEMPLATE, error=error, success=success)

@app.route('/history')
def history():
    """Redirect to history page"""
    return redirect('http://localhost:5001')  # Redirect to history Flask app

if __name__ == '__main__':
    print("🐍 Starting PyroSense Python Flask Dashboard...")
    print("🔥 Fire Detection System - Python Edition")
    print("=" * 50)
    print("Dashboard URL: http://localhost:5002")
    print("Features:")
    print("  • Real-time temperature monitoring")
    print("  • Python-powered analytics")
    print("  • Interactive controls via Flask API")
    print("  • Background temperature simulation")
    print("To stop server: Press Ctrl+C")
    print("=" * 50)
    
    # Run the Flask development server on port 5002
    app.run(debug=True, host='0.0.0.0', port=5002)

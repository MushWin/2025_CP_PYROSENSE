#!/usr/bin/env python3
"""
PyroSense History Page - Python Flask Application
Historical Data Analysis and Management System
"""

from flask import Flask, render_template_string, jsonify, request, send_file, redirect, session
from datetime import datetime, timedelta
import random
import json
import csv
import io
import os

# Use a consistent secret key across both applications
app = Flask(__name__)
app.secret_key = 'pyrosense_shared_secret_key'  # Use the same key in both apps

# Generate sample historical data
def generate_historical_data():
    """Generate realistic historical fire detection data"""
    data = []
    base_date = datetime.now() - timedelta(days=30)
    
    for i in range(720):  # 30 days * 24 hours
        timestamp = base_date + timedelta(hours=i)
        
        # Simulate temperature patterns (higher during day, cooler at night)
        hour = timestamp.hour
        base_temp = 25 + 10 * (1 + 0.3 * random.random()) * abs(12 - hour) / 12
        temp_variation = (random.random() - 0.5) * 5
        temperature = round(base_temp + temp_variation, 1)
        
        # Simulate fire events (rare)
        fire_detected = temperature > 65 and random.random() < 0.02
        
        # Generate alert levels
        if fire_detected:
            alert_level = "High"
        elif temperature > 50:
            alert_level = "Medium"
        elif temperature > 40:
            alert_level = "Low"
        else:
            alert_level = "None"
        
        # Device status (occasionally offline)
        camera_status = "Offline" if random.random() < 0.05 else "Online"
        thermal_status = "Error" if random.random() < 0.03 else "OK"
        
        data.append({
            'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'temperature': temperature,
            'fire_detected': fire_detected,
            'alert_level': alert_level,
            'camera_status': camera_status,
            'thermal_status': thermal_status,
            'location': f"Sector {random.randint(1, 8)}",
            'confidence': round(random.uniform(0.7, 0.99), 2) if fire_detected else round(random.uniform(0.1, 0.3), 2)
        })
    
    return data

# Global historical data
historical_data = generate_historical_data()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PyroSense History - Python Edition</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 0;
      padding: 0;
      background-color: #f0e6d2;
      color: #333;
    }
    
    .history-title {
      padding: 10px 20px;
      background: #333;
      color: #fff;
      font-size: 14px;
      font-weight: normal;
    }
    
    header {
      background: linear-gradient(90deg, #d62828, #e63946);
      color: white;
      padding: 15px 20px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
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
      gap: 15px;
    }
    
    .header-logo {
      width: 45px;
      height: 45px;
      background: white;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.8rem;
      box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    .header-title-section {
      text-align: left;
    }
    
    .header-title {
      margin: 0;
      font-size: 1.5rem;
      font-weight: 700;
      letter-spacing: -0.5px;
      color: white;
    }
    
    .header-subtitle {
      margin: 0;
      font-size: 0.8rem;
      opacity: 0.9;
      font-weight: 300;
    }
    
    .header-right {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    
    .badge {
      padding: 5px 10px;
      border-radius: 20px;
      font-size: 0.75rem;
      display: inline-block;
    }
    
    .python-badge {
      background: rgba(255,255,255,0.2);
      color: white;
    }
    
    .dashboard-button {
      padding: 5px 15px;
      border-radius: 20px;
      font-size: 0.8rem;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all 0.2s ease;
      background: rgba(255,255,255,0.2);
      color: white;
    }
    
    .dashboard-button:hover {
      background: rgba(255,255,255,0.3);
    }
    
    main {
      max-width: 1200px;
      margin: 0 auto;
      padding: 20px;
    }
    
    .stats-container {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 20px;
      margin-bottom: 20px;
    }
    
    .stat-card {
      background: white;
      border-radius: 15px;
      padding: 20px;
      text-align: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    
    .stat-icon {
      font-size: 2rem;
      margin-bottom: 10px;
    }
    
    .stat-value {
      font-size: 1.8rem;
      font-weight: bold;
      color: #d62828;
      margin: 5px 0;
    }
    
    .stat-label {
      font-size: 0.9rem;
      color: #777;
    }
    
    .filters-container {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 20px;
      margin-bottom: 20px;
    }
    
    .filter-card {
      background: white;
      border-radius: 15px;
      padding: 20px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    
    .filter-title {
      font-size: 0.9rem;
      font-weight: bold;
      margin-bottom: 10px;
      display: flex;
      align-items: center;
      gap: 5px;
    }
    
    .filter-icon {
      opacity: 0.7;
    }
    
    .filter-dropdown {
      width: 100%;
      padding: 8px;
      border-radius: 5px;
      border: 1px solid #ddd;
      margin-top: 5px;
      text-align: center;
      box-sizing: border-box;
    }
    
    .date-picker {
      width: 100%;
      display: flex;
      justify-content: center; /* Center the picker in its container */
    }
    
    .calendar-dropdown {
      position: relative;
      display: inline-block;
      width: 100%;
      text-align: center;
    }
    
    .calendar-dropdown-content {
      display: none;
      position: absolute;
      background-color: white;
      box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);
      z-index: 1;
      border-radius: 5px;
      padding: 10px;
      width: 280px;
      left: 50%;
      transform: translateX(-50%);
    }
    
    .calendar-dropdown-content.show {
      display: block;
    }
    
    .calendar {
      width: 100%;
      border-collapse: collapse;
    }
    
    .calendar th, .calendar td {
      text-align: center;
      padding: 6px;
    }
    
    .calendar th {
      background: #f8f8f8;
    }
    
    .calendar td:hover {
      background: #f0f0f0;
      cursor: pointer;
    }
    
    .calendar .selected {
      background: #d62828;
      color: white;
      border-radius: 50%;
    }
    
    .month-selector {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }
    
    .month-arrow {
      cursor: pointer;
      user-select: none;
    }
    
    .calendar-buttons {
      display: flex;
      justify-content: space-between;
      margin-top: 10px;
    }
    
    .calendar-button {
      padding: 8px 15px;
      border: none;
      border-radius: 5px;
      cursor: pointer;
    }
    
    .cancel-button {
      background: #f1f1f1;
    }
    
    .apply-button {
      background: #4c52af;
      color: white;
    }
    
    .actions-container {
      display: flex;
      gap: 10px;
      margin-bottom: 20px;
      justify-content: center;
    }
    
    .action-button {
      background: #f77f00;
      color: white;
      border: none;
      padding: 8px 15px;
      border-radius: 20px;
      font-size: 0.8rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 5px;
    }
    
    .action-button:hover {
      background: #e67300;
    }
    
    .action-button.red {
      background: #d62828;
    }
    
    .action-button.green {
      background: #4CAF50;
    }
    
    .action-button.gray {
      background: #777;
    }
    
    .records-card {
      background: white;
      border-radius: 15px;
      overflow: hidden;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
      margin-bottom: 20px;
    }
    
    .records-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 15px 20px;
      background: #f8f8f8;
      border-bottom: 1px solid #eee;
    }
    
    .records-title {
      margin: 0;
      font-size: 1.1rem;
      font-weight: 600;
    }
    
    .records-count {
      font-size: 0.8rem;
      background: #eee;
      padding: 2px 8px;
      border-radius: 10px;
    }
    
    .records-table {
      width: 100%;
      border-collapse: collapse;
    }
    
    .records-table th {
      padding: 10px;
      background: #f8f8f8;
      text-align: left;
      font-size: 0.9rem;
      border-bottom: 1px solid #eee;
    }
    
    .records-table td {
      padding: 10px;
      border-bottom: 1px solid #eee;
      font-size: 0.9rem;
    }
    
    .records-table tr:last-child td {
      border-bottom: none;
    }
    
    .status-indicator {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      display: inline-block;
      margin-right: 5px;
    }
    
    .status-green {
      background: #4CAF50;
    }
    
    .status-red {
      background: #f44336;
    }
    
    .status-text {
      font-weight: 500;
    }
    
    .status-text.ok {
      color: #4CAF50;
    }
    
    .status-text.offline {
      color: #f44336;
    }
    
    .pagination {
      display: flex;
      justify-content: center;
      margin-top: 20px;
    }
    
    .pagination-button {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      margin: 0 5px;
      background: #eee;
      border: none;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
    }
    
    .pagination-button.active {
      background: #e63946;
      color: white;
    }
    
    footer {
      text-align: center;
      padding: 10px;
      font-size: 0.8rem;
      color: #777;
      border-top: 1px solid #eee;
      background: transparent;
      margin-top: 20px;
    }
    
    .date-range-container {
      display: flex;
      gap: 10px;
      margin-bottom: 10px;
    }

    .date-input-group {
      flex: 1;
    }

    .date-input-group label {
      display: block;
      margin-bottom: 5px;
      font-size: 0.8rem;
      color: #666;
    }

    .range-selector-header {
      margin-bottom: 10px;
      text-align: center;
    }

    .range-mode {
      display: flex;
      background: #f1f1f1;
      border-radius: 5px;
      overflow: hidden;
    }

    .range-mode span {
      flex: 1;
      padding: 8px;
      cursor: pointer;
      font-size: 0.8rem;
    }

    .range-mode .active-mode {
      background: #4c52af;
      color: white;
    }
  </style>
</head>
<body>
  <div class="history-title">HISTORY</div>
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
        <a href="http://localhost:5000" class="dashboard-button">Back to Dashboard</a>
      </div>
    </div>
  </header>
  
  <main>
    <!-- Stats Section -->
    <div class="stats-container">
      <div class="stat-card">
        <div class="stat-icon">🔥</div>
        <div class="stat-value">{{ stats.fire_events }}</div>
        <div class="stat-label">Total Fire Events</div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon">🌡️</div>
        <div class="stat-value">{{ stats.avg_temperature }}°C</div>
        <div class="stat-label">Average Temperature</div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon">⚠️</div>
        <div class="stat-value">{{ stats.total_alerts }}</div>
        <div class="stat-label">Total Alerts</div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon">⏱️</div>
        <div class="stat-value">{{ stats.uptime }}%</div>
        <div class="stat-label">System Uptime</div>
      </div>
    </div>
    
    <!-- Filters Section -->
    <div class="filters-container">
      <div class="filter-card">
        <div class="filter-title">
          <span class="filter-icon">📅</span>
          <span>Date Range</span>
        </div>
        <div class="date-picker">
          <div class="date-range-container">
            <div class="date-input-group">
              <label for="startDate">From:</label>
              <input type="text" class="filter-dropdown" id="startDateDisplay" readonly placeholder="Start date" value="{{ start_date }}">
            </div>
            <div class="date-input-group">
              <label for="endDate">To:</label>
              <input type="text" class="filter-dropdown" id="endDateDisplay" readonly placeholder="End date" value="{{ end_date }}">
            </div>
          </div>
          <div class="calendar-dropdown" id="calendarDropdown">
            <div class="calendar-dropdown-content" id="calendarContent">
              <div class="range-selector-header">
                <div class="range-mode">
                  <span id="startDateMode" class="active-mode">Select Start Date</span>
                  <span id="endDateMode">Select End Date</span>
                </div>
              </div>
              <div class="month-selector">
                <span class="month-arrow" id="prevMonth">&#9664;</span>
                <span id="currentMonth">{{ current_month }}</span>
                <span class="month-arrow" id="nextMonth">&#9654;</span>
              </div>
              <table class="calendar" id="calendarTable">
                <thead>
                  <tr>
                    <th>Mo</th>
                    <th>Tu</th>
                    <th>We</th>
                    <th>Th</th>
                    <th>Fr</th>
                    <th>Sa</th>
                    <th>Su</th>
                  </tr>
                </thead>
                <tbody id="calendarBody">
                  <!-- Calendar days will be populated by JavaScript -->
                </tbody>
              </table>
              <div class="calendar-buttons">
                <button class="calendar-button cancel-button" id="cancelDate">Cancel</button>
                <button class="calendar-button apply-button" id="applyDate">Apply</button>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="filter-card">
        <div class="filter-title">
          <span class="filter-icon">🌡️</span>
          <span>Temperature Range</span>
        </div>
        <select class="filter-dropdown" id="minTemperature">
          <option value="">Min Temperature</option>
          <option value="20">20°C</option>
          <option value="30">30°C</option>
          <option value="40">40°C</option>
          <option value="50">50°C</option>
          <option value="60">60°C</option>
        </select>
        <select class="filter-dropdown" id="maxTemperature">
          <option value="">Max Temperature</option>
          <option value="40">40°C</option>
          <option value="50">50°C</option>
          <option value="60">60°C</option>
          <option value="70">70°C</option>
          <option value="80">80°C</option>
        </select>
      </div>
      
      <div class="filter-card">
        <div class="filter-title">
          <span class="filter-icon">🚨</span>
          <span>Alert Level</span>
        </div>
        <select class="filter-dropdown" id="alertLevel">
          <option value="">Alert Level</option>
          <option value="none">None</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
      </div>
      
      <div class="filter-card">
        <div class="filter-title">
          <span class="filter-icon">🔥</span>
          <span>Fire Detection</span>
        </div>
        <select class="filter-dropdown" id="fireDetection">
          <option value="">All Levels</option>
          <option value="yes">Detected</option>
          <option value="no">Not Detected</option>
        </select>
      </div>
    </div>
    
    <!-- Action Buttons -->
    <div class="actions-container">
      <button class="action-button" id="refreshData">
        <span>Refresh Data</span>
      </button>
      <button class="action-button green" id="exportCsv">
        <span>Export CSV</span>
      </button>
      <button class="action-button green" id="exportJson">
        <span>Export JSON</span>
      </button>
      <button class="action-button gray" id="clearFilters">
        <span>Clear Filters</span>
      </button>
      <button class="action-button" id="generateReport">
        <span>Generate Report</span>
      </button>
    </div>
    
    <!-- Records Table -->
    <div class="records-card">
      <div class="records-header">
        <h2 class="records-title">Historical Fire Detection Records</h2>
        <span class="records-count">{{ records|length }} records</span>
      </div>
      
      <table class="records-table">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Temperature</th>
            <th>Fire Detected</th>
            <th>Alert Level</th>
            <th>Location</th>
            <th>Confidence</th>
            <th>Camera Status</th>
            <th>Thermal Status</th>
          </tr>
        </thead>
        <tbody>
          {% for record in records %}
          <tr>
            <td>{{ record.timestamp }}</td>
            <td>{{ record.temperature }}°C</td>
            <td>{{ record.fire_detected }}</td>
            <td>{{ record.alert_level }}</td>
            <td>{{ record.location }}</td>
            <td>{{ record.confidence }}%</td>
            <td>
              {% if record.camera_status == 'Online' %}
                <span class="status-text ok">{{ record.camera_status }}</span>
              {% else %}
                <span class="status-text offline">{{ record.camera_status }}</span>
              {% endif %}
            </td>
            <td>
              {% if record.thermal_status == 'OK' %}
                <span class="status-text ok">{{ record.thermal_status }}</span>
              {% else %}
                <span class="status-text offline">{{ record.thermal_status }}</span>
              {% endif %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    
    <!-- Pagination -->
    <div class="pagination">
      <button class="pagination-button">1</button>
    </div>
  </main>
  
  <footer>
    PyroSense 2025 © All rights reserved - Python Flasked Edition
  </footer>

  <script>
    // Date picker functionality
    document.addEventListener('DOMContentLoaded', function() {
      const startDateDisplay = document.getElementById('startDateDisplay');
      const endDateDisplay = document.getElementById('endDateDisplay');
      const calendarDropdown = document.getElementById('calendarDropdown');
      const calendarContent = document.getElementById('calendarContent');
      const calendarBody = document.getElementById('calendarBody');
      const currentMonthDisplay = document.getElementById('currentMonth');
      const prevMonthBtn = document.getElementById('prevMonth');
      const nextMonthBtn = document.getElementById('nextMonth');
      const cancelDateBtn = document.getElementById('cancelDate');
      const applyDateBtn = document.getElementById('applyDate');
      const startDateMode = document.getElementById('startDateMode');
      const endDateMode = document.getElementById('endDateMode');
      
      let currentDate = new Date();
      let startDate = null;
      let endDate = null;
      let selectingStartDate = true;
      
      // Initialize calendar
      function initCalendar() {
        showCalendar(currentDate);
      }
      
      // Show calendar for a specific month
      function showCalendar(date) {
        const year = date.getFullYear();
        const month = date.getMonth();
        
        // Update month display
        const monthNames = ["January", "February", "March", "April", "May", "June",
                          "July", "August", "September", "October", "November", "December"];
        currentMonthDisplay.textContent = `${monthNames[month]} ${year}`;
        
        // Clear previous calendar
        calendarBody.innerHTML = '';
        
        // Get first day of month and total days
        const firstDay = new Date(year, month, 1).getDay() || 7; // Convert Sunday (0) to 7
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        
        // Create calendar rows
        let date1 = 1;
        for (let i = 0; i < 6; i++) {
          // Create a table row
          const row = document.createElement('tr');
          
          // Fill in the days
          for (let j = 1; j <= 7; j++) {
            const cell = document.createElement('td');
            if (i === 0 && j < firstDay) {
              // Empty cell before first day of month
              cell.textContent = '';
            } else if (date1 > daysInMonth) {
              // Empty cell after last day of month
              cell.textContent = '';
            } else {
              // Day cell
              cell.textContent = date1;
              cell.dataset.date = `${year}-${String(month + 1).padStart(2, '0')}-${String(date1).padStart(2, '0')}`;
              
              // Check if this date is selected
              const cellDate = new Date(year, month, date1);
              if (startDate && cellDate.getTime() === startDate.getTime()) {
                cell.classList.add('selected');
                cell.classList.add('range-start');
              }
              if (endDate && cellDate.getTime() === endDate.getTime()) {
                cell.classList.add('selected');
                cell.classList.add('range-end');
              }
              if (startDate && endDate && 
                  cellDate > startDate && cellDate < endDate) {
                cell.classList.add('in-range');
              }
              
              // Add click event
              cell.addEventListener('click', function() {
                const selectedDay = parseInt(this.textContent);
                const selectedDate = new Date(year, month, selectedDay);
                
                if (selectingStartDate) {
                  // Clear previous selections
                  document.querySelectorAll('.calendar td.selected, .calendar td.in-range').forEach(el => {
                    el.classList.remove('selected', 'in-range', 'range-start', 'range-end');
                  });
                  
                  startDate = selectedDate;
                  endDate = null;
                  this.classList.add('selected', 'range-start');
                  
                  // Switch to end date selection
                  selectingStartDate = false;
                  startDateMode.classList.remove('active-mode');
                  endDateMode.classList.add('active-mode');
                  
                  // Update display
                  startDateDisplay.value = formatDate(startDate);
                  endDateDisplay.value = '';
                } else {
                  // Selecting end date
                  if (selectedDate < startDate) {
                    // If end date is before start date, swap them
                    endDate = startDate;
                    startDate = selectedDate;
                    
                    // Update display
                    startDateDisplay.value = formatDate(startDate);
                  } else {
                    endDate = selectedDate;
                  }
                  
                  // Clear previous end/range selections
                  document.querySelectorAll('.calendar td.range-end, .calendar td.in-range').forEach(el => {
                    el.classList.remove('range-end', 'in-range');
                  });
                  
                  // Mark end date and range
                  this.classList.add('selected', 'range-end');
                  markDateRange();
                  
                  // Switch back to start date selection
                  selectingStartDate = true;
                  endDateMode.classList.remove('active-mode');
                  startDateMode.classList.add('active-mode');
                  
                  // Update display
                  endDateDisplay.value = formatDate(endDate);
                }
              });
              
              date1++;
            }
            row.appendChild(cell);
          }
          
          calendarBody.appendChild(row);
          if (date1 > daysInMonth) {
            break; // Stop creating rows if we've used all days
          }
        }
      }
      
      // Mark all dates in the selected range
      function markDateRange() {
        if (!startDate || !endDate) return;
        
        document.querySelectorAll('.calendar td').forEach(cell => {
          if (!cell.dataset.date) return;
          
          const cellParts = cell.dataset.date.split('-');
          const cellDate = new Date(
            parseInt(cellParts[0]),
            parseInt(cellParts[1]) - 1,
            parseInt(cellParts[2])
          );
          
          if (cellDate > startDate && cellDate < endDate) {
            cell.classList.add('in-range');
          }
        });
      }
      
      // Format date as YYYY-MM-DD
      function formatDate(date) {
        if (!date) return '';
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
      }
      
      // Toggle calendar dropdown when clicking on either date input
      startDateDisplay.addEventListener('click', function() {
        calendarContent.classList.toggle('show');
        selectingStartDate = true;
        startDateMode.classList.add('active-mode');
        endDateMode.classList.remove('active-mode');
      });
      
      endDateDisplay.addEventListener('click', function() {
        calendarContent.classList.toggle('show');
        selectingStartDate = false;
        startDateMode.classList.remove('active-mode');
        endDateMode.classList.add('active-mode');
      });
      
      // Mode selection
      startDateMode.addEventListener('click', function() {
        selectingStartDate = true;
        startDateMode.classList.add('active-mode');
        endDateMode.classList.remove('active-mode');
      });
      
      endDateMode.addEventListener('click', function() {
        selectingStartDate = false;
        startDateMode.classList.remove('active-mode');
        endDateMode.classList.add('active-mode');
      });
      
      // Close calendar when clicking outside
      window.addEventListener('click', function(e) {
        if (!calendarDropdown.contains(e.target) && 
            e.target !== startDateDisplay && 
            e.target !== endDateDisplay) {
          calendarContent.classList.remove('show');
        }
      });
      
      // Navigate to previous month
      prevMonthBtn.addEventListener('click', function() {
        currentDate.setMonth(currentDate.getMonth() - 1);
        showCalendar(currentDate);
      });
      
      // Navigate to next month
      nextMonthBtn.addEventListener('click', function() {
        currentDate.setMonth(currentDate.getMonth() + 1);
        showCalendar(currentDate);
      });
      
      // Cancel date selection
      cancelDateBtn.addEventListener('click', function() {
        calendarContent.classList.remove('show');
      });
      
      // Apply date selection
      applyDateBtn.addEventListener('click', function() {
        if (startDate) {
          // Here you would typically filter the data based on the selected dates
          const url = new URL(window.location);
          url.searchParams.set('start_date', formatDate(startDate));
          if (endDate) {
            url.searchParams.set('end_date', formatDate(endDate));
          } else {
            url.searchParams.delete('end_date');
          }
          window.history.replaceState({}, '', url);
          
          // In a real app, you might want to reload the data with the new date range
          // location.reload();
        }
        calendarContent.classList.remove('show');
      });
      
      // Initialize calendar
      initCalendar();
    });
  </script>
</body>
</html>
"""

def calculate_statistics(data):
    """Calculate statistics from historical data"""
    if not data:
        return {
            'total_fires': 0,
            'avg_temperature': 0,
            'total_alerts': 0,
            'uptime': 0
        }
    
    total_fires = sum(1 for record in data if record['fire_detected'])
    avg_temperature = round(sum(record['temperature'] for record in data) / len(data), 1)
    total_alerts = sum(1 for record in data if record['alert_level'] != 'None')
    
    # Calculate uptime (percentage of records where all systems are online)
    online_records = sum(1 for record in data 
                        if record['camera_status'] == 'Online' and record['thermal_status'] == 'OK')
    uptime = round((online_records / len(data)) * 100, 1) if data else 0
    
    return {
        'total_fires': total_fires,
        'avg_temperature': avg_temperature,
        'total_alerts': total_alerts,
        'uptime': uptime
    }

def filter_data(data, filters):
    """Apply filters to historical data"""
    filtered_data = data.copy()
    
    # Date range filter
    if filters.get('start_date'):
        start_date = datetime.fromisoformat(filters['start_date'])
        filtered_data = [r for r in filtered_data 
                        if datetime.fromisoformat(r['timestamp']) >= start_date]
    
    if filters.get('end_date'):
        end_date = datetime.fromisoformat(filters['end_date'])
        filtered_data = [r for r in filtered_data 
                        if datetime.fromisoformat(r['timestamp']) <= end_date]
    
    # Temperature range filter
    if filters.get('min_temp'):
        min_temp = float(filters['min_temp'])
        filtered_data = [r for r in filtered_data if r['temperature'] >= min_temp]
    
    if filters.get('max_temp'):
        max_temp = float(filters['max_temp'])
        filtered_data = [r for r in filtered_data if r['temperature'] <= max_temp]
    
    # Alert level filter
    if filters.get('alert_level'):
        alert_level = filters['alert_level']
        filtered_data = [r for r in filtered_data if r['alert_level'] == alert_level]
    
    # Fire detection filter
    if filters.get('fire_detected'):
        fire_detected = filters['fire_detected'].lower() == 'true'
        filtered_data = [r for r in filtered_data if r['fire_detected'] == fire_detected]
    
    return filtered_data

@app.route('/')
def root():
    """Display dashboard if authenticated, otherwise redirect to login"""
    if not session.get('user'):
        # If no user in session, show a simple login prompt
        return render_template_string("""
            <html>
                <head><title>PyroSense History - Authentication Required</title></head>
                <body style="background: #121212; color: white; text-align: center; padding-top: 100px; font-family: Arial;">
                    <h1>Authentication Required</h1>
                    <p>Please log in through the PyroSense Login Portal</p>
                    <p><a href="http://localhost:5000/login" style="color: #f77f00; text-decoration: none; padding: 10px 20px; border: 1px solid #f77f00; border-radius: 5px;">Go to Login</a></p>
                </body>
            </html>
        """)
    
    # Get recent 50 records for initial display
    recent_data = historical_data[:50]
    stats = calculate_statistics(historical_data)
    
    return render_template_string(HTML_TEMPLATE, 
                                records=recent_data,
                                stats=stats,
                                total_records=len(historical_data),
                                username=session.get('name', 'User'))

# Update the root route to show the dashboard directly
@app.route('/history')
def history_page():
    """Main history page - redirects to dashboard"""
    return root()  # Just call the root function

@app.route('/api/history')
def get_history():
    """API endpoint for filtered historical data"""
    # Check if user is authenticated
    if not session.get('user'):
        return jsonify({'error': 'Authentication required'}), 401
        
    # Get filter parameters
    filters = {
        'start_date': request.args.get('start_date'),
        'end_date': request.args.get('end_date'),
        'min_temp': request.args.get('min_temp'),
        'max_temp': request.args.get('max_temp'),
        'alert_level': request.args.get('alert_level'),
        'fire_detected': request.args.get('fire_detected')
    }
    
    # Remove empty filters
    filters = {k: v for k, v in filters.items() if v}
    
    # Apply filters
    filtered_data = filter_data(historical_data, filters)
    
    # Pagination
    page = int(request.args.get('page', 1))
    per_page = 50
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    paginated_data = filtered_data[start_idx:end_idx]
    total_pages = (len(filtered_data) + per_page - 1) // per_page
    
    # Calculate statistics for filtered data
    stats = calculate_statistics(filtered_data)
    
    return jsonify({
        'records': paginated_data,
        'stats': stats,
        'total_records': len(filtered_data),
        'pagination': {
            'current_page': page,
            'total_pages': total_pages,
            'per_page': per_page
        }
    })

@app.route('/api/export/csv')
def export_csv():
    """Export filtered data as CSV"""
    # Check if user is authenticated
    if not session.get('user'):
        return jsonify({'error': 'Authentication required'}), 401
        
    # Get filter parameters (same as history endpoint)
    filters = {k: v for k, v in request.args.items() if v}
    filtered_data = filter_data(historical_data, filters)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Timestamp', 'Temperature', 'Fire Detected', 'Alert Level', 
                    'Location', 'Confidence', 'Camera Status', 'Thermal Status'])
    
    # Write data
    for record in filtered_data:
        writer.writerow([
            record['timestamp'],
            record['temperature'],
            'Yes' if record['fire_detected'] else 'No',
            record['alert_level'],
            record['location'],
            f"{record['confidence']:.2f}",
            record['camera_status'],
            record['thermal_status']
        ])
    
    # Prepare response
    output.seek(0);
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'pyrosense_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

@app.route('/api/export/json')
def export_json():
    """Export filtered data as JSON"""
    # Check if user is authenticated
    if not session.get('user'):
        return jsonify({'error': 'Authentication required'}), 401
        
    # Get filter parameters (same as history endpoint)
    filters = {k: v for k, v in request.args.items() if v}
    filtered_data = filter_data(historical_data, filters)
    
    # Create JSON export
    export_data = {
        'export_info': {
            'generated_at': datetime.now().isoformat(),
            'total_records': len(filtered_data),
            'filters_applied': filters,
            'system': 'PyroSense Python Edition'
        },
        'statistics': calculate_statistics(filtered_data),
        'records': filtered_data
    }
    
    # Prepare response
    json_str = json.dumps(export_data, indent=2);
    return send_file(
        io.BytesIO(json_str.encode()),
        mimetype='application/json',
        as_attachment=True,
        download_name=f'pyrosense_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    )

@app.route('/api/statistics')
def get_statistics():
    """Get overall statistics"""
    # Check if user is authenticated
    if not session.get('user'):
        return jsonify({'error': 'Authentication required'}), 401
        
    stats = calculate_statistics(historical_data)
    return jsonify(stats)

# Add this route before the if __name__ == '__main__' block
@app.route('/dashboard')
def goto_dashboard():
    """Redirect to the main dashboard application"""
    return redirect('http://localhost:5000')

if __name__ == '__main__':
    print("🐍 Starting PyroSense History Python Flask Application...")
    print("📊 Historical Data Analysis System - Python Edition")
    print("=" * 60)
    print("History Page URL: http://localhost:5001")
    print("NOTE: Use the same login credentials as the login portal")
    print("Features:")
    print("  • 📅 Date range filtering")
    print("  • 🌡️ Temperature range filtering")
    print("  • 🚨 Alert level filtering")
    print("  • 🔥 Fire detection filtering")
    print("  • 📊 CSV/JSON data export")
    print("  • 📈 Real-time statistics")
    print("  • 🐍 Python-powered analytics")
    print("To stop server: Press Ctrl+C")
    print("=" * 60)
    
    # Run the Flask development server on port 5001
    app.run(debug=True, host='0.0.0.0', port=5001)
    print("🐍 Starting PyroSense History Python Flask Application...")
    print("📊 Historical Data Analysis System - Python Edition")
    print("=" * 60)
    print("History Page URL: http://localhost:5001")
    print("NOTE: Use the same login credentials as the login portal")
    print("Features:")
    print("  • 📅 Date range filtering")
    print("  • 🌡️ Temperature range filtering")
    print("  • 🚨 Alert level filtering")
    print("  • 🔥 Fire detection filtering")
    print("  • 📊 CSV/JSON data export")
    print("  • 📈 Real-time statistics")
    print("  • 🐍 Python-powered analytics")
    print("To stop server: Press Ctrl+C")
    print("=" * 60)
    
    # Run the Flask development server on port 5001
    app.run(debug=True, host='0.0.0.0', port=5001)
    app.run(debug=True, host='0.0.0.0', port=5001)

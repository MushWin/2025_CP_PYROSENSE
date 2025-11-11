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
import zipfile

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
   <link rel="stylesheet" href="{{ url_for('static', filename='css/history.css') }}">
</head>
<body>
  <div class="history-overlay">
    <!-- <div class="history-title">HISTORY</div> -->

    <header>
      <div class="header-container">
        <div class="header-left">
          <div class="header-logo">🔥</div>
          <div class="header-title-section">
            <h1 class="header-title">PYROSENSE</h1>
            <p class="header-subtitle">Advanced Fire Detection System - Python Edition</p>
          </div>
        </div>

        <div class="header-center">
          <nav class="main-nav">
            <a href="http://localhost:5002" class="nav-link" id="navDashboard">Dashboard</a>
            <span class="nav-sep" aria-hidden="true"></span>
            <a href="#" class="nav-link active" id="navHistory">History</a>
          </nav>
        </div>

        <div class="header-right">
          <span class="badge python-badge">Made with Python Flask</span>
          <!-- REMOVED: old right-side back button in favor of centered nav -->
          <!-- <a href="http://localhost:5002" class="dashboard-button">🏠 Back to Dashboard</a> -->
        </div>
      </div>
    </header>

    <main>
      <!-- Stats Section -->
    <div class="stats-container">
      <div class="stat-card">
        <div class="stat-icon">🔥</div>
        <div class="stat-value">{{ stats.total_fires }}</div>
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
          <span>Select Date Range</span>
        </div>
        <div class="date-range-inputs">
          <div class="date-input-group">               v
            <label class="date-input-label">Start Date</label>
            <input type="text" class="date-input" id="startDate" placeholder="📅 Start Date" readonly>
          </div>
          <div class="date-input-group">
            <label class="date-input-label">End Date</label>
            <input type="text" class="date-input" id="endDate" placeholder="📅 End Date" readonly>
          </div>
        </div>
      </div>
      
      <div class="filter-card">
        <div class="filter-title">
          <span class="filter-icon">🌡️</span>
          <span>Temperature Range</span>
        </div>
        <div class="temp-range-group">
          <label class="temp-range-label" for="minTemperature">Min Temperature (°C)</label>
          <input type="number" class="temp-range-input" id="minTemperature" placeholder="Min °C" min="0" max="100" step="1">
          <label class="temp-range-label" for="maxTemperature">Max Temperature (°C)</label>
          <input type="number" class="temp-range-input" id="maxTemperature" placeholder="Max °C" min="0" max="100" step="1">
        </div>
      </div>
      
      <div class="filter-card">
        <div class="filter-title">
          <span class="filter-icon">🚨</span>
          <span>Alert Level</span>
        </div>
        <div class="custom-dropdown" id="alertLevelDropdown">
          <button class="dropdown-toggle" type="button" id="alertLevelButton">
            <span id="alertLevelText">Select Alert Level</span>
          </button>
          <div class="dropdown-menu" id="alertLevelMenu">
            <button class="dropdown-item" type="button" data-value="low">Low</button>
            <button class="dropdown-item" type="button" data-value="medium">Medium</button>
            <button class="dropdown-item" type="button" data-value="high">High</button>
          </div>
        </div>
      </div>
      
      <div class="filter-card">
        <div class="filter-title">
          <span class="filter-icon">🔥</span>
          <span>Fire Detection</span>
        </div>
        <div class="custom-dropdown" id="fireDetectionDropdown">
          <button class="dropdown-toggle" type="button" id="fireDetectionButton">
            <span id="fireDetectionText">Select Fire Detection</span>
          </button>
          <div class="dropdown-menu" id="fireDetectionMenu">
            <button class="dropdown-item" type="button" data-value="yes">Detected</button>
            <button class="dropdown-item" type="button" data-value="no">Not Detected</button>
          </div>
        </div>
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
        <span class="records-count">{{ total_records }} records</span>
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
      {% if total_pages > 1 %}
        {% if current_page > 1 %}
          <a class="pagination-button" href="?page={{ current_page - 1 }}">←</a>
        {% endif %}
        
        {% for page_num in range(1, total_pages + 1) %}
          {% if page_num == current_page %}
            <span class="pagination-button active">{{ page_num }}</span>
          {% elif page_num == 1 or page_num == total_pages or (page_num >= current_page - 1 and page_num <= current_page + 1) %}
            <a class="pagination-button" href="?page={{ page_num }}">{{ page_num }}</a>
          {% elif page_num == current_page - 2 or page_num == current_page + 2 %}
            <span class="pagination-button">...</span>
          {% endif %}
        {% endfor %}
        
        {% if current_page < total_pages %}
          <a class="pagination-button" href="?page={{ current_page + 1 }}">→</a>
        {% endif %}
      {% endif %}
    </div>
  </main>
  
  <footer>
    PyroSense 2025 © All rights reserved - Python Flask Edition
  </footer>

  <!-- MODAL CALENDAR POPUP - FIXED VERSION -->
  <div class="calendar-modal-overlay" id="calendarOverlay">
    <div class="calendar-modal" id="calendarModal">
      <div class="calendar-header">
        <h3 class="calendar-title">📅 Select Date Range</h3>
        <p class="calendar-subtitle">Choose start and end dates for filtering</p>
        <button class="calendar-close" id="closeCalendar" type="button">×</button>
      </div>
      
      <div class="calendar-body">
        <div class="calendar-info">
          <div><strong>Today:</strong> <span id="todayDisplay">Loading...</span></div>
          <div id="rangeDisplay">Click dates to select range</div>
        </div>
        
        <!-- Date Input Display -->
        <div class="date-selection-inputs">
          <div class="date-input-group">
            <div class="date-input-label">📅 Start Date</div>
            <div class="date-input-field" id="startDateDisplay">Not selected</div>
          </div>
          <div class="date-input-group">
            <div class="date-input-label">📅 End Date</div>
            <div class="date-input-field" id="endDateDisplay">Not selected</div>
          </div>
        </div>
        
        <div class="selection-mode">
          <div class="mode-tab active" id="startMode">Select Start Date</div>
          <div class="mode-tab" id="endMode">Select End Date</div>
        </div>
        
        <div class="month-navigation">
          <button class="month-nav-btn" id="prevMonth" type="button">‹</button>
          <div class="current-month" id="currentMonthYear">January 2025</div>
          <button class="month-nav-btn" id="nextMonth" type="button">›</button>
        </div>
        
        <table class="calendar-grid">
          <thead>
            <tr>
              <th>Sun</th>
              <th>Mon</th>
              <th>Tue</th>
              <th>Wed</th>
              <th>Thu</th>
              <th>Fri</th>
              <th>Sat</th>
            </tr>
          </thead>
          <tbody id="calendarDays">
            <tr>
              <td colspan="7" style="text-align: center; padding: 20px; color: #999;">Loading calendar...</td>
            </tr>
          </tbody>
        </table>
      </div>
      
      <div class="calendar-footer">
        <div class="selected-range" id="selectedRange">No dates selected</div>
        <div class="calendar-actions">
          <button class="calendar-btn today" id="todayBtn" type="button">📅 Today</button>
          <button class="calendar-btn cancel" id="cancelBtn" type="button">Cancel</button>
          <button class="calendar-btn apply" id="applyBtn" type="button">Apply Range</button>
        </div>
      </div>
    </div>
  </div>

  <!-- include SweetAlert -->
  <script src="https://unpkg.com/sweetalert/dist/sweetalert.min.js"></script>

  <script>
    // Enhanced Calendar Modal System - COMPLETELY FIXED
    document.addEventListener('DOMContentLoaded', function() {
      console.log('Initializing calendar system...');
      
      // Elements
      const startDateInput = document.getElementById('startDate');
      const endDateInput = document.getElementById('endDate');
      const calendarOverlay = document.getElementById('calendarOverlay');
      const calendarModal = document.getElementById('calendarModal');
      const closeCalendar = document.getElementById('closeCalendar');
      const todayDisplay = document.getElementById('todayDisplay');
      const rangeDisplay = document.getElementById('rangeDisplay');
      const startDateDisplay = document.getElementById('startDateDisplay');
      const endDateDisplay = document.getElementById('endDateDisplay');
      const startMode = document.getElementById('startMode');
      const endMode = document.getElementById('endMode');
      const prevMonth = document.getElementById('prevMonth');
      const nextMonth = document.getElementById('nextMonth');
      const currentMonthYear = document.getElementById('currentMonthYear');
      const calendarDays = document.getElementById('calendarDays');
      const selectedRange = document.getElementById('selectedRange');
      const todayBtn = document.getElementById('todayBtn');
      const cancelBtn = document.getElementById('cancelBtn');
      const applyBtn = document.getElementById('applyBtn');
      
      // Improved scroll lock: prevent double-locking
      let scrollLocked = false;
      function lockBodyScroll() {
        if (scrollLocked) return;
        document.body.style.overflow = 'hidden';
        document.body.style.position = 'fixed';
        document.body.style.width = '100%';
        document.body.style.top = `-${window.scrollY}px`;
        document.body.dataset.scrollY = window.scrollY;
        scrollLocked = true;
      }

      function unlockBodyScroll() {
        if (!scrollLocked) return;
        const scrollY = document.body.dataset.scrollY || '0';
        document.body.style.overflow = '';
        document.body.style.position = '';
        document.body.style.width = '';
        document.body.style.top = '';
        window.scrollTo(0, parseInt(scrollY || '0'));
        scrollLocked = false;
      }
      
      // State
      let currentDate = new Date();
      let startDate = null;
      let endDate = null;
      let selectingStart = true;
      const today = new Date();
      
      // Initialize with default range (last 7 days)
      const defaultEnd = new Date();
      const defaultStart = new Date();
      defaultStart.setDate(defaultStart.getDate() - 7);
      
      startDate = defaultStart;
      endDate = defaultEnd;
      
      // Utility functions
      function formatDate(date) {
        if (!date) return '';
        return date.toLocaleDateString('en-US', { 
          year: 'numeric', 
          month: 'short', 
          day: 'numeric' 
        });
      }
      
      function formatInputDate(date) {
        if (!date) return '';
        return date.toLocaleDateString('en-US', { 
          month: 'short', 
          day: 'numeric',
          year: 'numeric'
        });
      }
      
      function isSameDay(date1, date2) {
        if (!date1 || !date2) return false;
        return date1.getDate() === date2.getDate() &&
               date1.getMonth() === date2.getMonth() &&
               date1.getFullYear() === date2.getFullYear();
      }
      
      function isInRange(date, start, end) {
        if (!start || !end) return false;
        return date > start && date < end;
      }
      
      // Initialize display
      function initializeDisplay() {
        console.log('Initializing displays...');
        todayDisplay.textContent = formatDate(today);
        updateDisplays();
      }
      
      function updateDisplays() {
        // Update input fields
        startDateInput.value = formatInputDate(startDate);
        endDateInput.value = formatInputDate(endDate);
        
        // Update modal displays
        startDateDisplay.textContent = startDate ? formatDate(startDate) : 'Not selected';
        endDateDisplay.textContent = endDate ? formatDate(endDate) : 'Not selected';
        
        // Update active state
        startDateDisplay.classList.toggle('active', selectingStart);
        endDateDisplay.classList.toggle('active', !selectingStart);
        
        // Update range display
        if (startDate && endDate) {
          rangeDisplay.innerHTML = `<strong>Selected:</strong> ${formatDate(startDate)} to ${formatDate(endDate)}`;
          selectedRange.textContent = `${formatDate(startDate)} - ${formatDate(endDate)}`;
        } else if (startDate) {
          rangeDisplay.innerHTML = `<strong>Start:</strong> ${formatDate(startDate)} - Select end date`;
          selectedRange.textContent = 'Select end date';
        } else {
          rangeDisplay.textContent = 'Click dates to select range';
          selectedRange.textContent = 'No dates selected';
        }
      }
      
      function updateModeDisplay() {
        startMode.classList.toggle('active', selectingStart);
        endMode.classList.toggle('active', !selectingStart);
      }
      
      // Calendar generation
      function generateCalendar(date) {
        console.log('Generating calendar for:', date);
        const year = date.getFullYear();
        const month = date.getMonth();
        
        const monthNames = [
          'January', 'February', 'March', 'April', 'May', 'June',
          'July', 'August', 'September', 'October', 'November', 'December'
        ];
        
        currentMonthYear.textContent = `${monthNames[month]} ${year}`;
        
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const daysInMonth = lastDay.getDate();
        const startingDayOfWeek = firstDay.getDay();
        
        let html = '';
        let dayCount = 1;
        
        // Generate calendar rows (6 weeks max)
        for (let week = 0; week < 6; week++) {
          html += '<tr>';
          
          for (let day = 0; day < 7; day++) {
            if (week === 0 && day < startingDayOfWeek) {
              // Empty cells before first day of month
              html += '<td class="empty"></td>';
            } else if (dayCount > daysInMonth) {
              // Empty cells after last day of month
              html += '<td class="empty"></td>';
            } else {
              // Actual calendar day
              const cellDate = new Date(year, month, dayCount);
              const cellClasses = [];
              
              if (isSameDay(cellDate, today)) {
                cellClasses.push('today');
              }
              
              if (isSameDay(cellDate, startDate)) {
                cellClasses.push('selected');
              } else if (isSameDay(cellDate, endDate)) {
                cellClasses.push('selected');
              } else if (isInRange(cellDate, startDate, endDate)) {
                cellClasses.push('in-range');
              }
              
              html += `<td class="${cellClasses.join(' ')}" data-date="${cellDate.toISOString()}">${dayCount}</td>`;
              dayCount++;
            }
          }
          
          html += '</tr>';
          
          if (dayCount > daysInMonth) break;
        }
        
        calendarDays.innerHTML = html;
        console.log('Calendar generated successfully');
      }
      
      function handleDateClick(event) {
        const td = event.target.closest('td[data-date]');
        if (!td) return;
        
        const clickedDate = new Date(td.dataset.date);
        console.log('Date clicked:', clickedDate);
        
        if (selectingStart) {
          startDate = clickedDate;
          endDate = null;
          selectingStart = false;
        } else {
          if (clickedDate < startDate) {
            // Swap dates if end is before start
            endDate = startDate;
            startDate = clickedDate;
          } else {
            endDate = clickedDate;
          }
          selectingStart = true;
        }
        
        updateModeDisplay();
        updateDisplays();
        generateCalendar(currentDate);
      }
      
      // --- Remove scroll locking ---
      // function lockBodyScroll() {
      //   document.body.style.overflow = 'hidden';
      //   document.body.style.position = 'fixed';
      //   document.body.style.width = '100vw';
      // }
      // function unlockBodyScroll() {
      //   document.body.style.overflow = '';
      //   document.body.style.position = '';
      //   document.body.style.width = '';
      // }

      // --- Modified showCalendar to always center modal and lock scrolling ---
      function showCalendar(inputElement) {
        // Always lock body scroll at the very start
        lockBodyScroll();

        console.log('🎬 Starting calendar show animation...');
        calendarOverlay.style.display = 'flex';
        calendarOverlay.style.visibility = 'visible';
        calendarOverlay.classList.remove('show');

        // Force reflow to ensure styles are applied
        void calendarOverlay.offsetHeight;

        // Trigger animation
        setTimeout(() => {
          calendarOverlay.classList.add('show');
          console.log('✨ Calendar animation started');
        }, 10);

        generateCalendar(currentDate);
        updateModeDisplay();
        updateDisplays();
      }

      function hideCalendar() {
        console.log('🎬 Starting calendar hide animation...');
        
        // Start fade out animation
        calendarOverlay.classList.remove('show');
        
        // Wait for animation to complete
        setTimeout(() => {
          calendarOverlay.style.display = 'none';
          calendarOverlay.style.visibility = 'hidden';
          // Always unlock body scroll when hiding
          unlockBodyScroll();
        }, 500);
      }
      
      // Enhanced dropdown animations with better centering
      function addDropdownAnimations() {
        const dropdowns = document.querySelectorAll('.filter-dropdown');
        
        dropdowns.forEach(dropdown => {
          // Focus animations
          dropdown.addEventListener('focus', function() {
            this.style.transform = 'scale(1.03)';
            this.style.boxShadow = '0 0 0 4px rgba(255, 107, 107, 0.15), 0 8px 25px rgba(0,0,0,0.15)';
            this.style.borderColor = '#ff6b6b';
          });
          
          // Blur animations
          dropdown.addEventListener('blur', function() {
            this.style.transform = 'scale(1)';
            this.style.boxShadow = '0 2px 4px rgba(0,0,0,0.05)';
            this.style.borderColor = '#e2e8f0';
          });
          
          // Change animations with bounce effect
          dropdown.addEventListener('change', function() {
            this.style.transform = 'scale(1.08)';
            this.style.boxShadow = '0 0 0 6px rgba(255, 107, 107, 0.2), 0 12px 30px rgba(0,0,0,0.2)';
            
            setTimeout(() => {
              this.style.transform = 'scale(1)';
              this.style.boxShadow = '0 2px 4px rgba(0,0,0,0.05)';
            }, 200);
            
            // Add ripple effect
            this.style.background = 'linear-gradient(135deg, rgba(255, 107, 107, 0.1) 0%, rgba(255, 165, 0, 0.1) 100%)';
            setTimeout(() => {
              this.style.background = 'white';
            }, 300);
          });
          
          // Mouse enter with smooth scale
          dropdown.addEventListener('mouseenter', function() {
            if (document.activeElement !== this) {
              this.style.transform = 'scale(1.02)';
              this.style.boxShadow = '0 0 0 3px rgba(255, 107, 107, 0.1), 0 6px 20px rgba(0,0,0,0.12)';
            }
          });
          
          // Mouse leave with smooth return
          dropdown.addEventListener('mouseleave', function() {
            if (document.activeElement !== this) {
              this.style.transform = 'scale(1)';
              this.style.boxShadow = '0 2px 4px rgba(0,0,0,0.05)';
            }
          });
          
          // Add click animation
          dropdown.addEventListener('mousedown', function() {
            this.style.transform = 'scale(0.98)';
          });
          
          dropdown.addEventListener('mouseup', function() {
            this.style.transform = 'scale(1.02)';
          });
          
          // Smooth opening animation
          dropdown.addEventListener('click', function() {
            // Add a subtle pulse effect when opened
            this.style.animation = 'pulse 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
            setTimeout(() => {
              this.style.animation = '';
            }, 600);
          });
        });
        
        // Close dropdowns when clicking elsewhere
        document.addEventListener('click', function(e) {
          if (!e.target.closest('.custom-dropdown')) {
            dropdowns.forEach(d => d.classList.remove('open'));
          }
        });
      }
      
      // Event listeners
      if (startDateInput) {
        startDateInput.addEventListener('click', function() {
          selectingStart = true;
          showCalendar(this); // always call showCalendar
        });
      }
      
      if (endDateInput) {
        endDateInput.addEventListener('click', function() {
          selectingStart = false;
          showCalendar(this); // always call showCalendar
        });
      }
      
      if (startMode) {
        startMode.addEventListener('click', () => {
          selectingStart = true;
          updateModeDisplay();
          updateDisplays();
        });
      }
      
      if (endMode) {
        endMode.addEventListener('click', () => {
          selectingStart = false;
          updateModeDisplay();
          updateDisplays();
        });
      }
      
      if (closeCalendar) {
        closeCalendar.addEventListener('click', hideCalendar);
      }
      
      if (calendarOverlay) {
        calendarOverlay.addEventListener('click', (e) => {
          if (e.target === calendarOverlay) {
            hideCalendar();
          }
        });
      }
      
      // Add event delegation for calendar day clicks
      if (calendarDays) {
        calendarDays.addEventListener('click', handleDateClick);
      }
      
      if (prevMonth) {
        prevMonth.addEventListener('click', () => {
          currentDate.setMonth(currentDate.getMonth() - 1);
          generateCalendar(currentDate);
        });
      }
      
      if (nextMonth) {
        nextMonth.addEventListener('click', () => {
          currentDate.setMonth(currentDate.getMonth() + 1);
          generateCalendar(currentDate);
        });
      }
      
      if (todayBtn) {
        todayBtn.addEventListener('click', () => {
          const today = new Date();
          if (selectingStart) {
            startDate = today;
          } else {
            endDate = today;
          }
          updateDisplays();
          generateCalendar(currentDate);
        });
      }
      
      if (cancelBtn) {
        cancelBtn.addEventListener('click', hideCalendar);
      }
      
      if (applyBtn) {
        applyBtn.addEventListener('click', () => {
          if (startDate && endDate) {
            hideCalendar();
            showNotification(`Date range applied: ${formatDate(startDate)} to ${formatDate(endDate)}`, 'success');
          } else {
            showNotification('Please select both start and end dates', 'error');
          }
        });
      }
      
      // Keyboard shortcuts
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && calendarOverlay.classList.contains('show')) {
          hideCalendar();
        }
      });
      
      // Enhanced notification system with better animations
      function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.style.cssText = `
          position: fixed; top: 20px; right: 20px; z-index: 2000000;
          background: ${type === 'success' ? 'linear-gradient(135deg, #4CAF50 0%, #66bb6a 100%)' : 'linear-gradient(135deg, #f44336 0%, #ff7043 100%)'};
          color: white; padding: 15px 25px; border-radius: 12px;
          box-shadow: 0 8px 25px rgba(0, 0, 0, 0.2);
          font-weight: 600; max-width: 350px; word-wrap: break-word;
          transform: translateX(400px) scale(0.8); 
          opacity: 0;
          transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
        `;
        notification.textContent = message;
        document.body.appendChild(notification);
        
        // Animate in with better easing
        requestAnimationFrame(() => {
          notification.style.transform = 'translateX(0) scale(1)';
          notification.style.opacity = '1';
        });
        
        // Animate out and remove
        setTimeout(() => {
          notification.style.transform = 'translateX(400px) scale(0.8)';
          notification.style.opacity = '0';
          setTimeout(() => notification.remove(), 400);
        }, 3000);
      }
      
      // Test function to verify calendar works
      window.testCalendar = function() {
        console.log('Testing calendar...');
        showCalendar();
      };
      
      // Initialize everything
      console.log('Initializing calendar system...');
      initializeDisplay();
      addDropdownAnimations();
      console.log('Calendar system initialized');
      
      // Add dropdown functionality
      function setupDropdowns() {
        const dropdowns = document.querySelectorAll('.custom-dropdown');
        dropdowns.forEach(dropdown => {
          const toggleBtn = dropdown.querySelector('.dropdown-toggle');
          const menu = dropdown.querySelector('.dropdown-menu');
          const items = dropdown.querySelectorAll('.dropdown-item');
          const displayText = dropdown.querySelector('span');
          
          // Toggle dropdown visibility on button click
          toggleBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            dropdown.classList.toggle('open');
            
            // Close all other dropdowns
            dropdowns.forEach(d => {
              if (d !== dropdown) d.classList.remove('open');
            });
          });
          
          // Handle item selection
          items.forEach(item => {
            item.addEventListener('click', function() {
              const value = this.dataset.value;
              const text = this.textContent;
              displayText.textContent = text;
              
              // Remove selected class from all items
              items.forEach(i => i.classList.remove('selected'));
              // Add selected class to clicked item
              this.classList.add('selected');
              
              // Close dropdown after selection
              dropdown.classList.remove('open');
            });
          });
        });
        
        // Close dropdowns when clicking elsewhere
        document.addEventListener('click', function(e) {
          if (!e.target.closest('.custom-dropdown')) {
            dropdowns.forEach(d => d.classList.remove('open'));
          }
        });
      }
      
      // Initialize dropdowns
      setupDropdowns();
    });

    // Action button functionality (SweetAlert enhancements)
    (function(){
      const safe = (id) => document.getElementById(id);

      const refreshBtn = safe('refreshData');
      if (refreshBtn) {
        refreshBtn.addEventListener('click', function(){
          swal({
            title: "Refresh data?",
            text: "This will reload the page and refresh the displayed data.",
            icon: "info",
            buttons: ["Cancel","Refresh"],
            dangerMode: false
          }).then(ok => { if (ok) location.reload(); });
        });
      }

      const exportCsv = safe('exportCsv');
      if (exportCsv) {
        exportCsv.addEventListener('click', function(){
          swal({
            title: "Export CSV?",
            text: "A CSV file will be downloaded containing the current filtered records.",
            icon: "info",
            buttons: ["Cancel","Export"],
          }).then(ok => { if (ok) window.open('/api/export/csv', '_blank'); });
        });
      }

      const exportJson = safe('exportJson');
      if (exportJson) {
        exportJson.addEventListener('click', function(){
          swal({
            title: "Export JSON?",
            text: "A JSON file will be downloaded containing the current filtered records.",
            icon: "info",
            buttons: ["Cancel","Export"],
          }).then(ok => { if (ok) window.open('/api/export/json', '_blank'); });
        });
      }

      const clearBtn = safe('clearFilters');
      if (clearBtn) {
        clearBtn.addEventListener('click', function(){
          swal({
            title: "Clear filters?",
            text: "This will reset all filters and URL parameters.",
            icon: "warning",
            buttons: ["Cancel","Clear"],
            dangerMode: true
          }).then(ok => {
            if (!ok) return;
            // Clear all filter fields
            const ids = ['minTemperature','maxTemperature','alertLevel','fireDetection','startDate','endDate'];
            ids.forEach(i => { const el = document.getElementById(i); if (el) el.value = ''; });
            const url = new URL(window.location);
            url.search = '';
            window.history.replaceState({}, '', url);
            swal("Filters cleared", { icon: "success", timer: 1500, buttons: false });
          });
        });
      }

      const genBtn = safe('generateReport');
      if (genBtn) {
        genBtn.addEventListener('click', function(){
          swal({
            title: "Generate report?",
            text: "A ZIP (CSV + JSON + summary) will be generated and downloaded using current filters.",
            icon: "info",
            buttons: ["Cancel","Generate"]
          }).then(ok => {
            if (ok) {
              // Use current URL search (server endpoints accept same query params)
              const url = '/api/generate_report' + window.location.search;
              // Show brief info then start download in a new tab/window
              swal({title: "Generating...", text: "Preparing report...", icon: "info", buttons: false, timer: 900});
              // Trigger download
              window.open(url, '_blank');
            }
          });
        });
      }
    })();

    // Pagination: using server-side anchors (href="?page=N"), no JS click handler required.

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
    
    # Server-side pagination
    try:
        page = int(request.args.get('page', 1))
    except Exception:
        page = 1
    per_page = 10
    total_records = len(historical_data)
    total_pages = (total_records + per_page - 1) // per_page if total_records > 0 else 1
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start_idx = (page - 1) * per_page
    recent_data = historical_data[start_idx:start_idx + per_page]
    stats = calculate_statistics(historical_data)

    return render_template_string(HTML_TEMPLATE,
                                records=recent_data,
                                stats=stats,
                                total_records=total_records,
                                current_page=page,
                                total_pages=total_pages,
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
    per_page = 10
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    paginated_data = filtered_data[start_idx:end_idx]
    total_pages = (len(filtered_data) + per_page - 1) // per_page;
    
    # Calculate statistics for filtered data
    stats = calculate_statistics(filtered_data);
    
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
    output = io.StringIO();
    writer = csv.writer(output);
    
    # Write header
    writer.writerow(['Timestamp', 'Temperature', 'Fire Detected', 'Alert Level', 
                    'Location', 'Confidence', 'Camera Status', 'Thermal Status']);
    
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
    output.seek(0)
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
    json_str = json.dumps(export_data, indent=2)
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
        
    stats = calculate_statistics(historical_data);
    return jsonify(stats);

# --- New: generate a ZIP "report" containing CSV + JSON + summary ---
@app.route('/api/generate_report')
def api_generate_report():
    """Generate a ZIP report (CSV + JSON + summary) using the same filters as the page (query params)."""
    if not session.get('user'):
        return jsonify({'error': 'Authentication required'}), 401

    # collect filters from request.args (same as other endpoints)
    filters = {k: v for k, v in request.args.items() if v}
    filtered = filter_data(historical_data, filters)

    # CSV content
    csv_buf = io.StringIO()
    csv_writer = csv.writer(csv_buf)
    csv_writer.writerow(['Timestamp', 'Temperature', 'Fire Detected', 'Alert Level',
                         'Location', 'Confidence', 'Camera Status', 'Thermal Status'])
    for r in filtered:
        csv_writer.writerow([
            r['timestamp'],
            r['temperature'],
            'Yes' if r['fire_detected'] else 'No',
            r['alert_level'],
            r['location'],
            f"{r['confidence']:.2f}",
            r['camera_status'],
            r['thermal_status']
        ]);
    csv_data = csv_buf.getvalue().encode('utf-8');

    # JSON content
    export_data = {
        'export_info': {
            'generated_at': datetime.now().isoformat(),
            'total_records': len(filtered),
            'filters_applied': filters,
            'system': 'PyroSense Python Edition'
        },
        'statistics': calculate_statistics(filtered),
        'records': filtered
    }
    json_data = json.dumps(export_data, indent=2).encode('utf-8');

    # Summary text
    stats = calculate_statistics(filtered)
    summary_lines = [
        f"PyroSense Report - Generated: {datetime.now().isoformat()}",
        f"Filters: {json.dumps(filters) if filters else 'None'}",
        f"Total records: {len(filtered)}",
        f"Total fires: {stats.get('total_fires', 0)}",
        f"Average temperature: {stats.get('avg_temperature', 0)}",
        f"Total alerts: {stats.get('total_alerts', 0)}",
        "",
        "This ZIP contains:",
        " - report.csv (CSV export)",
        " - report.json (JSON export with metadata)",
        " - summary.txt (this summary)",
    ]
    summary_data = ("\r\n".join(summary_lines)).encode('utf-8');

    # Build ZIP in-memory
    zip_buffer = io.BytesIO();
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('report.csv', csv_data);
        zf.writestr('report.json', json_data);
        zf.writestr('summary.txt', summary_data);

    zip_buffer.seek(0);
    filename = f'pyrosense_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip';
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=filename
    );

# Add this route before the if __name__ == '__main__' block
@app.route('/dashboard')
def goto_dashboard():
    """Redirect to the main dashboard application"""
    return redirect('http://localhost:5000');

if __name__ == '__main__':
    print("🐍 Starting PyroSense History Python Flask Application...");
    print("📊 Historical Data Analysis System - Python Edition");
    print("=" * 60);
    print("History Page URL: http://localhost:5001");
    print("NOTE: Use the same login credentials as the login portal");
    print("Features:");
    print("  • 📅 Date range filtering");
    print("  • 🌡️ Temperature range filtering");
    print("  • 🚨 Alert level filtering");
    print("  • 🔥 Fire detection filtering");
    print("  • 📊 CSV/JSON data export");
    print("  • 📈 Real-time statistics");
    print("  • 🐍 Python-powered analytics");
    print("To stop server: Press Ctrl+C");
    print("=" * 60);

    # Run the Flask development server on port 5001
    app.run(debug=True, host='0.0.0.0', port=5001)
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
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    html, body {
      max-width: 100vw;
      overflow-x: hidden;
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
    
    .history-overlay {
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(10px);
      min-height: 100vh;
    }
    
    .history-title {
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
    
    .dashboard-button {
      padding: 8px 20px;
      border-radius: 25px;
      font-size: 0.85rem;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: all 0.3s ease;
      background: rgba(255,255,255,0.2);
      color: white;
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255, 255, 255, 0.3);
      font-weight: 600;
    }
    
    .dashboard-button:hover {
      background: rgba(255,255,255,0.3);
      transform: translateY(-2px);
      box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    
    main {
      max-width: 1200px;
      margin: 0 auto;
      padding: 30px 20px;
    }
    
    .stats-container {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 25px;
      margin-bottom: 30px;
    }
    
    .stat-card {
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(15px);
      border-radius: 20px;
      padding: 30px;
      text-align: center;
      box-shadow: 0 8px 25px rgba(0,0,0,0.15);
      border: 1px solid rgba(255, 255, 255, 0.2);
      transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    .stat-icon {
      font-size: 3rem;
      margin-bottom: 15px;
      display: block;
    }
    
    .stat-value {
      font-size: 2.5rem;
      font-weight: 700;
      background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin: 10px 0;
    }
    
    .stat-label {
      font-size: 1rem;
      color: #6c757d;
      font-weight: 600;
    }
    
    .filters-container {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 25px;
      margin-bottom: 30px;
    }
    
    .filter-card {
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(15px);
      border-radius: 20px;
      padding: 25px;
      box-shadow: 0 8px 25px rgba(0,0,0,0.15);
      border: 1px solid rgba(255, 255, 255, 0.2);
      transition: transform 0.3s ease;
    }
    
    .filter-title {
      font-size: 1rem;
      font-weight: 700;
      margin-bottom: 15px;
      display: flex;
      align-items: center;
      gap: 8px;
      color: #2d3748;
    }
    
    .filter-icon {
      opacity: 0.8;
      font-size: 1.1rem;
    }
    
    .custom-dropdown {
      position: relative;
      width: 100%;
      margin-bottom: 16px;
      font-family: inherit;
      z-index: 100;
    }
    .custom-dropdown .dropdown-toggle {
      width: 100%;
      padding: 14px 20px;
      background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 100%);
      color: #fff;
      border: none;
      border-radius: 14px;
      font-size: 1.05rem;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 4px 18px rgba(255, 107, 107, 0.12);
      transition: background 0.3s, box-shadow 0.3s;
      text-align: left;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      position: relative;
      outline: none;
      min-height: 52px; /* Add min-height for consistency */
    }
    .custom-dropdown .dropdown-toggle::after {
      content: "▼";
      font-size: 1em;
      color: #fff;
      margin-left: auto;
      transition: transform 0.3s;
      vertical-align: middle;
    }
    .custom-dropdown.open .dropdown-toggle::after {
      transform: rotate(-180deg);
    }
    .custom-dropdown .dropdown-menu {
      position: absolute;
      top: 110%;
      left: 0;
      width: 100%;
      background: #fff;
      border-radius: 14px;
      box-shadow: 0 12px 32px rgba(0,0,0,0.14);
      border: 1px solid #e2e8f0;
      padding: 12px;
      opacity: 0;
      visibility: hidden;
      transform: translateY(-10px) scale(0.98);
      transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
      z-index: 9999;
      max-height: 220px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
    }
    
    .custom-dropdown.open .dropdown-menu {
      opacity: 1;
      visibility: visible;
      transform: translateY(0) scale(1);
    }
    
    .custom-dropdown .dropdown-item {
      padding: 10px 16px;
      font-size: 1rem;
      cursor: pointer;
      transition: background 0.2s, color 0.2s;
      border: none;
      background: rgba(255, 107, 107, 0.05);
      font-weight: 500;
      text-align: center;
      white-space: nowrap;
      border-radius: 12px;
      margin: 0;
      width: 80%;
    }
    
    /* Update the Fire Detection dropdown items to be consistent width */
    #fireDetectionMenu .dropdown-item,
    #alertLevelMenu .dropdown-item {
      width: 80%;
    }
    
    .actions-container {
      display: flex;
      gap: 15px;
      margin-bottom: 30px;
      justify-content: center;
      flex-wrap: wrap;
    }
    
    .action-button {
      background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 50%, #ffeb3b 100%);
      color: white;
      border: none;
      padding: 12px 20px;
      border-radius: 25px;
      font-size: 0.9rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 600;
      text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
      box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3);
      transition: all 0.3s ease;
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
    
    .action-button.green {
      background: linear-gradient(135deg, #4CAF50 0%, #66bb6a 100%);
      box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);
    }
    
    .action-button.gray {
      background: linear-gradient(135deg, #6c757d 0%, #868e96 100%);
      box-shadow: 0 4px 15px rgba(108, 117, 125, 0.3);
    }
    
    .records-card {
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(15px);
      border-radius: 20px;
      overflow: hidden;
      box-shadow: 0 8px 25px rgba(0,0,0,0.15);
      margin-bottom: 30px;
      border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .records-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 20px 25px;
      background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
      border-bottom: 1px solid rgba(0,0,0,0.1);
    }
    
    .records-title {
      margin: 0;
      font-size: 1.3rem;
      font-weight: 700;
      color: #2d3748;
    }
    
    .records-count {
      font-size: 0.85rem;
      background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 100%);
      color: white;
      padding: 6px 15px;
      border-radius: 20px;
      font-weight: 600;
    }
    
    .records-table {
      width: 100%;
      border-collapse: collapse;
    }
    
    .records-table th {
      padding: 15px 12px;
      background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
      text-align: left;
      font-size: 0.9rem;
      font-weight: 700;
      color: #2d3748;
      border-bottom: 1px solid rgba(0,0,0,0.1);
    }
    
    .records-table td {
      padding: 15px 12px;
      border-bottom: 1px solid rgba(0,0,0,0.05);
      font-size: 0.9rem;
      transition: background-color 0.2s ease;
    }
    
    .records-table tr:hover td {
      background-color: rgba(255, 107, 107, 0.05);
    }
    
    .records-table tr:last-child td {
      border-bottom: none;
    }
    
    .status-text {
      font-weight: 600;
      padding: 4px 12px;
      border-radius: 15px;
      font-size: 0.8rem;
    }
    
    .status-text.ok {
      background: linear-gradient(135deg, rgba(76, 175, 80, 0.2) 0%, rgba(102, 187, 106, 0.2) 100%);
      color: #2e7d32;
    }
    
    .status-text.offline {
      background: linear-gradient(135deg, rgba(244, 67, 54, 0.2) 0%, rgba(229, 57, 53, 0.2) 100%);
      color: #c62828;
    }
    
    .pagination {
      display: flex;
      justify-content: center;
      margin-top: 30px;
    }
    
    .pagination-button {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      margin: 0 8px;
      background: rgba(255, 255, 255, 0.9);
      border: 2px solid #e2e8f0;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-weight: 600;
      transition: all 0.3s ease;
      backdrop-filter: blur(10px);
    }
    
    .pagination-button:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .pagination-button.active {
      background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 100%);
      color: white;
      border-color: transparent;
      box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3);
    }
    
    footer {
      text-align: center;
      padding: 25px;
      font-size: 0.9rem;
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
    
    /* Date Range Input Styling */
    .date-range-inputs {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    
    .date-input-group {
      display: flex;
      flex-direction: column;
      gap: 5px;
    }
    
    .date-input-label {
      font-size: 0.92rem;
      font-weight: 600;
      color: #ff6b6b;
      margin-bottom: 2px;
      margin-left: 2px;
      letter-spacing: 0.5px;
      text-align: left;
    }
    
    .date-input {
      width: 100%;
      padding: 12px 15px;
      border-radius: 12px;
      border: 2px solid #e2e8f0;
      background: white;
      cursor: pointer;
      font-size: 0.9rem;
      text-align: center;
      transition: all 0.3s ease;
    }
    
    .date-input:hover, .date-input:focus {
      border-color: #ff6b6b;
      box-shadow: 0 0 0 3px rgba(255, 107, 107, 0.1);
      outline: none;
    }
    
    .date-input::placeholder {
      color: #999;
    }
    
    /* MODAL CALENDAR - COMPLETELY FIXED */
    .calendar-modal-overlay {
      position: fixed !important;
      top: 0 !important;
      left: 0 !important;
      right: 0 !important;
      bottom: 0 !important;
      width: 100vw !important;
      height: 100vh !important;
      background: rgba(0, 0, 0, 0) !important;
      backdrop-filter: blur(0px) !important;
      z-index: 999999 !important;
      display: none !important;
      align-items: center !important; /* center vertically */
      justify-content: center !important; /* center horizontally */
      opacity: 0 !important;
      visibility: hidden !important;
      transition: all 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94) !important;
    }
    .calendar-modal-overlay.show {
      display: flex !important;
      opacity: 1 !important;
      visibility: visible !important;
      background: rgba(0, 0, 0, 0.15) !important;
      backdrop-filter: blur(2px) !important;
    }
    .calendar-modal {
      position: relative !important; /* center in overlay */
      margin: auto !important;
      width: 100%;
      max-width: 650px !important;
      min-width: 350px !important;
      max-height: 90vh !important;
      overflow: auto !important;
      z-index: 1000000 !important;
      transform: scale(0.95) translateY(-20px) !important;
      opacity: 0 !important;
      transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94) !important;
      box-shadow: 0 25px 50px rgba(0, 0, 0, 0.25) !important;
    }
    .calendar-modal-overlay.show .calendar-modal {
      transform: scale(1) translateY(0px) !important;
      opacity: 1 !important;
    }
    
    .calendar-header {
      background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 100%) !important;
      color: white !important;
      padding: 20px 25px !important;
      text-align: center !important;
      position: relative !important;
      border-radius: 8px 8px 0 0 !important;
    }
    
    .calendar-title {
      margin: 0 !important;
      font-size: 1.3rem !important;
      font-weight: 700 !important;
    }
    
    .calendar-subtitle {
      margin: 3px 0 0 0 !important;
      font-size: 0.85rem !important;
      opacity: 0.9 !important;
    }
    
    .calendar-close {
      position: absolute !important;
      top: 15px !important;
      right: 20px !important;
      background: none !important;
      border: none !important;
      color: white !important;
      font-size: 1.6rem !important;
      cursor: pointer !important;
      width: 30px !important;
      height: 30px !important;
      border-radius: 4px !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      transition: background 0.2s ease !important;
      z-index: 1000001 !important;
    }
    
    .calendar-close:hover {
      background: rgba(255, 255, 255, 0.2) !important;
    }
    
    .calendar-body {
      padding: 25px !important;
      background: white !important;
    }
    
    .calendar-info {
      background: #f8f9fa !important;
      border-radius: 6px !important;
      padding: 12px !important;
      margin-bottom: 18px !important;
      text-align: center !important;
      font-size: 0.85rem !important;
      color: #666 !important;
    }
    
    .calendar-info strong {
      color: #ff6b6b !important;
    }
    
    /* Date Input Section in Modal */
    .date-selection-inputs {
      display: grid !important;
      grid-template-columns: 1fr 1fr !important;
      gap: 15px !important;
      margin-bottom: 18px !important;
    }
    
    .date-input-group {
      display: flex !important;
      flex-direction: column !important;
    }
    
    .date-input-label {
      font-size: 0.8rem !important;
      font-weight: 600 !important;
      color: #666 !important;
      margin-bottom: 6px !important;
      text-align: left !important;
    }
    
    .date-input-field {
      padding: 10px 12px !important;
      border: 2px solid #e0e0e0 !important;
      border-radius: 6px !important;
      font-size: 0.85rem !important;
      text-align: center !important;
      background: #f8f9fa !important;
      color: #666 !important;
      font-weight: 500 !important;
      min-height: 40px !important;
    }
    
    .date-input-field.active {
      border-color: #ff6b6b !important;
      background: white !important;
      color: #333 !important;
      box-shadow: 0 0 0 3px rgba(255, 107, 107, 0.1) !important;
    }
    
    .selection-mode {
      display: flex !important;
      background: #f0f0f0 !important;
      border-radius: 6px !important;
      margin-bottom: 18px !important;
      overflow: hidden !important;
    }
    
    .mode-tab {
      flex: 1 !important;
      padding: 10px 12px !important;
      text-align: center !important;
      cursor: pointer !important;
      font-weight: 600 !important;
      font-size: 0.85rem !important;
      color: #666 !important;
      transition: all 0.2s ease !important;
    }
    
    .mode-tab.active {
      background: #ff6b6b !important;
      color: white !important;
    }
    
    .month-navigation {
      display: flex !important;
      justify-content: space-between !important;
      align-items: center !important;
      margin-bottom: 18px !important;
    }
    
    .month-nav-btn {
      background: none !important;
      border: none !important;
      font-size: 1.4rem !important;
      cursor: pointer !important;
      color: #666 !important;
      width: 36px !important;
      height: 36px !important;
      border-radius: 6px !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      transition: all 0.2s ease !important;
    }
    
    .month-nav-btn:hover {
      background: #f0f0f0 !important;
      color: #ff6b6b !important;
    }
    
    .current-month {
      font-size: 1.1rem !important;
      font-weight: 700 !important;
      color: #333 !important;
    }
    
    .calendar-grid {
      width: 100% !important;
      border-collapse: collapse !important;
      margin-bottom: 18px !important;
      background: white !important;
      border: 1px solid #e0e0e0 !important;
      border-radius: 6px !important;
      overflow: hidden !important;
    }
    
    .calendar-grid th {
      padding: 12px 6px !important;
      text-align: center !important;
      font-weight: 600 !important;
      font-size: 0.8rem !important;
      color: #666 !important;
      border-bottom: 2px solid #e0e0e0 !important;
      background: #f8f9fa !important;
    }
    
    .calendar-grid td {
      padding: 10px 6px !important;
      text-align: center !important;
      cursor: pointer !important;
      font-size: 0.85rem !important;
      font-weight: 500 !important;
      transition: all 0.2s ease !important;
      border-radius: 4px !important;
      position: relative !important;
      width: 14.28% !important;
      height: 36px !important;
      vertical-align: middle !important;
      background: white !important;
      border-right: 1px solid #f0f0f0 !important;
    }
    
    .calendar-grid td:last-child {
      border-right: none !important;
    }
    
    .calendar-grid td:hover:not(.empty):not(.disabled) {
      background: #f0f0f0 !important;
      color: #ff6b6b !important;
      transform: scale(1.05) !important;
    }
    
    .calendar-grid td.empty {
      color: transparent !important;
      cursor: default !important;
      pointer-events: none !important;
    }
    
    .calendar-grid td.disabled {
      color: #ccc !important;
      cursor: not-allowed !important;
    }
    
    .calendar-grid td.today {
      background: #e3f2fd !important;
      color: #1976d2 !important;
      font-weight: 700 !important;
      border: none !important;
      box-shadow: none !important;
      outline: none !important;
      position: relative !important;
    }
    
    .calendar-grid td.today::after {
      display: none !important;
    }
    
    .calendar-grid td.today::before {
      display: none !important;
    }
    
    .calendar-grid td.today:hover {
      background: #bbdefb !important;
      color: #1976d2 !important;
      transform: scale(1.05) !important;
      border: none !important;
      box-shadow: none !important;
      outline: none !important;
    }
    
    .calendar-grid td.today:focus {
      border: none !important;
      box-shadow: none !important;
      outline: none !important;
    }
    
    .calendar-grid td.today:active {
      border: none !important;
      box-shadow: none !important;
      outline: none !important;
    }
    
    /* Force remove any pseudo-elements that might be causing the blue outline */
    .calendar-grid td.today *,
    .calendar-grid td.today *::before,
    .calendar-grid td.today *::after {
      border: none !important;
      box-shadow: none !important;
      outline: none !important;
    }
    
    .calendar-footer {
      background: #f8f9fa !important;
      padding: 15px 25px !important;
      display: flex !important;
      justify-content: space-between !important;
      align-items: center !important;
      border-top: 1px solid #e0e0e0 !important;
      border-radius: 0 0 8px 8px !important;
    }
    
    .selected-range {
      font-size: 0.8rem !important;
      color: #666 !important;
    }
    
    .calendar-actions {
      display: flex !important;
      gap: 8px !important;
    }
    
    .calendar-btn {
      padding: 8px 16px !important;
      border: none !important;
      border-radius: 6px !important;
      cursor: pointer !important;
      font-weight: 600 !important;
      font-size: 0.85rem !important;
      transition: all 0.2s ease !important;
    }
    
    .calendar-btn.cancel {
      background: #f5f5f5 !important;
      color: #666 !important;
      border: 1px solid #ddd !important;
    }
    
    .calendar-btn.cancel:hover {
      background: #e0e0e0 !important;
    }
    
    .calendar-btn.apply {
      background: #ff6b6b !important;
      color: white !important;
    }
    
    .calendar-btn.apply:hover {
      background: #ff5252 !important;
    }
    
    .calendar-btn.today {
      background: #e3f2fd !important;
      color: #1976d2 !important;
      border: 1px solid #bbdefb !important;
    }
    
    .calendar-btn.today:hover {
      background: #bbdefb !important;
    }
    
    /* Force visibility */
    .calendar-modal-overlay.show {
      visibility: visible !important;
      pointer-events: all !important;
    }

    /* Add style for temperature range inputs */
    .temp-range-group {
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin-top: 8px;
    }
    .temp-range-label {
      font-size: 0.92rem;
      font-weight: 600;
      color: #ff6b6b;
      margin-bottom: 2px;
      margin-left: 2px;
      letter-spacing: 0.5px;
    }
    .temp-range-input {
      width: 100%;
      padding: 12px 15px;
      border-radius: 12px;
      border: 2px solid #e2e8f0;
      background: #fff;
      font-size: 1rem;
      color: #333;
      text-align: center;
      transition: border-color 0.3s, box-shadow 0.3s;
      box-shadow: 0 2px 4px rgba(255,107,107,0.04);
      outline: none;
    }
    .temp-range-input:focus {
      border-color: #ff6b6b;
      box-shadow: 0 0 0 3px rgba(255,107,107,0.10);
    }
  </style>
</head>
<body>
  <div class="history-overlay">
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
          <a href="http://localhost:5002" class="dashboard-button">🏠 Back to Dashboard</a>
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
          <div class="date-input-group">
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
    PyroSense 2025 © All rights reserved - Python Flask Edition
  </footer>
  
  <div class="attribution">
    <a href="https://www.freepik.com/free-vector/minimalist-background-gradient-design-style_34345006.htm">Background by AndreaCharlesta on Freepik</a>
  </div>

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

    // Action button functionality
    document.getElementById('refreshData').addEventListener('click', function() {
      location.reload();
    });

    document.getElementById('exportCsv').addEventListener('click', function() {
      window.open('/api/export/csv', '_blank');
    });

    document.getElementById('exportJson').addEventListener('click', function() {
      window.open('/api/export/json', '_blank');
    });

    document.getElementById('clearFilters').addEventListener('click', function() {
      // Clear all filter dropdowns
      document.getElementById('minTemperature').value = '';
      document.getElementById('maxTemperature').value = '';
      document.getElementById('alertLevel').value = '';
      document.getElementById('fireDetection').value = '';
      document.getElementById('startDate').value = '';
      document.getElementById('endDate').value = '';
      
      // Clear URL parameters
      const url = new URL(window.location);
      url.search = '';
      window.history.replaceState({}, '', url);
      
      alert('Filters cleared!');
    });

    document.getElementById('generateReport').addEventListener('click', function() {
      alert('Report generation feature would be implemented here in a full version.');
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
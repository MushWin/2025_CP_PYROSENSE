"""
PyroSense - History Logic
All data generation, filtering, and statistics functions for history page
"""

from datetime import datetime, timedelta
import random

def generate_historical_data():
    """Generate realistic historical fire detection data with fire size metrics"""
    data = []
    base_date = datetime.now() - timedelta(days=30)
    
    for i in range(720):  # 30 days * 24 hours
        timestamp = base_date + timedelta(hours=i)
        
        hour = timestamp.hour
        base_temp = 25 + 10 * (1 + 0.3 * random.random()) * abs(12 - hour) / 12
        temp_variation = (random.random() - 0.5) * 5
        temperature = round(base_temp + temp_variation, 1)
        
        fire_detected = temperature > 65 and random.random() < 0.02
        fire_size_pct = 0.0
        
        if fire_detected:
            if temperature > 90:
                fire_size_pct = round(random.uniform(40, 60), 1)
            elif temperature > 80:
                fire_size_pct = round(random.uniform(25, 40), 1)
            elif temperature > 70:
                fire_size_pct = round(random.uniform(15, 25), 1)
            else:
                fire_size_pct = round(random.uniform(5, 15), 1)
        
        if fire_detected:
            if fire_size_pct > 40:
                alert_level = "Critical"
            elif fire_size_pct > 25:
                alert_level = "Warning"
            elif fire_size_pct > 15:
                alert_level = "Caution"
            else:
                alert_level = "Active"
        elif temperature > 50:
            alert_level = "Caution"
        elif temperature > 40:
            alert_level = "Active"
        else:
            alert_level = "None"
        
        has_stove = random.random() < 0.3
        has_candle = random.random() < 0.1
        has_person = random.random() < 0.4
        
        if fire_detected and has_person and alert_level != "Critical":
            alert_level = "Warning"
        
        camera_status = "Offline" if random.random() < 0.05 else "Online"
        thermal_status = "Error" if random.random() < 0.03 else "OK"
        
        data.append({
            'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'temperature': temperature,
            'fire_detected': fire_detected,
            'fire_size_pct': fire_size_pct,
            'alert_level': alert_level,
            'has_stove': has_stove,
            'has_candle': has_candle,
            'has_person': has_person,
            'camera_status': camera_status,
            'thermal_status': thermal_status,
            'location': f"Sector {random.randint(1, 8)}",
            'confidence': round(random.uniform(0.7, 0.99), 2) if fire_detected else round(random.uniform(0.1, 0.3), 2)
        })
    
    return data

def calculate_statistics(data):
    """Calculate statistics with fire size metrics"""
    if not data:
        return {
            'total_fires': 0,
            'avg_temperature': 0,
            'total_alerts': 0,
            'uptime': 0,
            'avg_fire_size': 0,
            'critical_alerts': 0,
            'warning_alerts': 0,
            'caution_alerts': 0
        }
    
    total_fires = sum(1 for record in data if record['fire_detected'])
    avg_temperature = round(sum(record['temperature'] for record in data) / len(data), 1)
    total_alerts = sum(1 for record in data if record['alert_level'] != 'None')
    
    fire_sizes = [record.get('fire_size_pct', 0) for record in data if record['fire_detected']]
    avg_fire_size = round(sum(fire_sizes) / len(fire_sizes), 1) if fire_sizes else 0
    
    critical_alerts = sum(1 for record in data if record['alert_level'] == 'Critical')
    warning_alerts = sum(1 for record in data if record['alert_level'] == 'Warning')
    caution_alerts = sum(1 for record in data if record['alert_level'] == 'Caution')
    
    online_records = sum(1 for record in data 
                        if record['camera_status'] == 'Online' and record['thermal_status'] == 'OK')
    uptime = round((online_records / len(data)) * 100, 1) if data else 0
    
    return {
        'total_fires': total_fires,
        'avg_temperature': avg_temperature,
        'total_alerts': total_alerts,
        'uptime': uptime,
        'avg_fire_size': avg_fire_size,
        'critical_alerts': critical_alerts,
        'warning_alerts': warning_alerts,
        'caution_alerts': caution_alerts
    }

def filter_data(data, filters):
    """Apply filters with new alert levels and fire size"""
    filtered_data = data.copy()
    
    if filters.get('start_date'):
        start_date = datetime.fromisoformat(filters['start_date'])
        filtered_data = [r for r in filtered_data 
                        if datetime.fromisoformat(r['timestamp']) >= start_date]
    
    if filters.get('end_date'):
        end_date = datetime.fromisoformat(filters['end_date'])
        filtered_data = [r for r in filtered_data 
                        if datetime.fromisoformat(r['timestamp']) <= end_date]
    
    if filters.get('min_temp'):
        min_temp = float(filters['min_temp'])
        filtered_data = [r for r in filtered_data if r['temperature'] >= min_temp]
    
    if filters.get('max_temp'):
        max_temp = float(filters['max_temp'])
        filtered_data = [r for r in filtered_data if r['temperature'] <= max_temp]
    
    if filters.get('alert_level'):
        alert_level = filters['alert_level'].capitalize()
        filtered_data = [r for r in filtered_data if r['alert_level'] == alert_level]
    
    if filters.get('fire_detected'):
        fire_detected_str = filters['fire_detected'].lower()
        if fire_detected_str in ['true', 'yes', '1']:
            filtered_data = [r for r in filtered_data if r['fire_detected']]
        elif fire_detected_str in ['false', 'no', '0']:
            filtered_data = [r for r in filtered_data if not r['fire_detected']]
    
    if filters.get('min_fire_size'):
        min_size = float(filters['min_fire_size'])
        filtered_data = [r for r in filtered_data if r.get('fire_size_pct', 0) >= min_size]
    
    if filters.get('max_fire_size'):
        max_size = float(filters['max_fire_size'])
        filtered_data = [r for r in filtered_data if r.get('fire_size_pct', 0) <= max_size]
    
    return filtered_data

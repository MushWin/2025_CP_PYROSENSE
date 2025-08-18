# PyroSense - Fire Detection & Management System

A modern web-based fire detection and management system built with Python Flask.

## 🔥 Features

- **Login System** - Secure authentication portal (UI demo)
- **Dashboard** - Real-time fire detection monitoring
- **History** - Historical data and incident tracking
- **Responsive Design** - Works on desktop and mobile devices

## 📋 Prerequisites

Before running PyroSense, make sure you have the following installed:

- **Python 3.7+** - [Download Python](https://www.python.org/downloads/)
- **XAMPP** (optional) - For local web server environment
- **Flask** - Python web framework

## 🚀 Installation

1. **Clone or download** the PyroSense project to your local machine:
   ```
   c:\xampp\htdocs\Pyrosense\
   ```

2. **Install Python dependencies:**
   ```bash
   pip install flask requests
   ```

## ▶️ How to Run PyroSense

PyroSense consists of three separate applications that run on different ports:

### 1. Login Application (Port 5000)
```bash
cd c:\xampp\htdocs\Pyrosense
python login.py
```
- **URL:** http://localhost:5000
- **Purpose:** User authentication and login portal
- **Note:** This is a UI-only demo - any username/password will work

### 2. Dashboard Application (Port 5002)
```bash
cd c:\xampp\htdocs\Pyrosense
python dashboard.py
```
- **URL:** http://localhost:5002
- **Purpose:** Main dashboard with fire detection monitoring
- **Note:** Must be running for login redirection to work

### 3. History Application (Port 5003)
```bash
cd c:\xampp\htdocs\Pyrosense
python history.py
```
- **URL:** http://localhost:5003
- **Purpose:** Historical data and incident tracking
- **Note:** Optional - for viewing historical fire detection data

## 🔄 Complete Startup Sequence

To run the complete PyroSense system:

1. **Start the Login app** (in terminal/command prompt 1):
   ```bash
   python login.py
   ```

2. **Start the Dashboard app** (in terminal/command prompt 2):
   ```bash
   python dashboard.py
   ```

3. **Start the History app** (in terminal/command prompt 3):
   ```bash
   python history.py
   ```

4. **Access the system:**
   - Go to http://localhost:5000
   - Login with any username/password
   - You'll be redirected to the dashboard

## 🛑 Stopping the Applications

To stop any application:
- Press `Ctrl+C` in the terminal where the app is running
- Or close the terminal window

## 🌐 Port Configuration

| Application | Port | URL |
|-------------|------|-----|
| Login | 5000 | http://localhost:5000 |
| Dashboard | 5002 | http://localhost:5002 |
| History | 5003 | http://localhost:5003 |

## 📱 Usage

1. **Login:** Start at http://localhost:5000 and enter any credentials
2. **Dashboard:** Monitor real-time fire detection data
3. **History:** View historical incidents and data
4. **Logout:** Use the logout option to return to login page

## 🎨 Design Credits

- **Background Design:** [AndreaCharlesta on Freepik](https://www.freepik.com/free-vector/minimalist-background-gradient-design-style_34345006.htm)

## 🔧 Troubleshooting

### Common Issues:

1. **"Port already in use" error:**
   - Make sure no other applications are using ports 5000, 5002, or 5003
   - Kill any existing Python processes using these ports

2. **Dashboard/History not accessible:**
   - Ensure all three applications are running simultaneously
   - Check that you're using the correct port numbers

3. **Login doesn't redirect:**
   - Make sure dashboard.py is running on port 5002
   - Check the console for any error messages

### System Requirements:
- **OS:** Windows, macOS, or Linux
- **Python:** Version 3.7 or higher
- **RAM:** Minimum 512MB available
- **Storage:** 50MB free space

## 📝 Notes

- This is a **demonstration/UI prototype** system
- Login authentication is for UI purposes only
- All components must be running for full functionality
- Data is not persistent between sessions (demo mode)

## 🆘 Support

If you encounter any issues:
1. Check that all Python dependencies are installed
2. Verify all three applications are running
3. Check console output for error messages
4. Ensure ports 5000, 5002, and 5003 are available

---

**PyroSense** - Fire Detection & Management System  
*Built with Python Flask*

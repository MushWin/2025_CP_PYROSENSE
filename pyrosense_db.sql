-- SQLite DDL for PyroSense

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Users (
    UserID INTEGER PRIMARY KEY AUTOINCREMENT,
    Username TEXT UNIQUE NOT NULL,
    Password TEXT NOT NULL,
    Email TEXT UNIQUE,
    UserRole TEXT DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS Devices (
    DeviceID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT,
    Location TEXT,
    Type TEXT,
    Status TEXT
);

CREATE TABLE IF NOT EXISTS Sensor_Readings (
    ReadingID INTEGER PRIMARY KEY AUTOINCREMENT,
    Timestamp DATETIME,
    TemperatureMatrix TEXT,
    ImageFrame TEXT,
    DeviceID INTEGER,
    FOREIGN KEY (DeviceID) REFERENCES Devices(DeviceID) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS Alert_Events (
    AlertID INTEGER PRIMARY KEY AUTOINCREMENT,
    ReadingID INTEGER,
    UserID INTEGER,
    Type TEXT,
    Confidence REAL,
    Timestamp DATETIME,
    Status TEXT,
    FOREIGN KEY (ReadingID) REFERENCES Sensor_Readings(ReadingID) ON DELETE SET NULL,
    FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS System_Logs (
    LogID INTEGER PRIMARY KEY AUTOINCREMENT,
    Timestamp DATETIME,
    EventType TEXT,
    Description TEXT,
    DeviceID INTEGER,
    UserID INTEGER,
    FOREIGN KEY (DeviceID) REFERENCES Devices(DeviceID) ON DELETE SET NULL,
    FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE SET NULL
);

-- PasswordResets table for password reset tokens
CREATE TABLE IF NOT EXISTS PasswordResets (
    Token TEXT PRIMARY KEY,
    UserID INTEGER NOT NULL,
    ExpiresAt TEXT NOT NULL,
    FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp ON Sensor_Readings (Timestamp);
CREATE INDEX IF NOT EXISTS idx_alert_events_timestamp ON Alert_Events (Timestamp);
CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp ON System_Logs (Timestamp);
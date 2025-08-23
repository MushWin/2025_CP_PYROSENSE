db pyrosense

-- Initial schema for PyroSense IoT Fire Detection System

Table Users {
  UserID int [pk]
  Username varchar
  Password varchar
  Email varchar -- Added for password reset
}

Table Devices {
  DeviceID int [pk]
  Name varchar         -- Device name/label
  Location varchar     -- Physical location
  Type varchar         -- e.g., 'Thermal', 'Camera', etc.
  Status varchar
}

Table Sensor_Readings {
  ReadingID int [pk]
  Timestamp datetime
  TemperatureMatrix text
  ImageFrame text
  DeviceID int [ref: > Devices.DeviceID]
}

Table Alert_Events {
  AlertID int [pk]
  ReadingID int [ref: > Sensor_Readings.ReadingID]
  UserID int [ref: > Users.UserID]    -- Who acknowledged/handled
  Type varchar
  Confidence float
  Timestamp datetime
  Status varchar
}

Table System_Logs {
  LogID int [pk]
  Timestamp datetime
  EventType varchar
  Description text
  DeviceID int [ref: > Devices.DeviceID]
  UserID int [ref: > Users.UserID]    -- Who performed the action
}

-- You may want to add indexes for performance on Timestamp, DeviceID, etc.
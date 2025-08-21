db pyrosense

intial 

Table Users {
  UserID int [pk]
  Username varchar
  Password varchar
}

Table Devices {
  DeviceID int [pk]
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
}
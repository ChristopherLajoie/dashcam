#!/bin/bash
# Wait for network to be ready
sleep 30

# Ensure services are running
systemctl start ipcamera-recorder.service
systemctl start ipcamera-web.service

# Log startup
echo "$(date): IP Camera system started" >> /opt/ipcamera/logs/system.log

#!/bin/bash
echo "Installing IP Camera services..."

# Copy service files
sudo cp /opt/ipcamera/config/ipcamera-recorder.service /etc/systemd/system/
sudo cp /opt/ipcamera/config/ipcamera-web.service /etc/systemd/system/

# Set proper ownership
sudo chown -R foxtrot /opt/ipcamera

# Reload systemd and enable services
sudo systemctl daemon-reload
sudo systemctl enable ipcamera-recorder.service
sudo systemctl enable ipcamera-web.service

# Start services
sudo systemctl start ipcamera-recorder.service
sudo systemctl start ipcamera-web.service

echo "Services installed and started!"
echo "Recorder status: $(sudo systemctl is-active ipcamera-recorder)"
echo "Web server status: $(sudo systemctl is-active ipcamera-web)"
echo ""
echo "Access the web interface at: http://10.42.0.1:5000"
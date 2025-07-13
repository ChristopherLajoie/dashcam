#!/bin/bash
echo "Setting up IP Camera system (using existing uap0 hotspot)..."

# Install and start services
echo "Installing system services..."
/opt/ipcamera/scripts/install_services.sh

# Create startup script that runs on boot
cat > /opt/ipcamera/scripts/startup.sh << 'STARTUP'
#!/bin/bash
# Wait for network to be ready
sleep 30

# Ensure services are running
systemctl start ipcamera-recorder.service
systemctl start ipcamera-web.service

# Log startup
echo "$(date): IP Camera system started" >> /opt/ipcamera/logs/system.log
STARTUP

chmod +x /opt/ipcamera/scripts/startup.sh

# Add startup script to crontab
(crontab -l 2>/dev/null; echo "@reboot /opt/ipcamera/scripts/startup.sh") | crontab -

echo ""
echo "=========================================="
echo "IP Camera System Setup Complete!"
echo "=========================================="
echo ""
echo "Using existing hotspot:"
echo "  Interface: uap0"
echo "  IP: 10.42.0.1"
echo ""
echo "Web Interface:"
echo "  URL: http://10.42.0.1:5000"
echo ""
echo "RTSP Camera:"
echo "  URL: rtsp://192.168.1.18:554/1/h264major"
echo ""
echo "To start using:"
echo "1. Make sure your phone is connected to the existing hotspot"
echo "2. Open browser and go to http://10.42.0.1:5000"
echo "3. Access live stream and recordings"
echo ""
echo "System will start automatically on boot!"
echo ""
echo "Check status with: /opt/ipcamera/scripts/status.sh"
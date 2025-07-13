#!/bin/bash
echo "=== IP Camera System Status ==="
echo ""
echo "Services:"
echo "  Recorder: $(sudo systemctl is-active ipcamera-recorder)"
echo "  Web Server: $(sudo systemctl is-active ipcamera-web)"
echo ""
echo "Network (uap0):"
ip addr show uap0 | grep -E "inet |state"
echo ""
echo "Hotspot Status:"
if ip addr show uap0 | grep -q "10.42.0.1"; then
    echo "  ✅ Hotspot active on uap0 (10.42.0.1)"
else
    echo "  ❌ Hotspot not detected"
fi
echo ""
echo "Disk Usage:"
df -h /opt/ipcamera/recordings
echo ""
echo "Recent Recordings:"
find /opt/ipcamera/recordings -name "*.mp4" -printf "%T@ %Tc %p\n" 2>/dev/null | sort -n | tail -5
echo ""
echo "Camera Connection Test:"
timeout 10 ffprobe rtsp://192.168.1.18:554/1/h264major 2>&1 | grep -q "Stream" && echo "  ✅ Camera accessible" || echo "  ❌ Camera connection failed"
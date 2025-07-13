import os
import json
import subprocess
import threading
import time
from datetime import datetime
from flask import Flask, render_template, Response, send_file, jsonify, request
from flask_cors import CORS

app = Flask(__name__, template_folder='/opt/ipcamera/web')
CORS(app)

# Configuration
RTSP_URL = "rtsp://192.168.1.18:554/1/h264major"
RECORDINGS_DIR = "/opt/ipcamera/recordings"
LOGS_DIR = "/opt/ipcamera/logs"

class StreamManager:
    def __init__(self):
        self.process = None
        self.streaming = False
    
    def start_stream(self):
        """Start FFmpeg process for live streaming"""
        if self.streaming:
            return
        
        cmd = [
            'ffmpeg',
            '-i', RTSP_URL,
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-c:a', 'aac',
            '-f', 'flv',
            '-'
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.streaming = True
        except Exception as e:
            print(f"Stream start error: {e}")
    
    def stop_stream(self):
        """Stop FFmpeg process"""
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
        self.streaming = False
    
    def get_frame(self):
        """Get video frame for MJPEG stream"""
        if not self.streaming:
            self.start_stream()
        
        if self.process and self.process.stdout:
            return self.process.stdout.read(4096)
        return b''

stream_manager = StreamManager()

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/live')
def live():
    """Live streaming page"""
    return render_template('live.html')

@app.route('/recordings')
def recordings():
    """Recordings page"""
    return render_template('recordings.html')

@app.route('/api/stream')  
def video_stream():
    """Stream individual JPEG frames"""
    def generate():
        cmd = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',
            '-buffer_size', '2048000',    # Increased buffer
            '-max_delay', '100000',       # Reduced delay
            '-fflags', 'nobuffer',        # No buffering
            '-flags', 'low_delay',        # Low delay mode
            '-i', RTSP_URL,
            '-vf', 'scale=640:480',
            '-q:v', '10',                 # Slightly lower quality for performance
            '-r', '30',                    # 8 FPS instead of 2
            '-f', 'image2pipe',
            '-vcodec', 'mjpeg',
            '-'
        ]
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        try:
            buffer = b''
            while True:
                chunk = process.stdout.read(1024)
                if not chunk:
                    break
                    
                buffer += chunk
                
                # Look for complete JPEG frames
                while True:
                    start = buffer.find(b'\xff\xd8')  # JPEG start
                    if start == -1:
                        break
                    end = buffer.find(b'\xff\xd9', start)  # JPEG end  
                    if end == -1:
                        break
                        
                    # Found complete JPEG frame
                    jpeg_frame = buffer[start:end+2]
                    buffer = buffer[end+2:]
                    
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n'
                           b'Content-Length: ' + str(len(jpeg_frame)).encode() + b'\r\n\r\n' + 
                           jpeg_frame + b'\r\n')
        finally:
            process.terminate()
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/snapshot')
def get_snapshot():
    """Get a single JPEG snapshot - better for mobile testing"""
    cmd = [
        'ffmpeg',
        '-rtsp_transport', 'tcp',
        '-buffer_size', '1024000',
        '-max_delay', '500000',
        '-i', RTSP_URL,
        '-vf', 'scale=640:480',
        '-q:v', '8',
        '-frames:v', '1',  # Just one frame
        '-f', 'image2pipe',
        '-vcodec', 'mjpeg',
        '-'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0 and result.stdout:
            return Response(result.stdout, mimetype='image/jpeg')
        else:
            return "Error capturing frame", 500
    except subprocess.TimeoutExpired:
        return "Timeout capturing frame", 500

@app.route('/api/recordings')
def get_recordings():
    """Get list of all recordings"""
    recordings = {}
    
    if os.path.exists(RECORDINGS_DIR):
        for date_dir in sorted(os.listdir(RECORDINGS_DIR), reverse=True):
            date_path = os.path.join(RECORDINGS_DIR, date_dir)
            if os.path.isdir(date_path):
                metadata_file = os.path.join(date_path, 'metadata.json')
                if os.path.exists(metadata_file):
                    try:
                        with open(metadata_file, 'r') as f:
                            recordings[date_dir] = json.load(f)
                    except:
                        # Fallback: scan directory for MP4 files
                        files = []
                        for f in os.listdir(date_path):
                            if f.endswith('.mp4'):
                                file_path = os.path.join(date_path, f)
                                stat = os.stat(file_path)
                                files.append({
                                    'filename': f,
                                    'start_time': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                    'size': stat.st_size
                                })
                        recordings[date_dir] = {'recordings': files}
    
    return jsonify(recordings)

@app.route('/api/download/<date>/<filename>')
def download_recording(date, filename):
    """Download a specific recording"""
    file_path = os.path.join(RECORDINGS_DIR, date, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "File not found", 404

@app.route('/api/play/<date>/<filename>')
def play_recording(date, filename):
    """Stream a recording for playback"""
    file_path = os.path.join(RECORDINGS_DIR, date, filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    return "File not found", 404

@app.route('/api/status')
def get_status():
    """Get system status"""
    import psutil
    
    # Disk usage
    usage = psutil.disk_usage(RECORDINGS_DIR)
    disk_usage = {
        'total': usage.total,
        'used': usage.used,
        'free': usage.free,
        'percent': (usage.used / usage.total) * 100
    }
    
    # Recording service status
    recording_status = "unknown"
    try:
        result = subprocess.run(['systemctl', 'is-active', 'ipcamera-recorder'], 
                              capture_output=True, text=True)
        recording_status = result.stdout.strip()
    except:
        pass
    
    # Network info
    network_info = {}
    try:
        result = subprocess.run(['ip', 'addr', 'show', 'uap0'], 
                              capture_output=True, text=True)
        if '10.42.0.1' in result.stdout:
            network_info['hotspot'] = 'active'
            network_info['ip'] = '10.42.0.1'
        else:
            network_info['hotspot'] = 'inactive'
    except:
        network_info['hotspot'] = 'unknown'
    
    return jsonify({
        'disk_usage': disk_usage,
        'recording_status': recording_status,
        'network': network_info,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/logs')
def get_logs():
    """Get recent log entries"""
    log_file = os.path.join(LOGS_DIR, 'recorder.log')
    logs = []
    
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                # Get last 50 lines
                logs = [line.strip() for line in lines[-50:]]
        except:
            pass
    
    return jsonify(logs)

if __name__ == '__main__':
    # Bind to uap0 interface IP
    app.run(host='0.0.0.0', port=5000, debug=False)
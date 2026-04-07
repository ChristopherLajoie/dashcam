import glob
import json
import os
import subprocess
import threading
import time
from datetime import datetime
from flask import Flask, render_template, Response, send_file, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__, template_folder="/opt/ipcamera/web")
CORS(app)

RTSP_URL = "rtsp://192.168.1.18:554/1/h264major"
RECORDINGS_DIR = "/opt/ipcamera/recordings"
LOGS_DIR = "/opt/ipcamera/logs"
HLS_DIR = "/tmp/hls"

hls_process = None
hls_lock = threading.Lock()

# Cached stream info so we don't probe on every request
_stream_info_cache = {"fps": None, "resolution": None, "fetched_at": 0}
_stream_info_lock = threading.Lock()


def purge_hls_dir():
    for f in glob.glob(os.path.join(HLS_DIR, "*.ts")):
        try:
            os.remove(f)
        except OSError:
            pass
    for f in glob.glob(os.path.join(HLS_DIR, "*.tmp")):
        try:
            os.remove(f)
        except OSError:
            pass


def start_hls():
    global hls_process
    os.makedirs(HLS_DIR, exist_ok=True)
    purge_hls_dir()
    cmd = [
        "ffmpeg",
        "-rtsp_transport", "tcp",
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-i", RTSP_URL,
        "-c:v", "copy",
        "-an",
        "-f", "hls",
        "-hls_time", "2",
        "-hls_list_size", "5",
        "-hls_flags", "delete_segments+omit_endlist+discont_start",
        "-hls_segment_filename", f"{HLS_DIR}/seg%03d.ts",
        f"{HLS_DIR}/stream.m3u8",
    ]
    os.makedirs(LOGS_DIR, exist_ok=True)
    ffmpeg_log = open(os.path.join(LOGS_DIR, "ffmpeg_stream.log"), "w")
    hls_process = subprocess.Popen(cmd, stdout=ffmpeg_log, stderr=ffmpeg_log)


def stop_hls():
    global hls_process
    if hls_process:
        hls_process.kill()
        hls_process.wait()
        hls_process = None


def probe_stream_info():
    """Use ffprobe to get FPS and resolution from the RTSP stream. Cached for 60s."""
    with _stream_info_lock:
        now = time.time()
        if now - _stream_info_cache["fetched_at"] < 60 and _stream_info_cache["fps"]:
            return _stream_info_cache.copy()

        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-rtsp_transport", "tcp",
                "-show_streams",
                "-select_streams", "v:0",
                "-of", "json",
                RTSP_URL,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                stream = data.get("streams", [{}])[0]

                width  = stream.get("width", 0)
                height = stream.get("height", 0)

                # fps is stored as a fraction e.g. "15/1" or "30000/1001"
                fps_raw = stream.get("r_frame_rate", "0/1")
                num, den = fps_raw.split("/")
                fps = round(int(num) / int(den), 1) if int(den) else 0

                _stream_info_cache["fps"]        = fps
                _stream_info_cache["resolution"] = f"{width}x{height}"
                _stream_info_cache["fetched_at"] = now
        except Exception:
            pass

        return _stream_info_cache.copy()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/recordings")
def recordings():
    return render_template("recordings.html")


@app.route("/api/stream/start", methods=["POST"])
def stream_start():
    with hls_lock:
        stop_hls()
        start_hls()
    return jsonify({"status": "started"})


@app.route("/api/stream/stop", methods=["POST"])
def stream_stop():
    with hls_lock:
        stop_hls()
        purge_hls_dir()
    return jsonify({"status": "stopped"})


@app.route("/api/stream/status")
def stream_status():
    m3u8 = os.path.join(HLS_DIR, "stream.m3u8")
    if not os.path.exists(m3u8):
        return jsonify({"ready": False, "reason": "playlist_missing"})
    segments = glob.glob(os.path.join(HLS_DIR, "seg*.ts"))
    if len(segments) < 2:
        return jsonify({"ready": False, "reason": "segments_building", "count": len(segments)})
    return jsonify({"ready": True, "segments": len(segments)})


@app.route("/api/stream/info")
def stream_info():
    info = probe_stream_info()
    return jsonify({
        "fps":        info.get("fps"),
        "resolution": info.get("resolution"),
    })


@app.route("/api/stream/hls/<path:filename>")
def hls_files(filename):
    return send_from_directory(HLS_DIR, filename)


@app.route("/api/wol", methods=["POST"])
def wake_on_lan():
    try:
        result = subprocess.run(
            ["wakeonlan", "-i", "10.0.0.255", "D8:5E:D3:FF:F8:2E"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return jsonify({"status": "sent", "message": "Magic packet sent to gaming PC"})
        else:
            return jsonify({"status": "error", "message": result.stderr.strip()}), 500
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "wakeonlan not installed on server"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/snapshot")
def get_snapshot():
    cmd = [
        "ffmpeg",
        "-rtsp_transport", "tcp",
        "-buffer_size", "1024000",
        "-max_delay", "500000",
        "-i", RTSP_URL,
        "-vf", "scale=640:480",
        "-q:v", "8",
        "-frames:v", "1",
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
        "-",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0 and result.stdout:
            return Response(result.stdout, mimetype="image/jpeg")
        else:
            return "Error capturing frame", 500
    except subprocess.TimeoutExpired:
        return "Timeout capturing frame", 500


@app.route("/api/debug")
def debug_recordings():
    debug_info = {}
    try:
        debug_info["recordings_dir_exists"] = os.path.exists(RECORDINGS_DIR)
        debug_info["recordings_dir_path"]   = RECORDINGS_DIR
        if os.path.exists(RECORDINGS_DIR):
            debug_info["recordings_dir_readable"] = os.access(RECORDINGS_DIR, os.R_OK)
            try:
                files = [f for f in os.listdir(RECORDINGS_DIR) if f.endswith(".mp4")]
                debug_info["recording_files"] = files
                debug_info["num_recordings"]  = len(files)
                metadata_file = os.path.join(RECORDINGS_DIR, "recordings.json")
                debug_info["metadata_exists"] = os.path.exists(metadata_file)
                if os.path.exists(metadata_file):
                    try:
                        with open(metadata_file, "r") as f:
                            metadata = json.load(f)
                        debug_info["metadata_valid"] = True
                        debug_info["metadata_keys"]  = list(metadata.keys())
                    except Exception as e:
                        debug_info["metadata_valid"] = False
                        debug_info["metadata_error"] = str(e)
            except Exception as e:
                debug_info["listdir_error"] = str(e)
        return jsonify(debug_info)
    except Exception as e:
        return jsonify({"error": str(e), "error_type": type(e).__name__}), 500


def get_video_duration(file_path):
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            duration_seconds = float(result.stdout.strip())
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            return f"{minutes}m {seconds:02d}s"
        else:
            return "Unknown"
    except Exception:
        return "Unknown"


@app.route("/api/recordings")
def get_recordings():
    all_recordings = []
    try:
        if not os.path.exists(RECORDINGS_DIR):
            return jsonify([])
        try:
            for f in os.listdir(RECORDINGS_DIR):
                if f.endswith(".mp4") and f.startswith("recording_"):
                    file_path = os.path.join(RECORDINGS_DIR, f)
                    if os.path.exists(file_path):
                        duration = get_video_duration(file_path)
                        recording_num = 0
                        try:
                            recording_num = int(f.replace("recording_", "").replace(".mp4", ""))
                        except ValueError:
                            recording_num = 0
                        all_recordings.append({
                            "filename":     f,
                            "duration":     duration,
                            "recording_num": recording_num,
                        })
        except Exception:
            return jsonify([])

        all_recordings.sort(key=lambda x: x["recording_num"], reverse=True)
        recordings_list = []
        for i, rec in enumerate(all_recordings):
            recordings_list.append({
                "filename":     rec["filename"],
                "display_name": f"Recording #{i+1} - {rec['duration']}",
            })
        return jsonify(recordings_list)
    except Exception as e:
        print(f"ERROR in get_recordings: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "error_type": type(e).__name__}), 500


@app.route("/api/download/<filename>")
def download_recording(filename):
    file_path = os.path.join(RECORDINGS_DIR, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "File not found", 404


@app.route("/api/play/<filename>")
def play_recording(filename):
    file_path = os.path.join(RECORDINGS_DIR, filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    return "File not found", 404


@app.route("/api/status")
def get_status():
    import psutil

    # Disk
    try:
        usage = psutil.disk_usage(RECORDINGS_DIR)
        disk_usage = {
            "total":   usage.total,
            "used":    usage.used,
            "free":    usage.free,
            "percent": (usage.used / usage.total) * 100,
        }
    except Exception:
        disk_usage = {"total": 0, "used": 0, "free": 0, "percent": 0}

    # Recording service
    recording_status = "unknown"
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "ipcamera-recorder"],
            capture_output=True, text=True,
        )
        recording_status = result.stdout.strip()
    except Exception:
        pass

    # Network — collect all non-loopback IPv4 addresses with their interface names
    network_interfaces = []
    try:
        for iface, addrs in psutil.net_if_addrs().items():
            if iface == "lo":
                continue
            for addr in addrs:
                if addr.family == 2:  # AF_INET = IPv4
                    network_interfaces.append({"interface": iface, "ip": addr.address})
    except Exception:
        pass

    # CPU & temperature
    cpu_percent = None
    cpu_temp    = None
    try:
        cpu_percent = psutil.cpu_percent(interval=0.5)
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["vcgencmd", "measure_temp"],
            capture_output=True, text=True, timeout=3
        )
        # Output: "temp=42.8'C"
        if result.returncode == 0:
            cpu_temp = result.stdout.strip().replace("temp=", "").replace("'C", "°C")
    except Exception:
        pass

    return jsonify({
        "disk_usage":          disk_usage,
        "recording_status":    recording_status,
        "network_interfaces":  network_interfaces,
        "cpu_percent":         cpu_percent,
        "cpu_temp":            cpu_temp,
        "timestamp":           datetime.now().isoformat(),
    })


@app.route("/api/logs")
def get_logs():
    log_file = os.path.join(LOGS_DIR, "recorder.log")
    logs = []
    if os.path.exists(log_file):
        try:
            with open(log_file, "r") as f:
                lines = f.readlines()
                logs = [line.strip() for line in lines[-50:]]
        except Exception:
            pass
    return jsonify(logs)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

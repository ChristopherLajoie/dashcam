import json
import os
import subprocess
import threading
import time
from datetime import datetime
from flask import Flask, render_template, Response, send_file, jsonify, request
from flask_cors import CORS

app = Flask(__name__, template_folder="/opt/ipcamera/web")
CORS(app)


RTSP_URL = "rtsp://192.168.1.18:554/1/h264major"
RECORDINGS_DIR = "/opt/ipcamera/recordings"
LOGS_DIR = "/opt/ipcamera/logs"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/recordings")
def recordings():
    return render_template("recordings.html")


@app.route("/api/snapshot")
def get_snapshot():
    cmd = [
        "ffmpeg",
        "-rtsp_transport",
        "tcp",
        "-buffer_size",
        "1024000",
        "-max_delay",
        "500000",
        "-i",
        RTSP_URL,
        "-vf",
        "scale=640:480",
        "-q:v",
        "8",
        "-frames:v",
        "1",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
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


def generate_stream():
    cmd = [
        "ffmpeg",
        "-rtsp_transport", "tcp",
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-i", RTSP_URL,
        "-vf", "scale=1280:720",
        "-q:v", "5",
        "-r", "15",
        "-f", "mjpeg",
        "-",
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
    buf = b""
    try:
        while True:
            chunk = process.stdout.read(4096)
            if not chunk:
                break
            buf += chunk
            while True:
                start = buf.find(b"\xff\xd8")
                end = buf.find(b"\xff\xd9", start + 2)
                if start == -1 or end == -1:
                    break
                frame = buf[start:end + 2]
                buf = buf[end + 2:]
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )
    finally:
        process.kill()


@app.route("/api/stream")
def video_stream():
    return Response(
        generate_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/api/debug")
def debug_recordings():
    debug_info = {}

    try:
        debug_info["recordings_dir_exists"] = os.path.exists(RECORDINGS_DIR)
        debug_info["recordings_dir_path"] = RECORDINGS_DIR

        if os.path.exists(RECORDINGS_DIR):
            debug_info["recordings_dir_readable"] = os.access(RECORDINGS_DIR, os.R_OK)
            try:
                files = [f for f in os.listdir(RECORDINGS_DIR) if f.endswith(".mp4")]
                debug_info["recording_files"] = files
                debug_info["num_recordings"] = len(files)

                metadata_file = os.path.join(RECORDINGS_DIR, "recordings.json")
                debug_info["metadata_exists"] = os.path.exists(metadata_file)

                if os.path.exists(metadata_file):
                    try:
                        with open(metadata_file, "r") as f:
                            metadata = json.load(f)
                        debug_info["metadata_valid"] = True
                        debug_info["metadata_keys"] = list(metadata.keys())
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
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
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
    except:
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
                            recording_num = int(
                                f.replace("recording_", "").replace(".mp4", "")
                            )
                        except ValueError:
                            recording_num = 0

                        all_recordings.append(
                            {
                                "filename": f,
                                "duration": duration,
                                "recording_num": recording_num,
                            }
                        )
        except Exception:
            return jsonify([])

        all_recordings.sort(key=lambda x: x["recording_num"], reverse=True)

        recordings_list = []
        for i, rec in enumerate(all_recordings):
            recordings_list.append(
                {
                    "filename": rec["filename"],
                    "display_name": f"Recording #{i+1} - {rec['duration']}",
                }
            )

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

    try:
        usage = psutil.disk_usage(RECORDINGS_DIR)
        disk_usage = {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": (usage.used / usage.total) * 100,
        }
    except Exception:
        disk_usage = {"total": 0, "used": 0, "free": 0, "percent": 0}

    recording_status = "unknown"
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "ipcamera-recorder"],
            capture_output=True,
            text=True,
        )
        recording_status = result.stdout.strip()
    except:
        pass

    network_info = {}
    try:
        result = subprocess.run(
            ["ip", "addr", "show", "uap0"], capture_output=True, text=True
        )
        if "10.42.0.1" in result.stdout:
            network_info["hotspot"] = "active"
            network_info["ip"] = "10.42.0.1"
        else:
            network_info["hotspot"] = "inactive"
    except:
        network_info["hotspot"] = "unknown"

    return jsonify(
        {
            "disk_usage": disk_usage,
            "recording_status": recording_status,
            "network": network_info,
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/api/logs")
def get_logs():
    log_file = os.path.join(LOGS_DIR, "recorder.log")
    logs = []

    if os.path.exists(log_file):
        try:
            with open(log_file, "r") as f:
                lines = f.readlines()

                logs = [line.strip() for line in lines[-50:]]
        except:
            pass

    return jsonify(logs)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

#!/usr/bin/env python3
"""
Cat detector — samples frames from the RTSP stream every N seconds,
runs YOLOv8n inference, and sends a push notification via ntfy.sh
when a cat is detected above the confidence threshold.

Setup:
    pip install ultralytics opencv-python-headless requests

Run manually:
    python3 /opt/ipcamera/scripts/cat_detector.py

Run as a service: see /etc/systemd/system/ipcamera-catdetector.service
"""

import io
import logging
import os
import time

import cv2
import requests
from ultralytics import YOLO

# ── Config ────────────────────────────────────────────────────────────────────
RTSP_URL        = "rtsp://192.168.1.18:554/1/h264major"
SAMPLE_INTERVAL = 8          # seconds between frame checks
CONFIDENCE      = 0.45       # minimum detection confidence (0–1)
NTFY_TOPIC      = "ipcamera-cats"   # change to your ntfy.sh topic
NTFY_URL        = f"https://ntfy.sh/{NTFY_TOPIC}"
COOLDOWN        = 120        # seconds between repeated notifications
SNAPSHOT_PATH   = "/tmp/cat_snapshot.jpg"
LOG_FILE        = "/opt/ipcamera/logs/cat_detector.log"

# COCO class ID for cat
CAT_CLASS_ID = 15
# ──────────────────────────────────────────────────────────────────────────────

os.makedirs("/opt/ipcamera/logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [cat_detector] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)


def grab_frame(rtsp_url: str):
    """Open the RTSP stream, grab one frame, release immediately."""
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise RuntimeError("Failed to grab frame from RTSP stream")
    return frame


def send_notification(confidence: float, snapshot_path: str):
    """POST a push notification to ntfy.sh with the snapshot attached."""
    try:
        with open(snapshot_path, "rb") as f:
            img_bytes = f.read()

        # Send image as attachment
        requests.post(
            NTFY_URL,
            data=img_bytes,
            headers={
                "Title":    "Cat detected!",
                "Message":  f"Confidence: {confidence:.0%}",
                "Priority": "default",
                "Tags":     "cat,camera",
                "Filename": "snapshot.jpg",
            },
            timeout=10,
        )
        log.info(f"Notification sent (confidence={confidence:.0%})")
    except Exception as e:
        log.error(f"Failed to send notification: {e}")


def main():
    log.info("Loading YOLOv8n model…")
    model = YOLO("yolov8n.pt")  # downloads automatically on first run
    log.info("Model loaded. Starting detection loop.")

    last_notified = 0.0

    while True:
        try:
            frame = grab_frame(RTSP_URL)

            results = model(frame, verbose=False)[0]

            cat_detections = [
                box for box in results.boxes
                if int(box.cls) == CAT_CLASS_ID and float(box.conf) >= CONFIDENCE
            ]

            if cat_detections:
                best_conf = max(float(b.conf) for b in cat_detections)
                log.info(f"Cat detected! Best confidence: {best_conf:.0%}")

                now = time.time()
                if now - last_notified >= COOLDOWN:
                    # Save annotated snapshot
                    annotated = results.plot()
                    cv2.imwrite(SNAPSHOT_PATH, annotated)
                    send_notification(best_conf, SNAPSHOT_PATH)
                    last_notified = now
                else:
                    remaining = int(COOLDOWN - (now - last_notified))
                    log.info(f"Cooldown active — {remaining}s remaining before next notification")
            else:
                log.debug("No cat detected.")

        except Exception as e:
            log.warning(f"Detection cycle error: {e}")

        time.sleep(SAMPLE_INTERVAL)


if __name__ == "__main__":
    main()

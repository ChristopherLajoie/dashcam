#!/usr/bin/env python3
"""
Motion detector — samples frames from the RTSP stream, uses MOG2 background
subtraction to detect motion, and sends a push notification via ntfy.sh when
movement exceeds the area threshold.

Setup:
    pip install opencv-python-headless requests

Run manually:
    python3 /opt/ipcamera/scripts/motion_detector.py

Run as a service: see /etc/systemd/system/ipcamera-motion.service
"""

import logging
import os
import signal
import time
from datetime import datetime

import cv2
import numpy as np
import requests

# ── Config ────────────────────────────────────────────────────────────────────
RTSP_URL           = "rtsp://192.168.1.18:554/1/h264major"
SAMPLE_INTERVAL    = 2            # seconds between frame grabs
MIN_CONTOUR_AREA   = 3000         # px² — raise to reduce sensitivity (wind, leaves)
NTFY_TOPIC         = "ipcamera-motion"
NTFY_URL           = f"https://ntfy.sh/{NTFY_TOPIC}"
COOLDOWN           = 90           # seconds between repeated notifications
SNAPSHOT_PATH      = "/tmp/motion_snapshot.jpg"
LOG_FILE           = "/opt/ipcamera/logs/motion_detector.log"
MOG2_HISTORY       = 500
MOG2_VAR_THRESH    = 25
IR_BRIGHTNESS_JUMP = 40           # mean luma delta that signals an IR mode switch
WARMUP_FRAMES      = 30
# ──────────────────────────────────────────────────────────────────────────────

os.makedirs("/opt/ipcamera/logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [motion_detector] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)


def grab_frame(rtsp_url: str):
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise RuntimeError("Failed to grab frame from RTSP stream")
    return frame


def send_notification(area: int, snapshot_path: str):
    try:
        with open(snapshot_path, "rb") as f:
            img_bytes = f.read()
        requests.post(
            NTFY_URL,
            data=img_bytes,
            headers={
                "Title":    "Motion detected!",
                "Message":  f"Region: {area} px²",
                "Priority": "default",
                "Tags":     "motion,camera",
                "Filename": "snapshot.jpg",
            },
            timeout=10,
        )
        log.info(f"Notification sent (area={area} px²)")
    except Exception as e:
        log.error(f"Failed to send notification: {e}")


def main():
    running = True

    def _stop(sig, frame):
        nonlocal running
        running = False
        log.info("Shutdown signal received")

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    fgbg = cv2.createBackgroundSubtractorMOG2(
        history=MOG2_HISTORY,
        varThreshold=MOG2_VAR_THRESH,
        detectShadows=True,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    log.info(f"Warming up background model ({WARMUP_FRAMES} frames)…")
    for i in range(WARMUP_FRAMES):
        if not running:
            return
        try:
            frame = grab_frame(RTSP_URL)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (21, 21), 0)
            fgbg.apply(blurred)
        except Exception as e:
            log.warning(f"Warmup frame {i} error: {e}")
        time.sleep(0.2)
    log.info("Warmup complete. Starting detection loop.")

    last_notified = 0.0
    prev_mean = None

    while running:
        try:
            frame = grab_frame(RTSP_URL)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            current_mean = float(np.mean(gray))

            # Detect IR mode transition — reset model to avoid false triggers
            if prev_mean is not None and abs(current_mean - prev_mean) > IR_BRIGHTNESS_JUMP:
                log.info(f"IR transition detected (Δluma={current_mean - prev_mean:.1f}), resetting background model")
                blurred = cv2.GaussianBlur(gray, (21, 21), 0)
                fgbg.apply(blurred, learningRate=1.0)
                prev_mean = current_mean
                time.sleep(SAMPLE_INTERVAL)
                continue

            prev_mean = current_mean

            blurred = cv2.GaussianBlur(gray, (21, 21), 0)
            fg_mask = fgbg.apply(blurred)

            # Shadow pixels are 127 in MOG2 — zero them out
            fg_mask[fg_mask == 127] = 0

            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
            fg_mask = cv2.dilate(fg_mask, None, iterations=2)

            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            motion_contours = [c for c in contours if cv2.contourArea(c) >= MIN_CONTOUR_AREA]

            if contours:
                max_area = max(int(cv2.contourArea(c)) for c in contours)
                log.debug(f"Max contour area: {max_area} px² (threshold: {MIN_CONTOUR_AREA})")

            if motion_contours:
                largest_area = max(int(cv2.contourArea(c)) for c in motion_contours)
                log.info(f"Motion detected! Largest region: {largest_area} px²")

                now = time.time()
                if now - last_notified >= COOLDOWN:
                    annotated = frame.copy()
                    for c in motion_contours:
                        x, y, w, h = cv2.boundingRect(c)
                        cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cv2.putText(annotated, f"MOTION DETECTED  {ts}", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    cv2.imwrite(SNAPSHOT_PATH, annotated)
                    send_notification(largest_area, SNAPSHOT_PATH)
                    last_notified = now
                else:
                    remaining = int(COOLDOWN - (now - last_notified))
                    log.info(f"Cooldown active — {remaining}s remaining before next notification")
            else:
                log.debug("No motion detected.")

        except Exception as e:
            log.warning(f"Detection cycle error: {e}")

        time.sleep(SAMPLE_INTERVAL)

    log.info("Motion detector stopped.")


if __name__ == "__main__":
    main()

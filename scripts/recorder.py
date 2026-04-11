import os
import time
import logging
import subprocess
import threading
import signal
import shutil
from datetime import datetime


class CameraRecorder:
    def __init__(self):
        self.base_dir = "/opt/ipcamera"
        self.recordings_dir = f"{self.base_dir}/recordings"
        self.logs_dir = f"{self.base_dir}/logs"
        self.rtsp_url = "rtsp://192.168.1.18:554/1/h264major"
        self.max_disk_usage = 80
        self.running = False
        self.current_process = None

        os.makedirs(self.logs_dir, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(f"{self.logs_dir}/recorder.log"),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)

        os.makedirs(self.recordings_dir, exist_ok=True)

        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, signum, frame):
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        if self.current_process:
            self.logger.info("Stopping current recording...")
            self.current_process.send_signal(signal.SIGINT)
            try:
                self.current_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.logger.warning("Recording didn't stop gracefully, forcing kill...")
                self.current_process.kill()

    def get_disk_usage(self):
        try:
            usage = shutil.disk_usage(self.recordings_dir)
            return (usage.used / usage.total) * 100
        except FileNotFoundError:
            self.logger.error(f"Recordings directory not found: {self.recordings_dir}")
            return 100

    def cleanup_old_files(self):
        current_usage = self.get_disk_usage()
        if current_usage > self.max_disk_usage:
            self.logger.info(
                f"Disk usage {current_usage:.2f}% is above threshold ({self.max_disk_usage}%). Cleaning up old files..."
            )

        while self.get_disk_usage() > self.max_disk_usage:
            oldest_file = None
            oldest_time = float("inf")

            try:
                files_in_dir = os.listdir(self.recordings_dir)
            except FileNotFoundError:
                self.logger.error(
                    f"Cannot list files, directory not found: {self.recordings_dir}"
                )
                break

            for item in files_in_dir:
                if item.endswith(".mp4"):
                    item_path = os.path.join(self.recordings_dir, item)
                    try:
                        if os.path.getsize(item_path) == 0:
                            self.logger.info(f"Removing zero-byte file: {item_path}")
                            os.remove(item_path)
                            continue

                        mtime = os.path.getmtime(item_path)
                        if mtime < oldest_time:
                            oldest_time = mtime
                            oldest_file = item_path
                    except FileNotFoundError:
                        continue

            if oldest_file:
                try:
                    self.logger.info(
                        f"Removing old recording: {oldest_file} to free up space."
                    )
                    os.remove(oldest_file)
                    time.sleep(1)
                except FileNotFoundError:
                    self.logger.warning(
                        f"Could not delete {oldest_file} as it was already removed."
                    )
                except Exception as e:
                    self.logger.error(f"Error removing file {oldest_file}: {e}")
                    break
            else:
                self.logger.info("No more files to remove.")
                break

    def record_continuous(self, output_file):
        cmd = [
            "ffmpeg",
            # No -y: never silently overwrite an existing file
            "-rtsp_transport",
            "tcp",
            "-buffer_size",
            "1024000",
            "-max_delay",
            "500000",
            "-i",
            self.rtsp_url,
            "-c:v",
            "copy",
            "-movflags",
            "frag_keyframe+empty_moov+default_base_moof",
            "-flush_packets",
            "1",
            "-f",
            "mp4",
            output_file,
        ]

        self.logger.info(f"Starting continuous recording: {' '.join(cmd)}")

        try:
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            _, stderr_output = self.current_process.communicate()
            rc = self.current_process.returncode

            # A graceful stop (SIGINT/SIGTERM) causes ffmpeg to exit with a
            # non-zero code.  That is expected — don't treat it as a failure.
            # Only flag as failure when we're still supposed to be running AND
            # ffmpeg quit on its own with an error.
            if self.running and rc != 0:
                self.logger.error(
                    f"FFmpeg exited unexpectedly with code {rc}"
                )
                self.logger.error(f"FFmpeg stderr: {stderr_output}")
                # Clean up empty/corrupt file
                if os.path.exists(output_file) and os.path.getsize(output_file) == 0:
                    os.remove(output_file)
                return False

            # Keep the file if it has content, regardless of exit code
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                self.logger.info(f"Recording saved: {output_file}")
                return True
            else:
                # Clean up empty file regardless of how we got here
                if os.path.exists(output_file):
                    try:
                        os.remove(output_file)
                    except OSError:
                        pass
                self.logger.warning(
                    f"Recording file is empty or missing: {output_file}"
                )
                return False

        except Exception as e:
            self.logger.error(f"Recording error: {e}")
            return False
        finally:
            self.current_process = None

    def get_output_filename(self):
        """Generate a unique timestamped filename — can never collide."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = os.path.join(self.recordings_dir, f"recording_{ts}.mp4")
        suffix = 0
        while os.path.exists(path):
            suffix += 1
            path = os.path.join(self.recordings_dir, f"recording_{ts}_{suffix}.mp4")
        return path

    def _monitor_disk_usage(self):
        self.logger.info("Starting background disk monitor.")
        while self.running:
            self.cleanup_old_files()
            time.sleep(60)
        self.logger.info("Stopping background disk monitor.")

    def run(self):
        self.logger.info("Camera recorder starting...")
        self.running = True

        disk_monitor_thread = threading.Thread(target=self._monitor_disk_usage)
        disk_monitor_thread.daemon = True
        disk_monitor_thread.start()

        while self.running:
            output_file = self.get_output_filename()
            self.logger.info(f"Starting recording session: {output_file}")

            success = self.record_continuous(output_file)

            if not success and self.running:
                self.logger.warning(
                    "Recording failed. Retrying in 30 seconds..."
                )
                time.sleep(30)
            else:
                # Either stopped gracefully or succeeded — exit the loop
                break

        self.logger.info("Camera recorder session ended")


if __name__ == "__main__":
    recorder = CameraRecorder()
    recorder.run()

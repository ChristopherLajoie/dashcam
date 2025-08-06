import os
import time
import logging
import subprocess
import threading
import signal
import shutil

class CameraRecorder:
    def __init__(self):
        self.base_dir = "/opt/ipcamera"
        self.recordings_dir = f"{self.base_dir}/recordings"
        self.logs_dir = f"{self.base_dir}/logs"
        self.rtsp_url = "rtsp://192.168.1.18:554/1/h264major"
        self.max_disk_usage = 80  # Max disk usage percentage
        self.running = False
        self.current_process = None
        
        # Setup logging
        os.makedirs(self.logs_dir, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'{self.logs_dir}/recorder.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Create recordings directory
        os.makedirs(self.recordings_dir, exist_ok=True)
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        # Gracefully stop current recording
        if self.current_process:
            self.logger.info("Stopping current recording...")
            # Send SIGINT (Ctrl+C) to ffmpeg for a graceful shutdown
            self.current_process.send_signal(signal.SIGINT)
            try:
                # Wait a moment for graceful shutdown
                self.current_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.logger.warning("Recording didn't stop gracefully, forcing kill...")
                self.current_process.kill()
    
    def get_disk_usage(self):
        """Get current disk usage percentage"""
        try:
            usage = shutil.disk_usage(self.recordings_dir)
            return (usage.used / usage.total) * 100
        except FileNotFoundError:
            self.logger.error(f"Recordings directory not found: {self.recordings_dir}")
            return 100 # Return 100% to prevent attempts to write

    def cleanup_old_files(self):
        """Remove old recordings if disk usage is too high"""
        # Check disk usage before starting the loop
        current_usage = self.get_disk_usage()
        if current_usage > self.max_disk_usage:
            self.logger.info(f"Disk usage {current_usage:.2f}% is above threshold ({self.max_disk_usage}%). Cleaning up old files...")
        
        while self.get_disk_usage() > self.max_disk_usage:
            oldest_file = None
            oldest_time = float('inf')
            
            # Find the oldest MP4 file
            try:
                files_in_dir = os.listdir(self.recordings_dir)
            except FileNotFoundError:
                self.logger.error(f"Cannot list files, directory not found: {self.recordings_dir}")
                break # Exit the loop if the directory disappears

            for item in files_in_dir:
                if item.endswith('.mp4'):
                    item_path = os.path.join(self.recordings_dir, item)
                    # Check for and remove zero-byte files immediately
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
                        # The file might have been deleted by another process, just skip it
                        continue
            
            if oldest_file:
                try:
                    self.logger.info(f"Removing old recording: {oldest_file} to free up space.")
                    os.remove(oldest_file)
                    # Give the OS a moment to update disk usage stats
                    time.sleep(1)
                except FileNotFoundError:
                    self.logger.warning(f"Could not delete {oldest_file} as it was already removed.")
                except Exception as e:
                    self.logger.error(f"Error removing file {oldest_file}: {e}")
                    break # Stop if we can't delete files
            else:
                self.logger.info("No more files to remove.")
                break # No files left to delete

    def record_continuous(self, output_file):
        """Record continuously until stopped - resilient to power loss"""
        cmd = [
            'ffmpeg',
            '-y',
            '-rtsp_transport', 'tcp',
            '-buffer_size', '1024000',
            '-max_delay', '500000',
            '-i', self.rtsp_url,
            '-c:v', 'copy', # Use stream copy to reduce CPU load
            '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
            '-flush_packets', '1',
            '-f', 'mp4',
            output_file
        ]
        
        self.logger.info(f"Starting continuous recording: {' '.join(cmd)}")
        
        try:
            # Using PIPE for stderr to log it if needed, but not blocking on read
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL, # We don't need stdout
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # This will block until the process terminates
            _, stderr_output = self.current_process.communicate()
            
            # After process ends, check return code
            if self.running and self.current_process.returncode != 0:
                self.logger.error(f"FFmpeg process exited unexpectedly with code {self.current_process.returncode}")
                self.logger.error(f"FFmpeg stderr: {stderr_output}")
                return False
            
            # Recording completed
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                self.logger.info(f"Recording completed: {output_file}")
                return True
            else:
                self.logger.warning(f"Recording file is empty or missing after process ended: {output_file}")
                return False
            
        except Exception as e:
            self.logger.error(f"Recording error: {e}")
            return False
        finally:
            self.current_process = None

    def get_next_recording_number(self):
        """Get the next recording number"""
        existing_files = []
        try:
            for f in os.listdir(self.recordings_dir):
                if f.endswith('.mp4') and f.startswith('recording_'):
                    try:
                        num = int(f.replace('recording_', '').replace('.mp4', ''))
                        existing_files.append(num)
                    except ValueError:
                        continue
        except FileNotFoundError:
            pass # Directory might not exist on first run
        
        return max(existing_files) + 1 if existing_files else 1

    def _monitor_disk_usage(self):
        """Periodically checks disk usage and cleans up if needed."""
        self.logger.info("Starting background disk monitor.")
        while self.running:
            self.cleanup_old_files()
            # Check every 60 seconds. Adjust as needed.
            time.sleep(60)
        self.logger.info("Stopping background disk monitor.")

    def run(self):
        """Main recording loop - one continuous recording per session"""
        self.logger.info("Camera recorder starting...")
        self.running = True
        
        # --- Start the background disk monitoring thread ---
        disk_monitor_thread = threading.Thread(target=self._monitor_disk_usage)
        disk_monitor_thread.daemon = True  # Allows main program to exit even if thread is running
        disk_monitor_thread.start()
        
        while self.running:
            # Generate a new filename for each attempt/restart
            recording_num = self.get_next_recording_number()
            output_file = os.path.join(self.recordings_dir, f"recording_{recording_num}.mp4")
            
            self.logger.info(f"Starting recording session for: {output_file}")
            
            # Start recording - this will block until it stops or fails
            success = self.record_continuous(output_file)
            
            # If the process failed and we are supposed to be running, wait and retry
            if not success and self.running:
                self.logger.warning("Recording process failed. Retrying in 30 seconds...")
                time.sleep(30)
            # If it was successful but we should keep running (e.g. for segmented recording in future)
            # or if self.running became false, we break the loop.
            else:
                break
        
        self.logger.info("Camera recorder session ended")


if __name__ == "__main__":
    recorder = CameraRecorder()
    recorder.run()
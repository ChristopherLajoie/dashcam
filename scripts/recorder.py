import os
import sys
import time
import json
import logging
import subprocess
import threading
import signal
from datetime import datetime, timedelta
import shutil
import psutil

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
            self.current_process.terminate()
            try:
                # Wait a moment for graceful shutdown
                self.current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.logger.warning("Recording didn't stop gracefully, forcing...")
                self.current_process.kill()
    
    def get_disk_usage(self):
        """Get current disk usage percentage"""
        usage = shutil.disk_usage(self.recordings_dir)
        return (usage.used / usage.total) * 100
    
    def cleanup_old_files(self):
        """Remove old recordings if disk usage is too high"""
        while self.get_disk_usage() > self.max_disk_usage:
            oldest_file = None
            oldest_time = float('inf')
            
            for item in os.listdir(self.recordings_dir):
                if item.endswith('.mp4'):
                    item_path = os.path.join(self.recordings_dir, item)
                    # Check for and remove zero-byte files
                    if os.path.getsize(item_path) == 0:
                        self.logger.info(f"Removing zero-byte file: {item_path}")
                        os.remove(item_path)
                        continue
                    
                    mtime = os.path.getmtime(item_path)
                    if mtime < oldest_time:
                        oldest_time = mtime
                        oldest_file = item_path
            
            if oldest_file:
                self.logger.info(f"Removing old recording: {oldest_file}")
                os.remove(oldest_file)
            else:
                break
    

    def record_continuous(self, output_file):
        """Record continuously until stopped - resilient to power loss"""
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file
            '-rtsp_transport', 'tcp',  # Use TCP for reliability
            '-buffer_size', '1024000',  # Larger input buffer
            '-max_delay', '500000',     # Allow buffering delay
            '-fflags', 'nobuffer',        # No buffering
            '-flags', 'low_delay',        # Low delay mode
            '-i', self.rtsp_url,
            '-c:v', 'libx264',  # Re-encode to ensure framerate control
            '-preset', 'ultrafast',  # Fast encoding
            '-crf', '23',  # Good quality
            '-force_fps',  # Force frame rate conversion
            '-c:a', 'copy',  # Copy audio without re-encoding
            # Fragmented MP4 for power-loss resilience
            '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
            '-flush_packets', '1',  # Flush data to disk frequently
            '-f', 'mp4',
            output_file
        ]
        
        self.logger.info(f"Starting continuous recording: {output_file}")
        
        try:
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Monitor process until stopped
            while self.current_process.poll() is None and self.running:
                time.sleep(1)
            
            # Check if we stopped gracefully or due to error
            if self.running and self.current_process.returncode != 0:
                error = self.current_process.stderr.read()
                self.logger.error(f"FFmpeg error: {error}")
                return False
            
            # Recording completed (either gracefully stopped or process ended)
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                filename = os.path.basename(output_file)
                self.create_metadata(filename)
                self.logger.info(f"Recording completed: {output_file}")
                return True
            else:
                self.logger.warning(f"Recording file is empty or missing: {output_file}")
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
                    # Extract number from recording_N.mp4
                    try:
                        num = int(f.replace('recording_', '').replace('.mp4', ''))
                        existing_files.append(num)
                    except ValueError:
                        continue
        except:
            pass
        
        # Return next number (start from 1)
        return max(existing_files) + 1 if existing_files else 1

    def create_metadata(self, filename):
        """Add filename to simple metadata list"""
        metadata_file = os.path.join(self.recordings_dir, "recordings.json")
        
        # Load existing metadata
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        except:
            metadata = {"recordings": []}
        
        # Add recording if not already present
        if filename not in metadata["recordings"]:
            metadata["recordings"].append(filename)
        
        # Save metadata
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

    def run(self):
        """Main recording loop - one continuous recording per session"""
        self.logger.info("Camera recorder starting...")
        self.running = True
        
        # Generate output filename - NO DATE FOLDERS, just flat structure
        recording_num = self.get_next_recording_number()
        output_file = os.path.join(self.recordings_dir, f"recording_{recording_num}.mp4")
        
        self.logger.info(f"Starting recording session: {output_file}")
        
        # Start continuous recording
        while self.running:
            # Cleanup old files before starting (free up space)
            self.cleanup_old_files()
            
            # Start recording - this will run until Pi shuts down or error occurs
            success = self.record_continuous(output_file)
            
            if not success and self.running:
                self.logger.warning("Recording failed, retrying in 30 seconds...")
                time.sleep(30)
            else:
                # Recording stopped (either gracefully or due to shutdown)
                break
        
        self.logger.info("Camera recorder session ended")

if __name__ == "__main__":
    recorder = CameraRecorder()
    recorder.run()
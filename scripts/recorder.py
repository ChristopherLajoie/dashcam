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
        self.segment_duration = 600  # 10 minutes
        self.max_disk_usage = 80  # Max disk usage percentage
        self.running = False
        
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
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def get_disk_usage(self):
        """Get current disk usage percentage"""
        usage = shutil.disk_usage(self.recordings_dir)
        return (usage.used / usage.total) * 100
    
    def cleanup_old_files(self):
        """Remove old recordings if disk usage is too high"""
        while self.get_disk_usage() > self.max_disk_usage:
            oldest_dir = None
            oldest_time = float('inf')
            
            for item in os.listdir(self.recordings_dir):
                item_path = os.path.join(self.recordings_dir, item)
                if os.path.isdir(item_path):
                    mtime = os.path.getmtime(item_path)
                    if mtime < oldest_time:
                        oldest_time = mtime
                        oldest_dir = item_path
            
            if oldest_dir:
                self.logger.info(f"Removing old recordings: {oldest_dir}")
                shutil.rmtree(oldest_dir)
            else:
                break
    
    def create_daily_metadata(self, date_str):
        """Create metadata file for the day"""
        metadata = {
            "date": date_str,
            "recordings": [],
            "created": datetime.now().isoformat()
        }
        
        date_dir = os.path.join(self.recordings_dir, date_str)
        metadata_file = os.path.join(date_dir, "metadata.json")
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return metadata_file
    
    def update_metadata(self, date_str, filename, start_time, end_time=None):
        """Update metadata file with recording info"""
        date_dir = os.path.join(self.recordings_dir, date_str)
        metadata_file = os.path.join(date_dir, "metadata.json")
        
        # Load existing metadata
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        except:
            metadata = {
                "date": date_str,
                "recordings": [],
                "created": datetime.now().isoformat()
            }
        
        # Add or update recording entry
        recording_entry = {
            "filename": filename,
            "start_time": start_time,
            "end_time": end_time,
            "duration": None
        }
        
        if end_time:
            start_dt = datetime.fromisoformat(start_time)
            end_dt = datetime.fromisoformat(end_time)
            recording_entry["duration"] = str(end_dt - start_dt)
        
        # Update or add entry
        found = False
        for i, rec in enumerate(metadata["recordings"]):
            if rec["filename"] == filename:
                metadata["recordings"][i] = recording_entry
                found = True
                break
        
        if not found:
            metadata["recordings"].append(recording_entry)
        
        metadata["updated"] = datetime.now().isoformat()
        
        # Save metadata
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def record_segment(self, output_file, start_time):
        """Record a single segment using FFmpeg"""
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file
            '-rtsp_transport', 'tcp',  # Use TCP for reliability
            '-buffer_size', '1024000',  # Larger input buffer
            '-max_delay', '500000',     # Allow buffering delay
            '-i', self.rtsp_url,
            '-c:v', 'copy',  # Copy video without re-encoding
            '-c:a', 'copy',  # Copy audio without re-encoding
            '-t', str(self.segment_duration),  # Duration
            '-f', 'mp4',
            output_file
        ]
        
        self.logger.info(f"Starting recording: {output_file}")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Monitor process
            while process.poll() is None and self.running:
                time.sleep(1)
            
            if not self.running:
                process.terminate()
                process.wait()
                return False
            
            if process.returncode == 0:
                end_time = datetime.now().isoformat()
                date_str = datetime.fromisoformat(start_time).strftime('%Y-%m-%d')
                filename = os.path.basename(output_file)
                self.update_metadata(date_str, filename, start_time, end_time)
                self.logger.info(f"Recording completed: {output_file}")
                return True
            else:
                error = process.stderr.read()
                self.logger.error(f"FFmpeg error: {error}")
                return False
            
        except Exception as e:
            self.logger.error(f"Recording error: {e}")
            return False
    
    def run(self):
        """Main recording loop"""
        self.logger.info("Camera recorder starting...")
        self.running = True
        
        while self.running:
            now = datetime.now()
            date_str = now.strftime('%Y-%m-%d')
            time_str = now.strftime('%H-%M-%S')
            
            # Create daily directory
            date_dir = os.path.join(self.recordings_dir, date_str)
            os.makedirs(date_dir, exist_ok=True)
            
            # Create metadata file if it doesn't exist
            metadata_file = os.path.join(date_dir, "metadata.json")
            if not os.path.exists(metadata_file):
                self.create_daily_metadata(date_str)
            
            # Generate output filename
            output_file = os.path.join(date_dir, f"{time_str}.mp4")
            start_time = now.isoformat()
            
            # Add entry to metadata (without end time initially)
            filename = os.path.basename(output_file)
            self.update_metadata(date_str, filename, start_time)
            
            # Record segment
            success = self.record_segment(output_file, start_time)
            
            if not success and self.running:
                self.logger.warning("Recording failed, retrying in 30 seconds...")
                time.sleep(30)
            
            # Cleanup old files
            self.cleanup_old_files()
        
        self.logger.info("Camera recorder stopped")

if __name__ == "__main__":
    recorder = CameraRecorder()
    recorder.run()
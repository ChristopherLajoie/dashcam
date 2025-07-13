#!/usr/bin/env python3

import sys
import time
from parameter import ParameterHandler, FramerateValues

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 change_parameter.py <resolution> <framerate>")
        print("\nValid resolutions: 480p, w480p, 576p, 720p, 960p, 1080p, 1536p")
        print("Valid framerates: 3, 5, 10, 15, 20, 25, 30")
        print("\nExample: python3 change_parameter.py 1080p 25")
        return 1
    
    target_resolution = sys.argv[1]
    target_framerate = sys.argv[2]
    
    # Validate resolution
    valid_resolutions = ["480p", "w480p", "576p", "720p", "960p", "1080p", "1536p"]
    if target_resolution not in valid_resolutions:
        print(f"❌ Invalid resolution: {target_resolution}")
        print(f"Valid options: {', '.join(valid_resolutions)}")
        return 1
    
    # Validate and convert framerate
    framerate_map = {
        "3": FramerateValues._3,
        "5": FramerateValues._5,
        "10": FramerateValues._10,
        "15": FramerateValues._15,
        "20": FramerateValues._20,
        "25": FramerateValues._25,
        "30": FramerateValues._30
    }
    
    if target_framerate not in framerate_map:
        print(f"❌ Invalid framerate: {target_framerate}")
        print("Valid framerates: 3, 5, 10, 15, 20, 25, 30")
        return 1
    
    framerate_enum = framerate_map[target_framerate]
    
    # Camera configuration
    camera_ip = "192.168.1.18"
    camera_port = 8999
    username = "admin"
    password = "admin"
    
    print("🎥 Camera Parameter Controller")
    print("=" * 40)
    print(f"Connecting to camera at {camera_ip}:{camera_port}")
    
    try:
        # Initialize camera handler
        camera = ParameterHandler(camera_ip, camera_port, username, password)
        
        # Enable verbose logging to see what's happening
        camera.verbose_logging = True
        
        print("Camera connected successfully!")
        
        # Change the resolution
        print(f"Setting resolution to {target_resolution}...")
        if camera.setResolution(target_resolution):
            print(f"✅ Resolution successfully changed to {target_resolution}")
        else:
            print(f"❌ Failed to change resolution to {target_resolution}")
            return 1
        
        # Change the frame rate
        print(f"Setting frame rate to {target_framerate} FPS...")
        if camera.setFrameRate(framerate_enum):
            print(f"✅ Frame rate successfully changed to {target_framerate} FPS")
        else:
            print(f"❌ Failed to change frame rate to {target_framerate} FPS")
            return 1
        
        # Wait a moment for settings to apply
        print("Waiting for settings to apply...")
        time.sleep(3)
        
        print("✅ Camera configuration complete!")
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Please check:")
        print("- Camera IP address is correct")
        print("- Camera is powered on and accessible")
        print("- Username and password are correct")
        print("- Network connectivity")
        return 1

if __name__ == "__main__":
    sys.exit(main())
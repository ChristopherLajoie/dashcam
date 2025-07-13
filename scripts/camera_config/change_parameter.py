#!/usr/bin/env python3

import sys
import time
from scripts.api import ParameterHandler, FramerateValues

class InteractiveCameraController:
    def __init__(self):
        # Camera configuration
        self.camera_ip = "192.168.1.18"
        self.camera_port = 8999
        self.username = "admin"
        self.password = "admin"
        
        # Define available parameters and their configurations
        self.parameters = {
            "resolution": {
                "display_name": "Resolution",
                "method": "setResolution",
                "values": ["480p", "w480p", "576p", "720p", "960p", "1080p", "1536p"],
                "value_type": "predefined"
            },
            "framerate": {
                "display_name": "Frame Rate (FPS)",
                "method": "setFrameRate", 
                "values": {
                    "3": FramerateValues._3,
                    "5": FramerateValues._5,
                    "10": FramerateValues._10,
                    "15": FramerateValues._15,
                    "20": FramerateValues._20,
                    "25": FramerateValues._25,
                    "30": FramerateValues._30
                },
                "value_type": "enum_map"
            },
            "brightness": {
                "display_name": "Brightness",
                "method": "setBrightness",
                "values": "0-100",
                "value_type": "range"
            },
            "contrast": {
                "display_name": "Contrast", 
                "method": "setContrast",
                "values": "0-100",
                "value_type": "range"
            },
            "saturation": {
                "display_name": "Saturation",
                "method": "setSaturation", 
                "values": "0-100",
                "value_type": "range"
            },
            "zoom": {
                "display_name": "Zoom Level",
                "method": "setZoom",
                "values": "1-10",
                "value_type": "range"
            },
            "focus": {
                "display_name": "Focus",
                "method": "setFocus",
                "values": "auto/manual",
                "value_type": "free_input"
            },
            "exposure": {
                "display_name": "Exposure",
                "method": "setExposure",
                "values": "auto/manual",
                "value_type": "free_input"
            },
            "white_balance": {
                "display_name": "White Balance",
                "method": "setWhiteBalance",
                "values": "auto/indoor/outdoor/fluorescent",
                "value_type": "free_input"
            },
            "night_mode": {
                "display_name": "Night Mode",
                "method": "setNightMode",
                "values": ["on", "off", "auto"],
                "value_type": "predefined"
            }
        }
        
        self.camera = None
    
    def connect_camera(self):
        """Connect to the camera"""
        print("🎥 Camera Parameter Controller")
        print("=" * 50)
        print(f"Connecting to camera at {self.camera_ip}:{self.camera_port}")
        
        try:
            self.camera = ParameterHandler(self.camera_ip, self.camera_port, 
                                         self.username, self.password)
            self.camera.verbose_logging = True
            print("✅ Camera connected successfully!")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            print("Please check:")
            print("- Camera IP address is correct")
            print("- Camera is powered on and accessible") 
            print("- Username and password are correct")
            print("- Network connectivity")
            return False
    
    def display_menu(self):
        """Display the parameter selection menu"""
        print("\n" + "=" * 50)
        print("📋 Available Parameters:")
        print("-" * 50)
        
        for i, (key, config) in enumerate(self.parameters.items(), 1):
            values_info = self.get_values_display(config)
            print(f"{i:2d}. {config['display_name']:<20} ({values_info})")
        
        print(f"{len(self.parameters) + 1:2d}. Exit")
        print("-" * 50)
    
    def get_values_display(self, config):
        """Get display string for parameter values"""
        if config["value_type"] == "predefined":
            return ", ".join(config["values"])
        elif config["value_type"] == "enum_map":
            return ", ".join(config["values"].keys())
        elif config["value_type"] == "range":
            return config["values"]
        else:
            return config["values"]
    
    def get_parameter_choice(self):
        """Get user's parameter selection"""
        while True:
            try:
                choice = input("\n🔧 Select parameter (number): ").strip()
                choice_num = int(choice)
                
                if choice_num == len(self.parameters) + 1:
                    return None  # Exit
                
                if 1 <= choice_num <= len(self.parameters):
                    param_keys = list(self.parameters.keys())
                    return param_keys[choice_num - 1]
                else:
                    print(f"❌ Invalid choice. Please enter 1-{len(self.parameters) + 1}")
            except ValueError:
                print("❌ Please enter a valid number")
    
    def get_value_choice(self, param_key):
        """Get user's value selection for the chosen parameter"""
        config = self.parameters[param_key]
        
        print(f"\n🎯 Setting {config['display_name']}")
        print("-" * 30)
        
        if config["value_type"] == "predefined":
            print("Available values:")
            for i, value in enumerate(config["values"], 1):
                print(f"  {i}. {value}")
            
            while True:
                try:
                    choice = input("Select value (number or type custom): ").strip()
                    
                    # Try as number first
                    try:
                        choice_num = int(choice)
                        if 1 <= choice_num <= len(config["values"]):
                            return config["values"][choice_num - 1]
                        else:
                            print(f"❌ Invalid choice. Please enter 1-{len(config['values'])}")
                            continue
                    except ValueError:
                        # If not a number, use as custom value
                        return choice
                        
                except KeyboardInterrupt:
                    return None
        
        elif config["value_type"] == "enum_map":
            print("Available values:")
            for i, key in enumerate(config["values"].keys(), 1):
                print(f"  {i}. {key}")
            
            while True:
                try:
                    choice = input("Select value (number): ").strip()
                    choice_num = int(choice)
                    keys = list(config["values"].keys())
                    
                    if 1 <= choice_num <= len(keys):
                        selected_key = keys[choice_num - 1]
                        return config["values"][selected_key]
                    else:
                        print(f"❌ Invalid choice. Please enter 1-{len(keys)}")
                except ValueError:
                    print("❌ Please enter a valid number")
                except KeyboardInterrupt:
                    return None
        
        else:  # range or free_input
            print(f"Valid values: {config['values']}")
            value = input("Enter value: ").strip()
            
            # For range values, try to convert to appropriate type
            if config["value_type"] == "range" and "-" in config["values"]:
                try:
                    # Try to convert to int if it looks like a numeric range
                    if value.isdigit():
                        return int(value)
                    elif value.replace(".", "").isdigit():
                        return float(value)
                except ValueError:
                    pass
            
            return value
    
    def apply_parameter_change(self, param_key, value):
        """Apply the parameter change"""
        config = self.parameters[param_key]
        method_name = config["method"]
        
        print(f"\n⚙️  Applying {config['display_name']} = {value}")
        
        try:
            # Get the method from the camera object
            method = getattr(self.camera, method_name)
            
            # Call the method with the value
            success = method(value)
            
            if success:
                print(f"✅ Successfully changed {config['display_name']} to {value}")
                print("⏳ Waiting for settings to apply...")
                time.sleep(2)
                return True
            else:
                print(f"❌ Failed to change {config['display_name']} to {value}")
                return False
                
        except AttributeError:
            print(f"❌ Method {method_name} not found. This parameter may not be supported.")
            return False
        except Exception as e:
            print(f"❌ Error applying change: {e}")
            return False
    
    def run_interactive_mode(self):
        """Run the interactive parameter controller"""
        if not self.connect_camera():
            return 1
        
        print("\n🚀 Interactive mode started!")
        print("You can now change any camera parameter.")
        
        while True:
            try:
                self.display_menu()
                param_key = self.get_parameter_choice()
                
                if param_key is None:  # User chose exit
                    print("\n👋 Goodbye!")
                    break
                
                value = self.get_value_choice(param_key)
                
                if value is None:  # User cancelled
                    continue
                
                self.apply_parameter_change(param_key, value)
                
                # Ask if user wants to continue
                continue_choice = input("\n🔄 Change another parameter? (y/n): ").strip().lower()
                if continue_choice not in ['y', 'yes', '']:
                    print("\n👋 Goodbye!")
                    break
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
        
        return 0
    
    def run_command_line_mode(self, param_name, value):
        """Run in command line mode with specific parameter and value"""
        if not self.connect_camera():
            return 1
        
        # Find parameter by name (case insensitive)
        param_key = None
        for key, config in self.parameters.items():
            if (key.lower() == param_name.lower() or 
                config['display_name'].lower() == param_name.lower()):
                param_key = key
                break
        
        if param_key is None:
            print(f"❌ Unknown parameter: {param_name}")
            print("Available parameters:")
            for key, config in self.parameters.items():
                print(f"  - {key} ({config['display_name']})")
            return 1
        
        # Convert value if needed
        config = self.parameters[param_key]
        if config["value_type"] == "enum_map":
            if value in config["values"]:
                value = config["values"][value]
            else:
                print(f"❌ Invalid value for {param_name}: {value}")
                print(f"Valid values: {list(config['values'].keys())}")
                return 1
        
        # Apply the change
        if self.apply_parameter_change(param_key, value):
            return 0
        else:
            return 1

def main():
    controller = InteractiveCameraController()
    
    if len(sys.argv) == 1:
        # Interactive mode
        return controller.run_interactive_mode()
    elif len(sys.argv) == 3:
        # Command line mode
        param_name = sys.argv[1]
        value = sys.argv[2]
        return controller.run_command_line_mode(param_name, value)
    else:
        print("Usage:")
        print("  Interactive mode: python3 change_parameter.py")
        print("  Command line:     python3 change_parameter.py <parameter> <value>")
        print("\nExamples:")
        print("  python3 change_parameter.py resolution 1080p")
        print("  python3 change_parameter.py framerate 25")
        print("  python3 change_parameter.py brightness 75")
        return 1

if __name__ == "__main__":
    sys.exit(main())
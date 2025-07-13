#!/usr/bin/env python3

import sys
import time
from scripts.api import (
    ParameterHandler, FramerateValues, Scenes, ExposureModes, 
    WhiteBalanceModes, IRModes, ShutterValues, AEGains
)

class InteractiveCameraController:
    def __init__(self):
        # Camera configuration
        self.camera_ip = "192.168.1.18"
        self.camera_port = 8999
        self.username = "admin"
        self.password = "admin"
        
        # Define all available parameters from parameter.py
        self.parameters = {
            # Basic image settings (0-255 range)
            "brightness": {
                "display_name": "Brightness",
                "method": "setBrightness",
                "values": "0-255",
                "value_type": "range"
            },
            "contrast": {
                "display_name": "Contrast",
                "method": "setContrast",
                "values": "0-255",
                "value_type": "range"
            },
            "saturation": {
                "display_name": "Saturation",
                "method": "setSaturation",
                "values": "0-255",
                "value_type": "range"
            },
            "sharpness": {
                "display_name": "Sharpness",
                "method": "setSharpness",
                "values": "0-255",
                "value_type": "range"
            },
            
            # Video settings
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
            "bitrate": {
                "display_name": "Bitrate (kbps)",
                "method": "setBitrate",
                "values": "128-10000",
                "value_type": "range"
            },
            
            # Advanced image enhancement
            "wdr_level": {
                "display_name": "Wide Dynamic Range Level",
                "method": "setWideDynamicRangeLevel",
                "values": "0-255",
                "value_type": "range"
            },
            "lens_distortion_correction": {
                "display_name": "Lens Distortion Correction Level",
                "method": "setLensDistortionCorrection", 
                "values": "0-255",
                "value_type": "range"
            },
            "anti_fog": {
                "display_name": "Anti-Fog Level",
                "method": "setAntiFog",
                "values": "0-255", 
                "value_type": "range"
            },
            
            # Scene and exposure settings
            "scene": {
                "display_name": "Scene Mode",
                "method": "setScene",
                "values": {
                    "outdoor": Scenes.OUTDOOR,
                    "indoor": Scenes.INDOOR
                },
                "value_type": "enum_map"
            },
            "exposure_mode": {
                "display_name": "Exposure Mode",
                "method": "setExposureMode",
                "values": {
                    "scene": ExposureModes.SCENE,
                    "manual": ExposureModes.MANUAL,
                    "shutter": ExposureModes.SHUTTER
                },
                "value_type": "enum_map"
            },
            "white_balance": {
                "display_name": "White Balance Mode",
                "method": "setWhiteBalanceMode",
                "values": {
                    "auto": WhiteBalanceModes.AUTO,
                    "manual": WhiteBalanceModes.MANUAL,
                    "indoor": WhiteBalanceModes.INDOOR,
                    "outdoor": WhiteBalanceModes.OUTDOOR,
                    "sunlight": WhiteBalanceModes.SUNLIGHT
                },
                "value_type": "enum_map"
            },
            "ir_mode": {
                "display_name": "IR Mode",
                "method": "setIRMode",
                "values": {
                    "auto": IRModes.AUTO,
                    "day": IRModes.DAY,
                    "night": IRModes.NIGHT
                },
                "value_type": "enum_map"
            },
            "shutter_speed": {
                "display_name": "Shutter Speed",
                "method": "setShutterSpeed",
                "values": {
                    "1/8000": ShutterValues._1_8000,
                    "1/6000": ShutterValues._1_6000,
                    "1/4000": ShutterValues._1_4000,
                    "1/2000": ShutterValues._1_2000,
                    "1/1000": ShutterValues._1_1000,
                    "1/500": ShutterValues._1_500,
                    "1/250": ShutterValues._1_250,
                    "1/200": ShutterValues._1_200,
                    "1/150": ShutterValues._1_150,
                    "1/100": ShutterValues._1_100,
                    "1/50": ShutterValues._1_50,
                    "1/25": ShutterValues._1_25,
                    "1/20": ShutterValues._1_20,
                    "1/15": ShutterValues._1_15,
                    "1/10": ShutterValues._1_10,
                    "1/8": ShutterValues._1_8,
                    "1/5": ShutterValues._1_5,
                    "1/3": ShutterValues._1_3,
                    "1/2": ShutterValues._1_2,
                    "1": ShutterValues._1
                },
                "value_type": "enum_map"
            },
            "manual_gain": {
                "display_name": "Manual Gain (ACG)",
                "method": "setManualACG",
                "values": {
                    "1x": AEGains._1X,
                    "2x": AEGains._2X,
                    "4x": AEGains._4X,
                    "8x": AEGains._8X,
                    "16x": AEGains._16X,
                    "32x": AEGains._32X,
                    "64x": AEGains._64X
                },
                "value_type": "enum_map"
            },
            
            # Boolean toggle features
            "wide_dynamic_range": {
                "display_name": "Wide Dynamic Range",
                "method": "toggle_wdr",
                "values": ["enable", "disable"],
                "value_type": "predefined"
            },
            "back_light": {
                "display_name": "Back Light Compensation",
                "method": "toggle_backlight",
                "values": ["enable", "disable"],
                "value_type": "predefined"
            },
            "horizontal_mirror": {
                "display_name": "Horizontal Mirror",
                "method": "toggle_horizontal_mirror",
                "values": ["enable", "disable"],
                "value_type": "predefined"
            },
            "vertical_mirror": {
                "display_name": "Vertical Mirror", 
                "method": "toggle_vertical_mirror",
                "values": ["enable", "disable"],
                "value_type": "predefined"
            },
            "anti_false_color": {
                "display_name": "Anti False Color",
                "method": "toggle_anti_false_color",
                "values": ["enable", "disable"],
                "value_type": "predefined"
            },
            "digital_image_stabilizer": {
                "display_name": "Digital Image Stabilizer",
                "method": "toggle_digital_stabilizer",
                "values": ["enable", "disable"],
                "value_type": "predefined"
            },
            "lens_shade_correction": {
                "display_name": "Lens Shade Correction",
                "method": "toggle_lens_shade_correction",
                "values": ["enable", "disable"],
                "value_type": "predefined"
            },
            "ir_illuminator": {
                "display_name": "IR Illuminator",
                "method": "toggle_ir",
                "values": ["enable", "disable"],
                "value_type": "predefined"
            }
        }
        
        self.camera = None
    
    # Toggle methods for boolean parameters
    def toggle_wdr(self, value):
        if value == "enable":
            return self.camera.setWideDynamicRangeLevel(128)  # Enable with default level
        else:
            return self.camera.disableWideDynamicRange()
    
    def toggle_backlight(self, value):
        if value == "enable":
            return self.camera.enableBackLight()
        else:
            return self.camera.disableBackLight()
    
    def toggle_horizontal_mirror(self, value):
        if value == "enable":
            return self.camera.HorizontalMirror()
        else:
            return self.camera.resetHorizontalMirror()
    
    def toggle_vertical_mirror(self, value):
        if value == "enable":
            return self.camera.VerticalMirror()
        else:
            return self.camera.resetVerticalMirror()
    
    def toggle_anti_false_color(self, value):
        if value == "enable":
            return self.camera.enableAntiFalseColor()
        else:
            return self.camera.disableAntiFalseColor()
    
    def toggle_digital_stabilizer(self, value):
        if value == "enable":
            return self.camera.enableDigitalImageStabilizer()
        else:
            return self.camera.disableDigitalImageStabilizer()
    
    def toggle_lens_shade_correction(self, value):
        if value == "enable":
            return self.camera.enableLensShadeCorrection()
        else:
            return self.camera.disableLensShadeCorrection()
    
    def toggle_ir(self, value):
        if value == "enable":
            return self.camera.setIRMode(IRModes.AUTO)  # Enable with auto mode
        else:
            return self.camera.disableIR()
    
    def add_parameter(self, key, display_name, method_name, values, value_type):
        """
        Helper method to easily add new parameters from your parameter.py file
        
        Args:
            key: Internal key name (e.g., "brightness")
            display_name: Human readable name (e.g., "Brightness")
            method_name: Method name in ParameterHandler (e.g., "setBrightness")
            values: Valid values - list for predefined, dict for enum_map, string for range/free_input
            value_type: "predefined", "enum_map", "range", or "free_input"
        
        Example usage:
            controller.add_parameter("brightness", "Brightness", "setBrightness", "0-255", "range")
        """
        self.parameters[key] = {
            "display_name": display_name,
            "method": method_name,
            "values": values,
            "value_type": value_type
        }
    
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
        """Display the parameter selection menu organized by category"""
        print("\n" + "=" * 70)
        print("📋 Available Camera Parameters:")
        print("=" * 70)
        
        # Organize parameters by category for better display
        categories = {
            "🎨 Basic Image Settings": [
                "brightness", "contrast", "saturation", "sharpness"
            ],
            "🎥 Video Settings": [
                "resolution", "framerate", "bitrate"
            ],
            "🔧 Advanced Enhancement": [
                "wdr_level", "lens_distortion_correction", "anti_fog"
            ],
            "📸 Scene & Exposure": [
                "scene", "exposure_mode", "white_balance", "ir_mode", 
                "shutter_speed", "manual_gain"
            ],
            "🔄 Toggle Features": [
                "wide_dynamic_range", "back_light", "horizontal_mirror", 
                "vertical_mirror", "anti_false_color", "digital_image_stabilizer",
                "lens_shade_correction", "ir_illuminator"
            ]
        }
        
        param_counter = 1
        for category, param_keys in categories.items():
            print(f"\n{category}")
            print("-" * (len(category) - 2))  # Subtract 2 for emoji
            
            for key in param_keys:
                if key in self.parameters:
                    config = self.parameters[key]
                    values_info = self.get_values_display(config)
                    print(f"{param_counter:2d}. {config['display_name']:<28} ({values_info})")
                    param_counter += 1
        
        print(f"\n{param_counter:2d}. Exit")
        print("=" * 70)
    
    def validate_range_value(self, value, range_str):
        """Validate if a value is within the specified range"""
        try:
            if "-" in range_str:
                min_val, max_val = map(int, range_str.split("-"))
                num_value = int(value) if isinstance(value, str) and value.replace("-", "").isdigit() else int(value)
                return min_val <= num_value <= max_val, min_val, max_val
        except (ValueError, TypeError):
            return False, None, None
        return True, None, None
    
    def get_values_display(self, config):
        """Get display string for parameter values"""
        if config["value_type"] == "predefined":
            values = config["values"]
            if len(values) <= 4:
                return ", ".join(values)
            else:
                return f"{len(values)} options"
        elif config["value_type"] == "enum_map":
            values = list(config["values"].keys())
            if len(values) <= 4:
                return ", ".join(values)
            else:
                return f"{len(values)} options"
        elif config["value_type"] == "range":
            return config["values"]
        else:
            return config["values"]
    
    def get_parameter_choice(self):
        """Get user's parameter selection"""
        # Create a flat list of parameter keys in display order
        param_order = []
        categories = {
            "🎨 Basic Image Settings": [
                "brightness", "contrast", "saturation", "sharpness"
            ],
            "🎥 Video Settings": [
                "resolution", "framerate", "bitrate"
            ],
            "🔧 Advanced Enhancement": [
                "wdr_level", "lens_distortion_correction", "anti_fog"
            ],
            "📸 Scene & Exposure": [
                "scene", "exposure_mode", "white_balance", "ir_mode", 
                "shutter_speed", "manual_gain"
            ],
            "🔄 Toggle Features": [
                "wide_dynamic_range", "back_light", "horizontal_mirror", 
                "vertical_mirror", "anti_false_color", "digital_image_stabilizer",
                "lens_shade_correction", "ir_illuminator"
            ]
        }
        
        for category, param_keys in categories.items():
            for key in param_keys:
                if key in self.parameters:
                    param_order.append(key)
        
        while True:
            try:
                choice = input("\n🔧 Select parameter (number): ").strip()
                choice_num = int(choice)
                
                if choice_num == len(param_order) + 1:
                    return None  # Exit
                
                if 1 <= choice_num <= len(param_order):
                    return param_order[choice_num - 1]
                else:
                    print(f"❌ Invalid choice. Please enter 1-{len(param_order) + 1}")
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
            
            while True:
                value = input("Enter value: ").strip()
                
                # For range values, validate the input
                if config["value_type"] == "range" and "-" in config["values"]:
                    is_valid, min_val, max_val = self.validate_range_value(value, config["values"])
                    
                    if is_valid:
                        # Convert to int if it's a valid number
                        try:
                            return int(value)
                        except ValueError:
                            try:
                                return float(value)
                            except ValueError:
                                return value
                    else:
                        if min_val is not None and max_val is not None:
                            print(f"❌ Value must be between {min_val} and {max_val}. Please try again.")
                        else:
                            print(f"❌ Invalid value format. Please enter a number between {config['values']}.")
                        continue
                else:
                    # For free input, return as-is
                    return value
    
    def apply_parameter_change(self, param_key, value):
        """Apply the parameter change"""
        config = self.parameters[param_key]
        method_name = config["method"]
        
        print(f"\n⚙️  Applying {config['display_name']} = {value}")
        
        try:
            # Check if it's a toggle method (custom methods in this class)
            if method_name.startswith("toggle_"):
                method = getattr(self, method_name)
                success = method(value)
            else:
                # Regular method from the camera object
                method = getattr(self.camera, method_name)
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
        
        # Convert and validate value if needed
        config = self.parameters[param_key]
        if config["value_type"] == "enum_map":
            if value in config["values"]:
                value = config["values"][value]
            else:
                print(f"❌ Invalid value for {param_name}: {value}")
                print(f"Valid values: {list(config['values'].keys())}")
                return 1
        elif config["value_type"] == "range" and "-" in config["values"]:
            is_valid, min_val, max_val = self.validate_range_value(value, config["values"])
            if not is_valid:
                print(f"❌ Invalid value for {param_name}: {value}")
                print(f"Valid range: {config['values']}")
                return 1
            # Convert to int for range values
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass
        
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
        print("  # Basic image settings")
        print("  python3 change_parameter.py resolution 1080p")
        print("  python3 change_parameter.py framerate 25")
        print("  python3 change_parameter.py brightness 128")
        print("  python3 change_parameter.py contrast 200")
        print("  python3 change_parameter.py saturation 150")
        print("  python3 change_parameter.py bitrate 5000")
        print("")
        print("  # Scene and exposure")
        print("  python3 change_parameter.py scene indoor")
        print("  python3 change_parameter.py exposure_mode manual")
        print("  python3 change_parameter.py white_balance auto")
        print("  python3 change_parameter.py ir_mode night")
        print("  python3 change_parameter.py shutter_speed '1/100'")
        print("")
        print("  # Toggle features")
        print("  python3 change_parameter.py back_light enable")
        print("  python3 change_parameter.py horizontal_mirror disable")
        print("  python3 change_parameter.py anti_false_color enable")
        print("")
        print("🔍 Run without arguments for interactive mode with full menu!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
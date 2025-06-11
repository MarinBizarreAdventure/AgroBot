#!/usr/bin/env python3
"""
MAVLink setup and configuration script for AgroBot Raspberry Pi
"""

import os
import sys
import time
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MAVLinkSetup:
    """MAVLink setup and configuration helper"""
    
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.project_root = self.script_dir.parent
        self.config_dir = self.project_root / "config"
        
    def run_setup(self):
        """Run complete MAVLink setup process"""
        logger.info("Starting MAVLink setup for AgroBot Raspberry Pi")
        
        try:
            # Check system requirements
            self.check_system_requirements()
            
            # Install system dependencies
            self.install_system_dependencies()
            
            # Configure serial ports
            self.configure_serial_ports()
            
            # Setup MAVLink permissions
            self.setup_mavlink_permissions()
            
            # Test MAVLink connection
            self.test_mavlink_connection()
            
            # Create configuration files
            self.create_configuration_files()
            
            logger.info("MAVLink setup completed successfully!")
            
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            sys.exit(1)
    
    def check_system_requirements(self):
        """Check if system meets requirements"""
        logger.info("Checking system requirements...")
        
        # Check Python version
        if sys.version_info < (3, 8):
            raise Exception("Python 3.8 or higher is required")
        
        # Check if running on Raspberry Pi
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
            if 'Raspberry Pi' not in cpuinfo:
                logger.warning("Not running on Raspberry Pi - some features may not work")
        except:
            logger.warning("Could not detect Raspberry Pi")
        
        # Check available serial ports
        serial_ports = self.detect_serial_ports()
        logger.info(f"Found serial ports: {serial_ports}")
        
        # Check GPIO access
        if os.path.exists('/dev/gpiomem'):
            logger.info("GPIO access available")
        else:
            logger.warning("GPIO access not available")
    
    def install_system_dependencies(self):
        """Install required system packages"""
        logger.info("Installing system dependencies...")
        
        packages = [
            'python3-dev',
            'python3-pip',
            'python3-venv',
            'build-essential',
            'libxml2-dev',
            'libxslt-dev',
            'libblas-dev',
            'liblapack-dev',
            'gfortran',
            'pkg-config',
            'libfreetype6-dev',
            'libpng-dev',
            'minicom',
            'screen',
            'gpsd',
            'gpsd-clients',
            'i2c-tools',
            'git'
        ]
        
        # Update package list
        self.run_command(['sudo', 'apt-get', 'update'])
        
        # Install packages
        cmd = ['sudo', 'apt-get', 'install', '-y'] + packages
        self.run_command(cmd)
        
        logger.info("System dependencies installed")
    
    def configure_serial_ports(self):
        """Configure serial ports for MAVLink communication"""
        logger.info("Configuring serial ports...")
        
        # Enable UART on Raspberry Pi
        self.enable_uart()
        
        # Disable serial console (if needed)
        self.disable_serial_console()
        
        # Set appropriate permissions
        self.setup_serial_permissions()
        
        logger.info("Serial ports configured")
    
    def enable_uart(self):
        """Enable UART on Raspberry Pi"""
        config_file = "/boot/config.txt"
        
        if not os.path.exists(config_file):
            logger.warning(f"{config_file} not found - skipping UART configuration")
            return
        
        # Read current config
        with open(config_file, 'r') as f:
            config_content = f.read()
        
        # Add UART configuration if not present
        uart_settings = [
            "enable_uart=1",
            "dtparam=spi=on",
            "dtparam=i2c_arm=on"
        ]
        
        modified = False
        for setting in uart_settings:
            if setting not in config_content:
                config_content += f"\n{setting}\n"
                modified = True
        
        # Write back if modified
        if modified:
            self.backup_file(config_file)
            with open(config_file, 'w') as f:
                f.write(config_content)
            logger.info("UART configuration added to /boot/config.txt")
        else:
            logger.info("UART already configured")
    
    def disable_serial_console(self):
        """Disable serial console to free up UART for MAVLink"""
        cmdline_file = "/boot/cmdline.txt"
        
        if not os.path.exists(cmdline_file):
            logger.warning(f"{cmdline_file} not found - skipping console configuration")
            return
        
        with open(cmdline_file, 'r') as f:
            cmdline = f.read().strip()
        
        # Remove console parameters
        console_params = ['console=serial0,115200', 'console=ttyAMA0,115200']
        modified = False
        
        for param in console_params:
            if param in cmdline:
                cmdline = cmdline.replace(param, '').strip()
                modified = True
        
        if modified:
            self.backup_file(cmdline_file)
            with open(cmdline_file, 'w') as f:
                f.write(cmdline)
            logger.info("Serial console disabled")
        else:
            logger.info("Serial console already disabled")
    
    def setup_serial_permissions(self):
        """Setup proper permissions for serial devices"""
        # Add user to dialout group
        username = os.getenv('USER', 'pi')
        try:
            self.run_command(['sudo', 'usermod', '-a', '-G', 'dialout', username])
            logger.info(f"Added {username} to dialout group")
        except Exception as e:
            logger.warning(f"Could not add user to dialout group: {e}")
        
        # Set udev rules for MAVLink devices
        udev_rules = """# MAVLink device rules
SUBSYSTEM=="tty", ATTRS{idVendor}=="26ac", ATTRS{idProduct}=="0011", SYMLINK+="pixhawk"
SUBSYSTEM=="tty", ATTRS{idVendor}=="3185", ATTRS{idProduct}=="0016", SYMLINK+="pixhawk"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1209", ATTRS{idProduct}=="5741", SYMLINK+="pixhawk"
"""
        
        udev_file = "/etc/udev/rules.d/99-mavlink.rules"
        try:
            with open(udev_file, 'w') as f:
                f.write(udev_rules)
            self.run_command(['sudo', 'udevadm', 'control', '--reload-rules'])
            logger.info("MAVLink udev rules installed")
        except Exception as e:
            logger.warning(f"Could not install udev rules: {e}")
    
    def setup_mavlink_permissions(self):
        """Setup MAVLink specific permissions"""
        # Create MAVLink group
        try:
            self.run_command(['sudo', 'groupadd', '-f', 'mavlink'])
            logger.info("MAVLink group created")
        except:
            pass
        
        # Add user to MAVLink group
        username = os.getenv('USER', 'pi')
        try:
            self.run_command(['sudo', 'usermod', '-a', '-G', 'mavlink', username])
            logger.info(f"Added {username} to mavlink group")
        except Exception as e:
            logger.warning(f"Could not add user to mavlink group: {e}")
    
    def test_mavlink_connection(self):
        """Test MAVLink connection"""
        logger.info("Testing MAVLink connection...")
        
        # Try to import pymavlink
        try:
            import pymavlink
            logger.info(f"PyMAVLink version: {pymavlink.__version__}")
        except ImportError:
            logger.error("PyMAVLink not installed - install with: pip install pymavlink")
            return False
        
        # Test serial ports
        serial_ports = self.detect_serial_ports()
        
        for port in serial_ports:
            if self.test_serial_port(port):
                logger.info(f"Successfully tested serial port: {port}")
            else:
                logger.warning(f"Could not test serial port: {port}")
        
        return True
    
    def create_configuration_files(self):
        """Create initial configuration files"""
        logger.info("Creating configuration files...")
        
        # Ensure config directory exists
        self.config_dir.mkdir(exist_ok=True)
        
        # Create MAVLink configuration
        mavlink_config = {
            "connection_string": "/dev/ttyUSB0",
            "baud_rate": 57600,
            "timeout": 5.0,
            "auto_connect": True,
            "heartbeat_timeout": 10.0
        }
        
        self.write_json_config("mavlink.json", mavlink_config)
        
        # Create hardware configuration
        hardware_config = {
            "gpio_pins": {
                "status_led": 18,
                "error_led": 19,
                "buzzer": 20,
                "emergency_stop": 21
            },
            "i2c_bus": 1,
            "spi_bus": 0,
            "serial_ports": list(self.detect_serial_ports())
        }
        
        self.write_json_config("hardware.json", hardware_config)
        
        logger.info("Configuration files created")
    
    def detect_serial_ports(self) -> List[str]:
        """Detect available serial ports"""
        import serial.tools.list_ports
        
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append(port.device)
        
        # Also check common Raspberry Pi ports
        common_ports = ['/dev/ttyAMA0', '/dev/ttyS0', '/dev/ttyUSB0', '/dev/ttyUSB1']
        for port in common_ports:
            if os.path.exists(port) and port not in ports:
                ports.append(port)
        
        return sorted(ports)
    
    def test_serial_port(self, port: str) -> bool:
        """Test if serial port is accessible"""
        try:
            import serial
            ser = serial.Serial(port, 57600, timeout=1)
            ser.close()
            return True
        except Exception as e:
            logger.debug(f"Could not open {port}: {e}")
            return False
    
    def write_json_config(self, filename: str, config: Dict[str, Any]):
        """Write JSON configuration file"""
        import json
        
        config_path = self.config_dir / filename
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Created configuration: {config_path}")
    
    def backup_file(self, filepath: str):
        """Create backup of file before modification"""
        backup_path = f"{filepath}.backup_{int(time.time())}"
        try:
            self.run_command(['sudo', 'cp', filepath, backup_path])
            logger.info(f"Backup created: {backup_path}")
        except Exception as e:
            logger.warning(f"Could not create backup: {e}")
    
    def run_command(self, cmd: List[str], check: bool = True):
        """Run system command"""
        logger.debug(f"Running command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if check and result.returncode != 0:
            raise Exception(f"Command failed: {' '.join(cmd)}\nError: {result.stderr}")
        
        return result
    
    def print_summary(self):
        """Print setup summary"""
        print("\n" + "="*60)
        print("MAVLink Setup Complete!")
        print("="*60)
        print("\nNext steps:")
        print("1. Reboot the Raspberry Pi to apply UART changes")
        print("2. Connect your Pixhawk flight controller")
        print("3. Run the test connection script")
        print("4. Start the AgroBot application")
        print("\nCommands:")
        print("  sudo reboot")
        print("  python scripts/test_connection.py")
        print("  python main.py")
        print("\nFor help, see: docs/setup.md")
        print("="*60)


def main():
    """Main setup function"""
    if os.geteuid() == 0:
        logger.error("Do not run this script as root")
        sys.exit(1)
    
    setup = MAVLinkSetup()
    setup.run_setup()
    setup.print_summary()


if __name__ == "__main__":
    main()
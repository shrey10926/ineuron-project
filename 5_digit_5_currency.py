import socket, json, os
from datetime import datetime

# Device configuration
DEVICE_IP = '192.168.1.101'  # Replace with your device's IP
DEVICE_PORT = 20108          # Replace with the correct port

OVERFLOW_POSITIONS = {
    'A': ('Z', 3),  # USD uses position 4 (index 3) of Z module
    'B': ('Z', 2),  # GBP uses position 3 (index 2) of Z module  
    'C': ('Z', 1),  # EUR uses position 2 (index 1) of Z module
    'D': ('Z', 0),  # CAN uses position 1 (index 0) of Z module
    'E': ('Y', 3)   # JPY uses position 4 (index 3) of Y module
}

# Replace the existing CURRENCY_NAMES dictionary
CURRENCY_NAMES = {
    'A': 'USD',
    'B': 'GBP', 
    'C': 'EUR',
    'D': 'CAN',
    'E': 'JPY'
}

class ForexController:

    def __init__(self, state_file='forex_state.json'):
        self.client_socket = None
        self.state_file = state_file
        
        # Initialize state - tracks current values of all modules
        self.state = {
            'main_modules': {'A': '0000', 'B': '0000', 'C': '0000', 'D': '0000', 'E': '0000'},
            'z_module': ['0', '0', '0', '0'],  # [CAN_5th, EUR_5th, GBP_5th, USD_5th]
            'y_module': ['0', '0', '0', '0'],  # [unused, unused, unused, JPY_5th]
            'last_updated': None
        }
        
        # Load previous state if exists
        self.load_state()


    def load_state(self):
        """Load previous state from file if it exists"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    saved_state = json.load(f)
                    # Ensure backward compatibility - add Y module if not present
                    if 'y_module' not in saved_state:
                        saved_state['y_module'] = ['0', '0', '0', '0']
                    # Add JPY to main modules if not present
                    if 'E' not in saved_state.get('main_modules', {}):
                        saved_state['main_modules']['E'] = '0000'
                    
                    self.state.update(saved_state)
                    print(f"📁 Loaded previous state from {self.state_file}")
                    self.display_current_state()
            else:
                print("🆕 Starting with fresh state")
        except Exception as e:
            print(f"⚠️  Could not load state file: {e}")
            print("🆕 Starting with fresh state")


    def save_state(self):
        """Save current state to file"""
        try:
            self.state['last_updated'] = datetime.now().isoformat()
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            print(f"💾 State saved to {self.state_file}")
        except Exception as e:
            print(f"⚠️  Could not save state: {e}")


    def connect_to_device(self):
        """
        Connects to the Forex device.
        :return: True if successful, False otherwise
        """
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # self.client_socket.connect((DEVICE_IP, DEVICE_PORT))
            print(f"🔗 Connected to {DEVICE_IP}:{DEVICE_PORT}")
            return True
        except socket.error as e:
            print(f"❌ Failed to connect to the device: {e}")
            # return False
            return True


    def send_command(self, command):
        """
        Sends a command to the device.
        :param command: Command string to send
        :return: True if successful, False otherwise
        """
        try:
            # self.client_socket.sendall(command.encode())
            print(f"📤 Sent: {command}")
            return True
        except socket.error as e:
            print(f"❌ Socket error while sending command: {e}")
            # return False
            return True


    def get_z_module_value(self):
        """
        Get current Z module value from our state tracking.
        :return: Z module value as 4-digit string
        """
        return ''.join(self.state['z_module'])


    def update_overflow_module(self, currency_code, fifth_digit):
        """
        Updates the appropriate overflow module state and sends command to device.
        :param currency_code: Currency code (A, B, C, D, E)
        :param fifth_digit: The fifth digit to set (0-9)
        :return: True if successful, False otherwise
        """
        # Get overflow module and position for this currency
        module_name, position = OVERFLOW_POSITIONS[currency_code]
        
        # Update our state tracking
        if module_name == 'Z':
            self.state['z_module'][position] = str(fifth_digit)
        elif module_name == 'Y':
            self.state['y_module'][position] = str(fifth_digit)
        
        # Get the complete module value
        module_value = ''.join(self.state[f'{module_name.lower()}_module'])
        
        # Send command to device
        success = self.send_command(f"{module_name}{module_value}")
        
        if success:
            print(f"✅ Updated {module_name} module to: {module_value}")
            print(f"   Position {position + 1} set to {fifth_digit} for {CURRENCY_NAMES[currency_code]}")
            return True
        else:
            print(f"❌ Failed to update {module_name} module, rolling back state")
            return False


    def set_currency_rate(self, currency_code, rate_value):
        """
        Sets the currency rate, handling both 4 and 5 digit values.
        :param currency_code: Currency code (A, B, C, D)
        :param rate_value: Rate value as string (4 or 5 digits)
        :return: True if successful, False otherwise
        """
        currency_name = CURRENCY_NAMES[currency_code]
        print(f"\n🔄 Setting {currency_name} rate to {rate_value}")
        
        success = False
        
        if len(rate_value) == 4:
            # 4-digit value: Update main module and set Z position to 0
            print(f"   📊 4-digit rate: Main={rate_value}, Overflow=0")
            
            main_success = self.send_command(f"{currency_code}{rate_value}")
            overflow_success = self.update_overflow_module(currency_code, 0)

            if main_success and overflow_success:
                # Update our state tracking
                self.state['main_modules'][currency_code] = rate_value
                print(f"✅ Successfully set {currency_name} to {rate_value}")
                success = True
                
        elif len(rate_value) == 5:
            # 5-digit value: Update main module with first 4 digits, Z with 5th
            main_digits = rate_value[:4]
            fifth_digit = rate_value[4]
            
            print(f"   📊 5-digit rate: Main={main_digits}, Overflow={fifth_digit}")
            
            main_success = self.send_command(f"{currency_code}{main_digits}")
            overflow_success = self.update_overflow_module(currency_code, fifth_digit)

            if main_success and overflow_success:
                # Update our state tracking
                self.state['main_modules'][currency_code] = main_digits
                print(f"✅ Successfully set {currency_name} to {rate_value}")
                print(f"   Main module: {main_digits}, Overflow digit: {fifth_digit}")
                success = True
        else:
            print(f"❌ Invalid rate length. Must be 4 or 5 digits, got {len(rate_value)}")
            return False
        
        if success:
            self.save_state()  # Save state after successful update
            return True
        else:
            print(f"❌ Failed to set {currency_name} rate")
            return False


    def get_full_currency_value(self, currency_code):
        """
        Get the complete currency value (main + overflow digit).
        :param currency_code: Currency code (A, B, C, D, E)
        :return: Complete currency value as string
        """
        main_value = self.state['main_modules'][currency_code]
        module_name, position = OVERFLOW_POSITIONS[currency_code]
        
        if module_name == 'Z':
            overflow_digit = self.state['z_module'][position]
        elif module_name == 'Y':
            overflow_digit = self.state['y_module'][position]
        
        if overflow_digit == '0':
            return main_value  # 4-digit value
        else:
            return main_value + overflow_digit  # 5-digit value


    def display_current_state(self):
        """Display current state of all modules and currency values"""
        print(f"\n📊 === Current System State ===")
        
        # Show individual module states
        print(f"🔧 Module States:")
        for code, name in CURRENCY_NAMES.items():
            main_val = self.state['main_modules'][code]
            print(f"   {name} ({code}): {main_val}")
        
        z_val = ''.join(self.state['z_module'])
        y_val = ''.join(self.state['y_module'])  # Add this line
        print(f"   Overflow (Z): {z_val}")
        print(f"   Overflow (Y): {y_val}")      # Add this line
        
        # Show overflow digit allocation
        print(f"\n🔀 Overflow Digit Allocation:")
        print(f"   Z Module:")                   # Add this line
        print(f"     Position 1: {self.state['z_module'][0]} (CAN 5th digit)")
        print(f"     Position 2: {self.state['z_module'][1]} (EUR 5th digit)")
        print(f"     Position 3: {self.state['z_module'][2]} (GBP 5th digit)")
        print(f"     Position 4: {self.state['z_module'][3]} (USD 5th digit)")
        print(f"   Y Module:")                   # Add this section
        print(f"     Position 1: {self.state['y_module'][0]} (unused)")
        print(f"     Position 2: {self.state['y_module'][1]} (unused)")
        print(f"     Position 3: {self.state['y_module'][2]} (unused)")
        print(f"     Position 4: {self.state['y_module'][3]} (JPY 5th digit)")
        
        # Show complete currency values (this part should already be working correctly)
        print(f"\n💰 Complete Currency Values:")
        for code, name in CURRENCY_NAMES.items():
            full_value = self.get_full_currency_value(code)
            print(f"   {name}: {full_value}")
        
        if self.state['last_updated']:
            print(f"\n🕒 Last Updated: {self.state['last_updated']}")


    def reset_all_modules(self):
        """Reset all modules to 0000"""
        print(f"\n🔄 Resetting all modules...")
        
        success_count = 0
        
        # Reset main modules
        for code in ['A', 'B', 'C', 'D', 'E']:
            if self.send_command(f"{code}0000"):
                self.state['main_modules'][code] = '0000'
                success_count += 1
        
        # Reset Z module
        if self.send_command("Z0000"):
            self.state['z_module'] = ['0', '0', '0', '0']
            success_count += 1

        # Add Y module reset after Z module reset
        if self.send_command("Y0000"):
            self.state['y_module'] = ['0', '0', '0', '0']
            success_count += 1

        if success_count == 7:
            print(f"✅ All modules reset successfully")
            self.save_state()
            return True
        else:
            print(f"⚠️  Some modules failed to reset ({success_count}/5 successful)")
            return False


    def close_connection(self):
        """Close the socket connection"""
        if self.client_socket:
            self.client_socket.close()
            print("🔌 Connection closed.")



def main():
    controller = ForexController()
    
    # Connect to device
    if not controller.connect_to_device():
        return
    
    try:
        print("\n🚀 === Enhanced Forex Rate Controller (State Tracking) ===")
        print("📋 Commands:")
        print("   - Set rate: A12345, B2345, C34567, D4567")
        print("   - 'status' - Show current state")
        print("   - 'reset' - Reset all modules to 0000")
        print("   - 'exit' - Quit program")
        
        while True:
            user_input = input("\n💬 Enter command: ").strip().upper()
            
            if user_input == 'EXIT':
                print("👋 Exiting...")
                break
                
            if user_input == 'STATUS':
                controller.display_current_state()
                continue
                
            if user_input == 'RESET':
                confirm = input("⚠️  Reset all modules to 0000? (y/N): ").strip().lower()
                if confirm == 'y':
                    controller.reset_all_modules()
                else:
                    print("❌ Reset cancelled")
                continue
            
            # Validate input format
            if len(user_input) < 5 or len(user_input) > 6:
                print("❌ Invalid format. Use: <A-D><4-5 digits> (e.g., A1234 or A12345)")
                continue
                
            currency_code = user_input[0]
            rate_digits = user_input[1:]
            
            if currency_code not in ['A', 'B', 'C', 'D', 'E']:
                print("❌ Invalid currency code. Use A, B, C, D or E")
                continue
                
            if not rate_digits.isdigit():
                print("❌ Rate must contain only digits")
                continue
                
            if len(rate_digits) not in [4, 5]:
                print("❌ Rate must be 4 or 5 digits")
                continue
            
            # Set the currency rate
            controller.set_currency_rate(currency_code, rate_digits)
            
    except KeyboardInterrupt:
        print("\n\n⚡ Interrupted by user")
    finally:
        controller.close_connection()


if __name__ == "__main__":
    main()
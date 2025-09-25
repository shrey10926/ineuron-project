# TODO
# 1. Backup state files.
# 2. Logging
# 3. config file for creds


import socket, json, os, time
from datetime import datetime

# Device configuration
DEVICE_IP = '192.168.1.7'
DEVICE_PORT = 20108

# Updated to use only E module for all 4 currencies
OVERFLOW_POSITIONS = {
    'A': ('E', 3),  # USD uses position 4 (index 3) of E module
    'B': ('E', 2),  # GBP uses position 3 (index 2) of E module
    'C': ('E', 1),  # EUR uses position 2 (index 1) of E module
    'D': ('E', 0),  # CAN uses position 1 (index 0) of E module
}

# Updated to include only 4 currencies
CURRENCY_NAMES = {
    'A': 'USD',
    'B': 'GBP',
    'C': 'EUR',
    'D': 'CAN'
}


class ForexController:

    def __init__(self, state_file='forex_state.json', submissions_file='forex_submissions.json'):
        self.client_socket = None
        self.state_file = state_file
        self.submissions_file = submissions_file

        # Initialize submissions history - tracks last 5 submissions
        self.submissions_history = []

        # Initialize state - tracks current values of all modules
        self.state = {
            'main_modules': {'A': '0000', 'B': '0000', 'C': '0000', 'D': '0000'},
            'e_module': ['0', '0', '0', '0'],  # [CAN_5th, EUR_5th, GBP_5th, USD_5th]
            'last_updated': None
        }
        
        # Load previous state and submissions
        self.load_state()
        self.load_submissions()

    def load_state(self):
        """Load previous state from file if it exists (with validation)."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    saved_state = json.load(f)

                # Validate and apply main_modules
                if 'main_modules' in saved_state and isinstance(saved_state['main_modules'], dict):
                    filtered = {}
                    for k in ['A', 'B', 'C', 'D']:
                        v = saved_state['main_modules'].get(k)
                        # accept only 4-digit numeric strings
                        if isinstance(v, str) and v.isdigit() and len(v) == 4:
                            filtered[k] = v
                        else:
                            filtered[k] = '0000'
                    self.state['main_modules'] = filtered

                # Validate and apply e_module
                if 'e_module' in saved_state and isinstance(saved_state['e_module'], list) and len(saved_state['e_module']) == 4:
                    e_list = []
                    for x in saved_state['e_module']:
                        s = str(x)
                        # take first char if digit, else '0'
                        if s and s[0].isdigit():
                            e_list.append(s[0])
                        else:
                            e_list.append('0')
                    self.state['e_module'] = e_list

                # Apply last_updated if present
                if 'last_updated' in saved_state and isinstance(saved_state['last_updated'], str):
                    self.state['last_updated'] = saved_state['last_updated']

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

    def load_submissions(self):
        """Load submission history from file if it exists."""
        try:
            if os.path.exists(self.submissions_file):
                with open(self.submissions_file, 'r') as f:
                    saved_submissions = json.load(f)
                
                if isinstance(saved_submissions, list):
                    # Keep only last 5 submissions
                    self.submissions_history = saved_submissions[-5:]
                
                print(f"📋 Loaded {len(self.submissions_history)} previous submissions")
            else:
                print("📋 Starting with empty submission history")
        except Exception as e:
            print(f"⚠️  Could not load submissions file: {e}")

    def save_submissions(self):
        """Save current submission history to file."""
        try:
            with open(self.submissions_file, 'w') as f:
                json.dump(self.submissions_history, f, indent=2)
        except Exception as e:
            print(f"⚠️  Could not save submissions: {e}")

    def log_submission(self, raw_input, entries, results):
        """Add a new submission to history, keeping only last 5."""
        submission = {
            'timestamp': datetime.now().isoformat(),
            'raw_input': raw_input,
            'entries': entries,
            'results': results,
            'success_count': sum(1 for r in results if r['success']),
            'total_count': len(results)
        }
        
        # Add to history
        self.submissions_history.append(submission)
        
        # Keep only last 5 submissions
        if len(self.submissions_history) > 5:
            self.submissions_history = self.submissions_history[-5:]
        
        # Save to file
        self.save_submissions()

    def connect_to_device(self, timeout=5.0):
        """
        Connects to the Forex device with a timeout.
        :return: True if successful, False otherwise
        """
        try:
            # If existing socket present, close it first
            if self.client_socket:
                try:
                    self.client_socket.close()
                except Exception:
                    pass
                self.client_socket = None

            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Optional: reduce blocking time
            self.client_socket.settimeout(timeout)
            # # Optional: disable Nagle algo if you need low-latency small writes
            # try:
            #     self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            # except Exception:
            #     pass

            # self.client_socket.connect((DEVICE_IP, DEVICE_PORT))
            print(f"🔗 Connected to {DEVICE_IP}:{DEVICE_PORT}")
            return True

        except socket.error as e:
            print(f"❌ Failed to connect to the device: {e}")
            self.client_socket = None
            return False

    def connect_with_retry(self, max_retries=3, backoff_factor=2):
        """
        Enhanced connection with exponential backoff retry logic.
        :param max_retries: Maximum number of connection attempts (default: 3)
        :param backoff_factor: Multiplier for wait time between retries (default: 2)
        :return: True if successful, False if all attempts failed
        """
        print(f"🔄 Attempting connection with up to {max_retries} retries...")
        
        for attempt in range(max_retries):
            print(f"📡 Connection attempt {attempt + 1}/{max_retries}")
            
            if self.connect_to_device():
                return True

            # Don't wait after the final attempt
            if attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                print(f"⏳ Connection failed. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"❌ All {max_retries} connection attempts failed")
        
        return False

    def send_command(self, command, terminator=""):
        """
        Sends a command to the device.
        Returns True if successful, False otherwise.
        """
        if not self.client_socket:
            print("❌ Not connected to device (socket is None).")
            return False
        try:
            msg = (command + terminator).encode()
            print(f'MSG --> {msg}')
            # self.client_socket.sendall(msg)
            print(f"📤 Sent: {command}{terminator}")
            # short sleep to give device time to process (if needed)
            time.sleep(0.25)
            return True
        except (socket.error, AttributeError) as e:
            print(f"❌ Socket error while sending command: {e}")
            return False

    def update_overflow_module(self, currency_code, fifth_digit):
        """
        Updates the E module state and sends command to device.
        Commits in-memory state only after successful send.
        :param currency_code: Currency code (A, B, C, D)
        :param fifth_digit: The fifth digit to set (0-9)
        :return: True if successful, False otherwise
        """

        print(f'currency code --> {currency_code}')
        # Get overflow module and position for this currency
        module_name, position = OVERFLOW_POSITIONS[currency_code]
        print(f'module name and position --> {module_name} {position}')

        # Prepare new e_module value without mutating state yet
        new_e = self.state['e_module'][:] # shallow copy
        new_e[position] = str(fifth_digit)
        print(f'new_e --> {new_e}')

        # Get the complete module value
        module_value = ''.join(new_e)

        # Send command to device
        success = self.send_command(f"{module_name}{module_value}")

        if success:
            # Commit to in-memory state only after successful send
            self.state['e_module'] = new_e
            print(f"✅ Updated {module_name} module to: {module_value}")
            print(f"   Position {position + 1} set to {fifth_digit} for {CURRENCY_NAMES[currency_code]}")
            return True
        else:
            print(f"❌ Failed to update {module_name} module. No state change performed.")
            return False

    def set_currency_rate(self, currency_code, rate_value):
        """
        Sets the currency rate, handling 3, 4, and 5 digit values.
        All inputs are normalized to 5 digits with leading zeros if needed.
        :param currency_code: Currency code (A, B, C, D)
        :param rate_value: Rate value as string (3, 4, or 5 digits)
        :return: True if successful, False otherwise
        """
        currency_name = CURRENCY_NAMES[currency_code]
        original_value = rate_value

        # Validate input length (3, 4, or 5 digits)
        if len(rate_value) not in [3, 4, 5]:
            print(f"❌ Invalid rate length. Must be 3, 4, or 5 digits, got {len(rate_value)}")
            return False

        # Pad to 5 digits with leading zeros if needed
        padded_value = rate_value.zfill(5)

        print(f"\n🔄 Setting {currency_name} rate")
        print(f"   📥 Original input: {original_value}")
        print(f"   📏 Padded to 5 digits: {padded_value}")

        # Always use 5-digit logic now
        main_digits = padded_value[:4]  # First 4 digits
        fifth_digit = padded_value[4]   # 5th digit

        print(f"   📊 Main module: {main_digits}, Overflow digit: {fifth_digit}")

        # Send commands to device
        main_success = self.send_command(f"{currency_code}{main_digits}")
        overflow_success = self.update_overflow_module(currency_code, fifth_digit)

        if main_success and overflow_success:
            # Update our state tracking
            self.state['main_modules'][currency_code] = main_digits
            print(f"✅ Successfully set {currency_name}")
            print(f"   Final display: {padded_value} (Main: {main_digits}, Overflow: {fifth_digit})")
            self.save_state()
            return True
        else:
            print(f"❌ Failed to set {currency_name} rate")
            return False

    def get_full_currency_value(self, currency_code):
        """
        Get the complete currency value (main + overflow digit).
        :param currency_code: Currency code (A, B, C, D)
        :return: Complete currency value as string
        """
        main_value = self.state['main_modules'][currency_code]
        module_name, position = OVERFLOW_POSITIONS[currency_code]

        print(f'main value, module name and position --> {main_value}, {module_name}, {position}')

        # Only E module now
        overflow_digit = self.state['e_module'][position]
        print(f'overflow digit --> {overflow_digit}')

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

        e_val = ''.join(self.state['e_module'])
        print(f"   Overflow (E): {e_val}")

        # Show overflow digit allocation
        print(f"\n🔀 Overflow Digit Allocation (E Module):")
        print(f"     Position 1: {self.state['e_module'][0]} (CAN 5th digit)")
        print(f"     Position 2: {self.state['e_module'][1]} (EUR 5th digit)")
        print(f"     Position 3: {self.state['e_module'][2]} (GBP 5th digit)")
        print(f"     Position 4: {self.state['e_module'][3]} (USD 5th digit)")

        # Show complete currency values
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

        # Reset main modules (only 4 now)
        for code in ['A', 'B', 'C', 'D']:
            if self.send_command(f"{code}0000"):
                self.state['main_modules'][code] = '0000'
                success_count += 1

        # Reset E module only
        if self.send_command("E0000"):
            self.state['e_module'] = ['0', '0', '0', '0']
            success_count += 1

        if success_count == 5:  # 4 main modules + 1 E module = 5 total
            print(f"✅ All modules reset successfully")
            self.save_state()
            return True
        else:
            print(f"⚠️  Some modules failed to reset ({success_count}/5 successful)")
            return False

    def close_connection(self):
        """Close the socket connection"""
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
            self.client_socket = None
            print("🔌 Connection closed.")


def main():
    controller = ForexController()

    # Connect to device
    if not controller.connect_with_retry():
        print("💥 Could not establish connection to forex device. Exiting...")
        return

    try:
        print("\n🚀 === Forex Rate Controller (4 Currencies) ===")
        print("📋 Commands:")
        print("   - Set rate(s): A123, B4567, C98765 (comma-separated)")
        print("   - 'status' - Show current state")
        print("   - 'reset' - Reset all modules to 0000")
        print("   - 'exit' - Quit program")

        while True:
            user_input = input("\n💬 Enter command (comma-separated for multiple rates): ").strip().upper()

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

            # Split input by commas and process each entry
            entries = [entry.strip() for entry in user_input.split(',') if entry.strip()]
            if not entries:
                print("❌ No valid entries found.")
                continue

            # Track results for logging
            results = []
            all_success = True

            for entry in entries:
                if len(entry) < 4 or len(entry) > 6:
                    print(f"❌ Invalid format for '{entry}'. Use: <A-D><3-5 digits>")
                    results.append({'entry': entry, 'success': False, 'error': 'Invalid format'})
                    all_success = False
                    continue

                currency_code = entry[0]
                rate_digits = entry[1:]

                if currency_code not in ['A', 'B', 'C', 'D']:
                    print(f"❌ Invalid currency code in '{entry}'. Use A, B, C, or D")
                    results.append({'entry': entry, 'success': False, 'error': 'Invalid currency code'})
                    all_success = False
                    continue

                if not rate_digits.isdigit():
                    print(f"❌ Rate must contain only digits in '{entry}'")
                    results.append({'entry': entry, 'success': False, 'error': 'Non-digit characters'})
                    all_success = False
                    continue

                # Set the currency rate
                success = controller.set_currency_rate(currency_code, rate_digits)
                results.append({
                    'entry': entry, 
                    'currency': CURRENCY_NAMES[currency_code],
                    'success': success,
                    'error': None if success else 'Failed to set rate'
                })
                if not success:
                    all_success = False

            # Log the entire submission
            controller.log_submission(user_input, entries, results)

            if all_success:
                print("✅ All currency rates updated successfully.")
            else:
                print("⚠️  Some entries failed to update. See messages above.")

    except KeyboardInterrupt:
        print("\n\n⚡ Interrupted by user")
    finally:
        controller.close_connection()

if __name__ == "__main__":
    main()
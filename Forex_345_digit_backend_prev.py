import socket, json, os, time
from datetime import datetime

# Device configuration
DEVICE_IP = '192.168.1.7'
DEVICE_PORT = 20108

DEBUG = False

# Overflow mapping:
#   A-D use E module (positions 0..3)
#   F (JPY) uses G module (position 3 -> 4th digit of G)
OVERFLOW_POSITIONS = {
    'A': ('E', 3),  # USD uses position 4 (index 3) of E module
    'B': ('E', 2),  # GBP uses position 3 (index 2) of E module
    'C': ('E', 1),  # EUR uses position 2 (index 1) of E module
    'D': ('E', 0),  # CAN uses position 1 (index 0) of E module
    'F': ('G', 3),  # JPY uses position 4 (index 3) of G module
}

# Currency names (main modules)
CURRENCY_NAMES = {
    'A': 'USD',
    'B': 'GBP',
    'C': 'EUR',
    'D': 'CAN',
    'F': 'JPY'
}

ALL_CURRENCIES = list(CURRENCY_NAMES.keys())
# Unique overflow module names derived from OVERFLOW_POSITIONS
OVERFLOW_MODULE_NAMES = sorted({module for (module, _) in OVERFLOW_POSITIONS.values()})

def dbg(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


class ForexController:

    def __init__(self, state_file='forex_state.json', submissions_file='forex_submissions.json'):
        self.client_socket = None
        self.state_file = state_file
        self.submissions_file = submissions_file
        self.submissions_history = []

        # default state: build main_modules dynamically
        self.state = {
            'main_modules': {k: '0000' for k in ALL_CURRENCIES},
            # create default overflow lists for each overflow module name
            **{f"{m.lower()}_module": ['0', '0', '0', '0'] for m in OVERFLOW_MODULE_NAMES},
            'last_updated': None
        }

        self.load_state()
        self.load_submissions()

    def _sanitize_main_modules(self, saved):
        """Return a dict with valid 4-digit strings for each currency in ALL_CURRENCIES."""
        out = {}
        src = saved.get('main_modules', {}) if isinstance(saved, dict) else {}
        for k in ALL_CURRENCIES:
            v = src.get(k)
            if isinstance(v, str) and v.isdigit() and len(v) == 4:
                out[k] = v
            else:
                out[k] = '0000'
        return out

    def _sanitize_overflow_list(self, saved, key):
        """
        Validate saved[key] is a list of length 4 and return sanitized list of single digits.
        key should be like 'e_module' or 'g_module' (lowercase).
        """
        out = ['0', '0', '0', '0']
        src = saved.get(key) if isinstance(saved, dict) else None
        if isinstance(src, list) and len(src) == 4:
            for i, x in enumerate(src):
                s = str(x)
                out[i] = s[0] if s and s[0].isdigit() else '0'
        return out

    def load_state(self):
        """Load previous state with sanitization using helpers."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    saved = json.load(f)

                self.state['main_modules'] = self._sanitize_main_modules(saved)

                # sanitize each overflow module present in state structure
                for m in OVERFLOW_MODULE_NAMES:
                    key = f"{m.lower()}_module"  # e_module, g_module etc.
                    self.state[key] = self._sanitize_overflow_list(saved, key)

                if 'last_updated' in saved and isinstance(saved['last_updated'], str):
                    self.state['last_updated'] = saved['last_updated']

                print(f"📁 Loaded previous state from {self.state_file}")
                self.display_current_state()
            else:
                print("🆕 Starting with fresh state")
        except Exception as e:
            print(f"⚠️  Could not load state file: {e}")
            print("🆕 Starting with fresh state")

    def save_state(self):
        try:
            self.state['last_updated'] = datetime.now().isoformat()
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            print(f"💾 State saved to {self.state_file}")
        except Exception as e:
            print(f"⚠️  Could not save state: {e}")

    def load_submissions(self):
        try:
            if os.path.exists(self.submissions_file):
                with open(self.submissions_file, 'r') as f:
                    saved = json.load(f)
                if isinstance(saved, list):
                    self.submissions_history = saved[-5:]
                print(f"📋 Loaded {len(self.submissions_history)} previous submissions")
            else:
                print("📋 Starting with empty submission history")
        except Exception as e:
            print(f"⚠️  Could not load submissions file: {e}")

    def save_submissions(self):
        try:
            with open(self.submissions_file, 'w') as f:
                json.dump(self.submissions_history, f, indent=2)
        except Exception as e:
            print(f"⚠️  Could not save submissions: {e}")

    def log_submission(self, raw_input, entries, results):
        submission = {
            'timestamp': datetime.now().isoformat(),
            'raw_input': raw_input,
            'entries': entries,
            'results': results,
            'success_count': sum(1 for r in results if r['success']),
            'total_count': len(results),
        }
        self.submissions_history.append(submission)
        self.submissions_history = self.submissions_history[-5:]
        self.save_submissions()

    # --------------------
    # Network / send
    # --------------------
    def connect_to_device(self, timeout=5.0):
        try:
            if self.client_socket:
                try:
                    self.client_socket.close()
                except Exception:
                    pass
                self.client_socket = None

            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(timeout)
            self.client_socket.connect((DEVICE_IP, DEVICE_PORT))
            print(f"🔗 Connected to {DEVICE_IP}:{DEVICE_PORT}")
            return True
        except socket.error as e:
            print(f"❌ Failed to connect to the device: {e}")
            self.client_socket = None
            return False

    def connect_with_retry(self, max_retries=3, backoff_factor=2):
        print(f"🔄 Attempting connection with up to {max_retries} retries...")
        for attempt in range(max_retries):
            dbg(f"Attempt {attempt+1}/{max_retries}")
            if self.connect_to_device():
                return True
            if attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                print(f"⏳ Connection failed. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"❌ All {max_retries} connection attempts failed")
        return False

    def send_command(self, command, terminator=""):
        if not self.client_socket:
            print("❌ Not connected to device (socket is None).")
            return False
        try:
            msg = (command + terminator).encode()
            dbg(f"MSG --> {msg}")
            self.client_socket.sendall(msg)
            dbg(f"📤 Sent: {command}{terminator}")
            time.sleep(0.25)
            return True
        except (socket.error, AttributeError) as e:
            print(f"❌ Socket error while sending command: {e}")
            return False

    # --------------------
    # Overflow handling (generic)
    # --------------------
    def update_overflow_module(self, currency_code, fifth_digit):
        """
        Generic: find module & position from OVERFLOW_POSITIONS,
        update the corresponding in-memory overflow list, and send full module.
        """
        if currency_code not in OVERFLOW_POSITIONS:
            print(f"❌ No overflow mapping for {currency_code}")
            return False

        module_name, position = OVERFLOW_POSITIONS[currency_code]
        dbg(f"Updating overflow: {currency_code} -> module {module_name}, pos {position}")

        key = f"{module_name.lower()}_module"
        module_list = self.state.get(key, ['0', '0', '0', '0'])[:]
        module_list[position] = str(fifth_digit)
        module_value = ''.join(module_list)
        dbg(f"Prepared {module_name}{module_value}")

        # Overflow module updation. Test this with False.
        success = self.send_command(f"{module_name}{module_value}")
        if success:
            self.state[key] = module_list
            dbg(f"Updated state {key} = {module_list}")
            print(f"✅ Updated {module_name} module to: {module_value}")
            print(f"   Position {position + 1} set to {fifth_digit} for {CURRENCY_NAMES.get(currency_code, currency_code)}")
            return True
        else:
            print(f"❌ Failed to update {module_name} module. No state change performed.")
            return False

    # --------------------
    # Currency set / query
    # --------------------
    def set_currency_rate(self, currency_code, rate_value):
        currency_name = CURRENCY_NAMES.get(currency_code, currency_code)
        if len(rate_value) not in (3, 4, 5):
            print(f"❌ Invalid rate length for {currency_code}: {len(rate_value)}")
            return False

        padded_value = rate_value.zfill(5)
        main_digits, fifth_digit = padded_value[:4], padded_value[4]
        dbg(f"Setting {currency_code}: main={main_digits}, overflow={fifth_digit}")

        main_success = self.send_command(f"{currency_code}{main_digits}")
        overflow_success = self.update_overflow_module(currency_code, fifth_digit)

        if main_success and overflow_success:
            self.state['main_modules'][currency_code] = main_digits
            print(f"✅ Successfully set {currency_name} -> {padded_value}")
            self.save_state()
            return True
        else:
            print(f"❌ Failed to set {currency_name}")
            return False

    def get_full_currency_value(self, currency_code):
        main_value = self.state['main_modules'].get(currency_code, '0000')
        module_name, position = OVERFLOW_POSITIONS.get(currency_code, (None, None))
        overflow_digit = '0'
        if module_name:
            key = f"{module_name.lower()}_module"
            overflow_list = self.state.get(key, ['0', '0', '0', '0'])
            overflow_digit = overflow_list[position]
        return main_value if overflow_digit == '0' else main_value + overflow_digit

    # --------------------
    # UI / Reset / Close
    # --------------------
    def display_current_state(self):
        print("\n📊 === Current System State ===")
        print("🔧 Module States:")
        for code, name in CURRENCY_NAMES.items():
            print(f"   {name} ({code}): {self.state['main_modules'].get(code, '0000')}")

        # Show overflow module values dynamically
        for m in OVERFLOW_MODULE_NAMES:
            key = f"{m.lower()}_module"
            print(f"   Overflow ({m}): {''.join(self.state.get(key, ['0','0','0','0']))}")

        # Show allocation (invert OVERFLOW_POSITIONS)
        alloc = {}
        for cur, (mod, pos) in OVERFLOW_POSITIONS.items():
            alloc.setdefault(mod, {})[pos] = f"{CURRENCY_NAMES.get(cur,cur)} ({cur})"

        for mod, positions in alloc.items():
            print(f"\n🔀 Overflow Digit Allocation ({mod}):")
            for pos in range(4):
                desc = positions.get(pos, "unused")
                key = f"{mod.lower()}_module"
                val = self.state.get(key, ['0','0','0','0'])[pos]
                print(f"     Position {pos+1}: {val} -> {desc}")

        print("\n💰 Complete Currency Values:")
        for code, name in CURRENCY_NAMES.items():
            print(f"   {name}: {self.get_full_currency_value(code)}")

        if self.state.get('last_updated'):
            print(f"\n🕒 Last Updated: {self.state['last_updated']}")

    def reset_all_modules(self):
        print("\n🔄 Resetting all modules...")
        success_count = 0

        # Reset all main modules
        for code in ALL_CURRENCIES:
            if self.send_command(f"{code}0000"):
                self.state['main_modules'][code] = '0000'
                success_count += 1

        # Reset all overflow modules dynamically
        for m in OVERFLOW_MODULE_NAMES:
            if self.send_command(f"{m}0000"):
                self.state[f"{m.lower()}_module"] = ['0','0','0','0']
                success_count += 1

        expected = len(ALL_CURRENCIES) + len(OVERFLOW_MODULE_NAMES)
        if success_count == expected:
            print(f"✅ All modules reset successfully")
            self.save_state()
            return True
        else:
            print(f"⚠️  Some modules failed to reset ({success_count}/{expected} successful)")
            return False

    def close_connection(self):
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
        print("\n🚀 === Forex Rate Controller (5 Currencies + 2 Overflow Modules E & G) ===")
        print("📋 Commands:")
        print("   - Set rate(s): A123, B4567, C98765, F12345 (comma-separated)")
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
                    print(f"❌ Invalid format for '{entry}'. Use: <A-D,F><3-5 digits>")
                    results.append({'entry': entry, 'success': False, 'error': 'Invalid format'})
                    all_success = False
                    continue

                currency_code = entry[0]
                rate_digits = entry[1:]

                if currency_code not in ['A', 'B', 'C', 'D', 'F']:
                    print(f"❌ Invalid currency code in '{entry}'. Use A, B, C, D or F")
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

import socket, json, os
from datetime import datetime

DEVICE_IP = '192.168.1.101'
DEVICE_PORT = 20108

CURRENCY_NAMES = {
    "A": "USD_TTB", "B": "GBP_TTB", "C": "EUR_TTB", "D": "JPY_TTB", "E": "CAN_TTB",
    "F": "USD_TTS", "G": "GBP_TTS", "H": "EUR_TTS", "I": "JPY_TTS", "J": "CAN_TTS",
    "K": "USD_BLB", "L": "GBP_BLB", "M": "EUR_BLB", "N": "JPY_BLB", "O": "CAN_BLB",
    "P": "USD_BLS", "Q": "GBP_BLS", "R": "EUR_BLS", "S": "JPY_BLS", "T": "CAN_BLS",
    "U": "USD_FCB", "V": "GBP_FCB", "W": "EUR_FCB", "X": "JPY_FCB", "Y": "CAN_FCB",
    "Z": "USD_FCS", "a": "GBP_FCS", "b": "EUR_FCS", "c": "JPY_FCS", "d": "CAN_FCS"
}

OVERFLOW_POSITIONS = {
    'A': ('ZZ', 3), 'B': ('ZZ', 2), 'C': ('ZZ', 1), 'D': ('ZZ', 0), 'E': ('YY', 3),
    'F': ('YY', 2), 'G': ('YY', 1), 'H': ('YY', 0), 'I': ('XX', 3), 'J': ('XX', 2),
    'K': ('XX', 1), 'L': ('XX', 0), 'M': ('WW', 3), 'N': ('WW', 2), 'O': ('WW', 1),
    'P': ('WW', 0), 'Q': ('VV', 3), 'R': ('VV', 2), 'S': ('VV', 1), 'T': ('VV', 0),
    'U': ('UU', 3), 'V': ('UU', 2), 'W': ('UU', 1), 'X': ('UU', 0), 'Y': ('TT', 3),
    'Z': ('TT', 2), 'a': ('TT', 1), 'b': ('TT', 0), 'c': ('SS', 3), 'd': ('SS', 2)
}

RATE_TYPES = ['TTB', 'TTS', 'BLB', 'BLS', 'FCB', 'FCS']
BASE_CURRENCIES = ['USD', 'GBP', 'EUR', 'JPY', 'CAN']
OVERFLOW_MODULES = ['ZZ', 'YY', 'XX', 'WW', 'VV', 'UU', 'TT', 'SS']

class ForexController:
    def __init__(self, state_file='forex_state_expanded.json'):
        self.client_socket = None
        self.state_file = state_file
        
        self.state = {
            'main_modules': {},
            'overflow_modules': {},
            'last_updated': None
        }
        
        for module_code in CURRENCY_NAMES.keys():
            self.state['main_modules'][module_code] = '0000'
        
        for module_name in OVERFLOW_MODULES:
            self.state['overflow_modules'][module_name] = ['0', '0', '0', '0']
        
        self.load_state()

    def load_state(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    saved_state = json.load(f)
                    
                    if 'main_modules' in saved_state:
                        for module_code in CURRENCY_NAMES.keys():
                            if module_code in saved_state['main_modules']:
                                self.state['main_modules'][module_code] = saved_state['main_modules'][module_code]
                    
                    if 'overflow_modules' in saved_state:
                        for module_name in OVERFLOW_MODULES:
                            if module_name in saved_state['overflow_modules']:
                                self.state['overflow_modules'][module_name] = saved_state['overflow_modules'][module_name]
                    
                    if 'last_updated' in saved_state:
                        self.state['last_updated'] = saved_state['last_updated']
                    
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

    def connect_to_device(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # self.client_socket.connect((DEVICE_IP, DEVICE_PORT))
            print(f"🔗 Connected to {DEVICE_IP}:{DEVICE_PORT}")
            return True
        except socket.error as e:
            print(f"❌ Failed to connect to the device: {e}")
            return False

    def send_command(self, command):
        try:
            # self.client_socket.sendall(command.encode())
            print(f"📤 Sent: {command}")
            return True
        except socket.error as e:
            print(f"❌ Socket error while sending command: {e}")
            return False

    def update_overflow_module(self, currency_code, fifth_digit):
        module_name, position = OVERFLOW_POSITIONS[currency_code]
        
        self.state['overflow_modules'][module_name][position] = str(fifth_digit)
        
        module_value = ''.join(self.state['overflow_modules'][module_name])
        
        success = self.send_command(f"{module_name}{module_value}")
        
        if success:
            print(f"✅ Updated {module_name} module to: {module_value}")
            print(f"   Position {position + 1} set to {fifth_digit} for {CURRENCY_NAMES[currency_code]}")
            return True
        else:
            print(f"❌ Failed to update {module_name} module, rolling back state")
            return False

    def set_currency_rate(self, currency_code, rate_value):
        currency_name = CURRENCY_NAMES[currency_code]
        print(f"\n🔄 Setting {currency_name} rate to {rate_value}")
        
        success = False
        
        if len(rate_value) == 4:
            print(f"   📊 4-digit rate: Main={rate_value}, Overflow=0")
            
            main_success = self.send_command(f"{currency_code}{rate_value}")
            overflow_success = self.update_overflow_module(currency_code, 0)

            if main_success and overflow_success:
                self.state['main_modules'][currency_code] = rate_value
                print(f"✅ Successfully set {currency_name} to {rate_value}")
                success = True
                
        elif len(rate_value) == 5:
            main_digits = rate_value[:4]
            fifth_digit = rate_value[4]
            
            print(f"   📊 5-digit rate: Main={main_digits}, Overflow={fifth_digit}")
            
            main_success = self.send_command(f"{currency_code}{main_digits}")
            overflow_success = self.update_overflow_module(currency_code, fifth_digit)

            if main_success and overflow_success:
                self.state['main_modules'][currency_code] = main_digits
                print(f"✅ Successfully set {currency_name} to {rate_value}")
                print(f"   Main module: {main_digits}, Overflow digit: {fifth_digit}")
                success = True
        else:
            print(f"❌ Invalid rate length. Must be 4 or 5 digits, got {len(rate_value)}")
            return False
        
        if success:
            self.save_state()
            return True
        else:
            print(f"❌ Failed to set {currency_name} rate")
            return False

    def get_full_currency_value(self, currency_code):
        main_value = self.state['main_modules'][currency_code]
        module_name, position = OVERFLOW_POSITIONS[currency_code]
        overflow_digit = self.state['overflow_modules'][module_name][position]
        
        if overflow_digit == '0':
            return main_value
        else:
            return main_value + overflow_digit

    def display_current_state(self):
        print(f"\n📊 === Current System State (30 Currency Rates) ===")
        
        for base_currency in BASE_CURRENCIES:
            print(f"\n💰 {base_currency} Rates:")
            for rate_type in RATE_TYPES:
                target_name = f"{base_currency}_{rate_type}"
                module_code = None
                for code, name in CURRENCY_NAMES.items():
                    if name == target_name:
                        module_code = code
                        break
                
                if module_code:
                    full_value = self.get_full_currency_value(module_code)
                    print(f"   {rate_type}: {full_value} (Module {module_code})")
        
        print(f"\n🔧 Overflow Module States:")
        for module_name in OVERFLOW_MODULES:
            module_value = ''.join(self.state['overflow_modules'][module_name])
            print(f"   {module_name}: {module_value}")
        
        if self.state['last_updated']:
            print(f"\n🕒 Last Updated: {self.state['last_updated']}")

    def display_rate_type_summary(self, rate_type):
        print(f"\n📈 {rate_type} Rates Across All Currencies:")
        for base_currency in BASE_CURRENCIES:
            target_name = f"{base_currency}_{rate_type}"
            module_code = None
            for code, name in CURRENCY_NAMES.items():
                if name == target_name:
                    module_code = code
                    break
            
            if module_code:
                full_value = self.get_full_currency_value(module_code)
                print(f"   {base_currency}: {full_value}")

    def reset_all_modules(self):
        print(f"\n🔄 Resetting all 30 main modules and 8 overflow modules...")
        
        success_count = 0
        total_modules = len(CURRENCY_NAMES) + len(OVERFLOW_MODULES)
        
        for code in CURRENCY_NAMES.keys():
            if self.send_command(f"{code}0000"):
                self.state['main_modules'][code] = '0000'
                success_count += 1
        
        for module_name in OVERFLOW_MODULES:
            if self.send_command(f"{module_name}0000"):
                self.state['overflow_modules'][module_name] = ['0', '0', '0', '0']
                success_count += 1

        if success_count == total_modules:
            print(f"✅ All {total_modules} modules reset successfully")
            self.save_state()
            return True
        else:
            print(f"⚠️  Some modules failed to reset ({success_count}/{total_modules} successful)")
            return False

    def close_connection(self):
        if self.client_socket:
            self.client_socket.close()
            print("🔌 Connection closed.")


def main():
    controller = ForexController()
    
    if not controller.connect_to_device():
        return
    
    try:
        print("\n🚀 === Enhanced Forex Rate Controller (30 Currency Rates) ===")
        print("📋 Commands:")
        print("   - Set rate: A1234, F23456, K34567, etc. (Module + 4-5 digits)")
        print("   - 'status' - Show current state")
        print("   - 'summary <RATE_TYPE>' - Show all currencies for rate type (TTB, TTS, BLB, BLS, FCB, FCS)")
        print("   - 'reset' - Reset all modules to 0000")
        print("   - 'help' - Show module mapping")
        print("   - 'exit' - Quit program")
        
        while True:
            user_input = input("\n💬 Enter command: ").strip()
            
            if user_input.upper() == 'EXIT':
                print("👋 Exiting...")
                break
                
            if user_input.upper() == 'STATUS':
                controller.display_current_state()
                continue
                
            if user_input.upper().startswith('SUMMARY '):
                rate_type = user_input[8:].upper()
                if rate_type in RATE_TYPES:
                    controller.display_rate_type_summary(rate_type)
                else:
                    print(f"❌ Invalid rate type. Use: {', '.join(RATE_TYPES)}")
                continue
                
            if user_input.upper() == 'RESET':
                confirm = input("⚠️  Reset all modules to 0000? (y/N): ").strip().lower()
                if confirm == 'y':
                    controller.reset_all_modules()
                else:
                    print("❌ Reset cancelled")
                continue
                
            if user_input.upper() == 'HELP':
                print("\n📖 Module Mapping:")
                for code, name in CURRENCY_NAMES.items():
                    print(f"   {code}: {name}")
                continue
            
            if len(user_input) < 2:
                print("❌ Invalid format. Use: <Module><4-5 digits> (e.g., A1234 or F12345)")
                continue
                
            currency_code = user_input[0]
            rate_digits = user_input[1:]
            
            if currency_code not in CURRENCY_NAMES:
                print(f"❌ Invalid module code. Use one of: {', '.join(CURRENCY_NAMES.keys())}")
                continue
                
            if not rate_digits.isdigit():
                print("❌ Rate must contain only digits")
                continue
                
            if len(rate_digits) not in [4, 5]:
                print("❌ Rate must be 4 or 5 digits")
                continue
            
            controller.set_currency_rate(currency_code, rate_digits)
            
    except KeyboardInterrupt:
        print("\n\n⚡ Interrupted by user")
    finally:
        controller.close_connection()

if __name__ == "__main__":
    main()
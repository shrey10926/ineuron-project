import json, os, socket, sys
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QLineEdit, QLabel, 
                             QPushButton, QMessageBox, QStatusBar, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPalette

# Constants from original code
DEVICE_IP = '192.168.1.101'
DEVICE_PORT = 20108

CURRENCY_NAMES = {
    "A": "USD_TTB", "B": "GBP_TTB", "C": "EUR_TTB", "D": "JPY_TTB", "E": "CAD_TTB",
    "F": "USD_TTS", "G": "GBP_TTS", "H": "EUR_TTS", "I": "JPY_TTS", "J": "CAD_TTS",
    "K": "USD_BLB", "L": "GBP_BLB", "M": "EUR_BLB", "N": "JPY_BLB", "O": "CAD_BLB",
    "P": "USD_BLS", "Q": "GBP_BLS", "R": "EUR_BLS", "S": "JPY_BLS", "T": "CAD_BLS",
    "U": "USD_FCB", "V": "GBP_FCB", "W": "EUR_FCB", "X": "JPY_FCB", "Y": "CAD_FCB",
    "Z": "USD_FCS", "a": "GBP_FCS", "b": "EUR_FCS", "c": "JPY_FCS", "d": "CAD_FCS"
}

OVERFLOW_POSITIONS = {
    'A': ('ZZ', 3), 'B': ('ZZ', 2), 'C': ('ZZ', 1), 'D': ('ZZ', 0), 'E': ('YY', 3),
    'F': ('YY', 2), 'G': ('YY', 1), 'H': ('YY', 0), 'I': ('XX', 3), 'J': ('XX', 2),
    'K': ('XX', 1), 'L': ('XX', 0), 'M': ('WW', 3), 'N': ('WW', 2), 'O': ('WW', 1),
    'P': ('WW', 0), 'Q': ('VV', 3), 'R': ('VV', 2), 'S': ('VV', 1), 'T': ('VV', 0),
    'U': ('UU', 3), 'V': ('UU', 2), 'W': ('UU', 1), 'X': ('UU', 0), 'Y': ('TT', 3),
    'Z': ('TT', 2), 'a': ('TT', 1), 'b': ('TT', 0), 'c': ('SS', 3), 'd': ('SS', 2)
}

OVERFLOW_MODULES = ['ZZ', 'YY', 'XX', 'WW', 'VV', 'UU', 'TT', 'SS']
BASE_CURRENCIES = ['USD', 'GBP', 'EUR', 'JPY', 'CAD']
RATE_TYPES = ['TTB', 'TTS', 'BLB', 'BLS', 'FCB', 'FCS']

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
        except Exception as e:
            pass

    def save_state(self):
        try:
            self.state['last_updated'] = datetime.now().isoformat()
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            return True
        except Exception as e:
            return False

    def connect_to_device(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # self.client_socket.connect((DEVICE_IP, DEVICE_PORT))
            return True
        except socket.error as e:
            return False

    def send_command(self, command):
        try:
            # self.client_socket.sendall(command.encode())
            print(f'Send command -> {command}')
            return True
        except socket.error as e:
            return False

    def update_overflow_module(self, currency_code, fifth_digit):
        module_name, position = OVERFLOW_POSITIONS[currency_code]
        self.state['overflow_modules'][module_name][position] = str(fifth_digit)
        module_value = ''.join(self.state['overflow_modules'][module_name])
        return self.send_command(f"{module_name}{module_value}")

    def set_currency_rate(self, currency_code, rate_value):
        if not (3 <= len(rate_value) <=5):
            return False
        
        padded_rate = rate_value.zfill(5)

        main_digits = padded_rate[:4]
        fifth_digit = padded_rate[4]

        main_success = self.send_command(f"{currency_code}{main_digits}")

        overflow_success = self.update_overflow_module(currency_code, fifth_digit)

        if main_success and overflow_success:
            self.state['main_modules'][currency_code] = main_digits
            return True
        
        return False

    def get_full_currency_value(self, currency_code):
        main_value = self.state['main_modules'][currency_code]
        module_name, position = OVERFLOW_POSITIONS[currency_code]
        overflow_digit = self.state['overflow_modules'][module_name][position]

        return main_value + overflow_digit

    def close_connection(self):
        if self.client_socket:
            self.client_socket.close()

class ForexGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = ForexController()
        self.rate_inputs = {}
        self.is_connected = False
        self.init_ui()
        self.load_current_rates()
        
    def init_ui(self):
        self.setWindowTitle("Forex Rate Controller")
        self.setGeometry(100, 100, 900, 700)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # Title
        title = QLabel("Forex Rate Controller")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setStyleSheet("color: #2c3e50; margin: 10px;")
        main_layout.addWidget(title)
        
        # Connection status
        self.connection_status = QLabel("Status: Disconnected")
        self.connection_status.setAlignment(Qt.AlignCenter)
        self.connection_status.setStyleSheet("color: red; font-weight: bold; margin: 5px;")
        main_layout.addWidget(self.connection_status)
        
        # Matrix container
        matrix_frame = QFrame()
        matrix_frame.setFrameStyle(QFrame.Box)
        matrix_frame.setStyleSheet("QFrame { border: 2px solid #34495e; border-radius: 10px; margin: 10px; }")
        matrix_layout = QVBoxLayout(matrix_frame)
        
        # Matrix grid
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(5)
        
        # Empty top-left cell
        empty_cell = QLabel("")
        grid_layout.addWidget(empty_cell, 0, 0)
        
        # Column headers (Rate Types)
        for col, rate_type in enumerate(RATE_TYPES):
            header = QLabel(rate_type)
            header.setAlignment(Qt.AlignCenter)
            header.setFont(QFont("Arial", 11, QFont.Bold))
            header.setStyleSheet("background-color: #3498db; color: white; padding: 8px; border-radius: 5px;")
            grid_layout.addWidget(header, 0, col + 1)
        
        # Row headers (Currencies) and input boxes
        for row, currency in enumerate(BASE_CURRENCIES):
            # Row header
            header = QLabel(currency)
            header.setAlignment(Qt.AlignCenter)
            header.setFont(QFont("Arial", 11, QFont.Bold))
            header.setStyleSheet("background-color: #2ecc71; color: white; padding: 8px; border-radius: 5px;")
            grid_layout.addWidget(header, row + 1, 0)
            
            # Input boxes for each rate type
            for col, rate_type in enumerate(RATE_TYPES):
                input_box = QLineEdit()
                input_box.setMaxLength(5)
                input_box.setPlaceholderText("0000")
                input_box.setAlignment(Qt.AlignCenter)
                input_box.setFont(QFont("Arial", 10))
                input_box.setStyleSheet("""
                    QLineEdit {
                        padding: 8px;
                        border: 2px solid #bdc3c7;
                        border-radius: 5px;
                        background-color: white;
                    }
                    QLineEdit:focus {
                        border-color: #3498db;
                    }
                """)
                
                # Store reference
                key = f"{currency}_{rate_type}"
                self.rate_inputs[key] = input_box
                
                grid_layout.addWidget(input_box, row + 1, col + 1)
        
        matrix_layout.addWidget(grid_widget)
        main_layout.addWidget(matrix_frame)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.connect_btn = QPushButton("Connect to Device")
        self.connect_btn.setFont(QFont("Arial", 10, QFont.Bold))
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.connect_btn.clicked.connect(self.connect_device)
        button_layout.addWidget(self.connect_btn)
        
        self.submit_btn = QPushButton("Submit")
        self.submit_btn.setFont(QFont("Arial", 10, QFont.Bold))
        self.submit_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #5dade2;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.submit_btn.clicked.connect(self.submit_rates)
        self.submit_btn.setEnabled(False)
        button_layout.addWidget(self.submit_btn)
        
        self.clear_btn = QPushButton("Clear All Fields")
        self.clear_btn.setFont(QFont("Arial", 10, QFont.Bold))
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_all_fields)
        button_layout.addWidget(self.clear_btn)
        
        main_layout.addLayout(button_layout)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Load previous rates and connect to device")

    def load_current_rates(self):
        # Load current rates from controller state into input boxes
        for key, input_box in self.rate_inputs.items():
            currency, rate_type = key.split('_')
            target_name = f"{currency}_{rate_type}"

            # Find module code for this currency-rate combination
            module_code = None
            for code, name in CURRENCY_NAMES.items():
                if name == target_name:
                    module_code = code
                    break
            
            if module_code:
                full_value = self.controller.get_full_currency_value(module_code)
                input_box.setText(full_value)
        
        # Update status with last updated time
        if self.controller.state['last_updated']:
            self.status_bar.showMessage(f"Rates loaded - Last updated: {self.controller.state['last_updated'][:19]}")
    
    def connect_device(self):
        if self.controller.connect_to_device():
            self.is_connected = True
            self.connection_status.setText("Status: Connected")
            self.connection_status.setStyleSheet("color: green; font-weight: bold; margin: 5px;")
            self.connect_btn.setText("Connected")
            self.connect_btn.setEnabled(False)
            self.submit_btn.setEnabled(True)
            self.status_bar.showMessage("Connected to device successfully")
        else:
            QMessageBox.critical(self, "Connection Error", 
                               f"Failed to connect to device at {DEVICE_IP}:{DEVICE_PORT}")
            self.status_bar.showMessage("Connection failed")
    
    def submit_rates(self):
        if not self.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to device first")
            return
        
        # Find all input boxes that have values (regardless of selection)
        fields_to_process = []
        for key, input_box in self.rate_inputs.items():
            rate_value = input_box.text().strip()
            if rate_value:  # If field has any value
                fields_to_process.append((key, input_box, rate_value))
        
        if not fields_to_process:
            QMessageBox.warning(self, "No Data", "Please enter values in one or more rate fields")
            return
        
        success_count = 0
        total_count = len(fields_to_process)
        failed_rates = []
        
        for key, input_box, rate_value in fields_to_process:
            if not rate_value.isdigit() or len(rate_value) not in [3, 4, 5]:
                failed_rates.append(f"{key}: Invalid format (3-5 digits required)")
                continue
            
            currency, rate_type = key.split('_')
            target_name = f"{currency}_{rate_type}"
            
            # Find module code
            module_code = None
            for code, name in CURRENCY_NAMES.items():
                if name == target_name:
                    module_code = code
                    break
            
            if module_code:
                if self.controller.set_currency_rate(module_code, rate_value):
                    success_count += 1
                    # Visual feedback - green border for success
                    input_box.setStyleSheet("""
                        QLineEdit {
                            padding: 8px;
                            border: 2px solid #27ae60;
                            border-radius: 5px;
                            background-color: white;
                        }
                        QLineEdit:focus {
                            border-color: #27ae60;
                        }
                    """)
                else:
                    failed_rates.append(f"{key}: Update failed")
                    # Visual feedback - red background for failure
                    input_box.setStyleSheet("""
                        QLineEdit {
                            padding: 8px;
                            border: 2px solid #e74c3c;
                            border-radius: 5px;
                            background-color: #ffebee;
                        }
                        QLineEdit:focus {
                            border-color: #e74c3c;
                        }
                    """)
        
        # Save state after successful updates
        if success_count > 0:
            self.controller.save_state()
        
        # Show results
        if success_count == total_count:
            QMessageBox.information(self, "Success", f"All {total_count} rates updated successfully!")
            self.status_bar.showMessage(f"Successfully updated {success_count} rates")
        else:
            failed_text = "\n".join(failed_rates) if failed_rates else "Unknown errors"
            QMessageBox.warning(self, "Partial Success", 
                              f"Updated {success_count}/{total_count} rates.\n\nFailed:\n{failed_text}")
            self.status_bar.showMessage(f"Updated {success_count}/{total_count} rates")
    
    def clear_all_fields(self):
        """Clear all input fields and reset their styling"""
        for input_box in self.rate_inputs.values():
            input_box.clear()
            input_box.setStyleSheet("""
                QLineEdit {
                    padding: 8px;
                    border: 2px solid #bdc3c7;
                    border-radius: 5px;
                    background-color: white;
                }
                QLineEdit:focus {
                    border-color: #3498db;
                }
            """)
        
        self.status_bar.showMessage("All fields cleared")
    
    def closeEvent(self, event):
        # Clean up connection when closing
        self.controller.close_connection()
        event.accept()

def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = ForexGUI()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

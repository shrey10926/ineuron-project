import tkinter as tk
from tkinter import messagebox
import socket
import threading

# Device configuration
DEVICE_IP = '192.168.1.71'  # Replace with your device's IP
DEVICE_PORT = 20108          # Replace with the correct port

# Mapping input fields to protocol prefixes
FIELD_MAPPING = {
    "SDC": "C",
    "SB": "D",
    "CONE/SHL/DENT": "E",
    "BJM": "F",
    "BS/TM": "G",
    "BLR/SP/SFL/HP/PFL/DP": "H",
    "NC": "I",
    "DD/BL": "J",
    "PUGS": "K",
    "TOTAL": "L"
}

# Store last sent values to track changes
last_sent_values = {field: "" for field in FIELD_MAPPING}

def send_to_device(command):
    """Sends the formatted command to the LAN device using a persistent connection."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((DEVICE_IP, DEVICE_PORT))
            client_socket.sendall(command.encode())
            response = client_socket.recv(1024).decode()
        return response
    except socket.error as e:
        return f"Connection Error: {e}"

def process_submission():
    """Handles submission asynchronously to avoid UI freezing."""
    updated_fields = {}
    for field, prefix in FIELD_MAPPING.items():
        value = entries[field].get().strip()
        if value and (value != last_sent_values[field]):  # Process only updated fields
            if not value.isdigit() or len(value) != 4:
                messagebox.showerror("Input Error", f"{field} must be a 4-digit number!")
                return
            updated_fields[field] = f"{prefix}{value}"
            last_sent_values[field] = value  # Update last sent value

    if not updated_fields:
        messagebox.showinfo("Info", "No new data to send.")
        return
    
    responses = {}
    for field, command in updated_fields.items():
        responses[field] = send_to_device(command)
    
    # Show responses in a consolidated message
    response_text = "\n".join([f"{field}: Sent {cmd}, Received: {resp}" for field, (cmd, resp) in zip(updated_fields.keys(), responses.items())])
    messagebox.showinfo("Response", response_text)
    
    # Clear only submitted fields
    for field in updated_fields:
        entries[field].delete(0, tk.END)

def submit():
    """Starts the submission process in a separate thread."""
    threading.Thread(target=process_submission, daemon=True).start()

# GUI Setup
root = tk.Tk()
root.title("LAN Device Controller")
root.geometry("400x400")
root.configure(bg='darkblue')

tk.Label(root, text="Modern Insulators Ltd.", font=("Arial", 16, "bold"), fg="white", bg="darkblue").pack(pady=10)

tk.Label(root, text="SHAPING DEFECTS", font=("Arial", 12), fg="white", bg="darkblue").pack()

entries = {}
for field in FIELD_MAPPING.keys():
    frame = tk.Frame(root, bg='darkblue')
    frame.pack(pady=5)
    tk.Label(frame, text=field, font=("Arial", 12, "bold"), fg="white", bg="darkblue").pack(side=tk.LEFT, padx=10)
    entry = tk.Entry(frame, font=("Arial", 12), width=6)
    entry.pack(side=tk.RIGHT)
    entries[field] = entry

tk.Button(root, text="Submit", font=("Arial", 12, "bold"), command=submit, bg="red", fg="white").pack(pady=20)

root.mainloop()

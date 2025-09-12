import socket

# Device configuration
DEVICE_IP = '192.168.1.101'  # Replace with your device's IP
DEVICE_PORT = 20108          # Replace with the correct port


def connect_to_device():
    """
    Connects to the ROI device.
    :return: The socket object if successful, None otherwise
    """
    try:
        # Create a TCP socket
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((DEVICE_IP, DEVICE_PORT))
        print(f"Connected to {DEVICE_IP}:{DEVICE_PORT}")
        return client_socket
    except socket.error as e:
        print(f"Failed to connect to the device: {e}")
        return None



def send_to_device(client_socket, line, data):
    """
    Sends a command to the ROI device to update a specific line with the given data.
    :param client_socket: The connected socket object
    :param line: The line identifier (A, B, C, D, or E)
    :param data: The 4-digit data to display on the line
    :return: True if successful, False otherwise
    """
    try:
        # Format the command (e.g., "A1234")
        command = f"{line}{data}"
        client_socket.sendall(command.encode())
        print(f"Sent: {command}")

        # Wait for a response (if the device sends one)
        response = client_socket.recv(1024)
        if response:
            print(f"Received: {response.decode()}")
        return True
    except socket.error as e:
        print(f"Socket error while sending data: {e}")
        return False


def main():
    # Connect to the device
    client_socket = connect_to_device()
    if not client_socket:
        return  # Exit if connection fails

    try:
        while True:
            # Get user input
            user_input = input("Enter command (e.g., 'A1234' or 'exit' to quit): ").strip().upper()

            if user_input == 'EXIT':
                print("Exiting...")
                break

            # Validate input
            if len(user_input) != 5 or user_input[0] not in ['A', 'B', 'C', 'D', 'E'] or not user_input[1:].isdigit():
                print("Invalid command. Format: <A-E><4 digits> (e.g., A1234)")
                continue

            # Extract line and data
            line = user_input[0]
            data = user_input[1:]

            # Send command to the device
            if send_to_device(client_socket, line, data):
                print(f"Successfully updated line {line} with {data}")
            else:
                print("Failed to update the device.")
    finally:
        # Close the socket when done
        client_socket.close()
        print("Connection closed.")

if __name__ == "__main__":
    main()
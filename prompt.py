I want to communicate with a Foreign Exchange (Forex) device via LAN using python. The Forex device displays the current price for various currencies. It has various currencies and their rates such as USD, GBP, EUR etc. I am using TCP as the protocol. I have the IP and the PORT for the device. I also have the communication protocol for sending data to the device. It is as follows:
1.) For Setting price for USD : "A8994"
2.) For Setting price for GBP : "B1234"
3.) For Setting price for EUR : "C9876"
4.) For Setting price for CAN : "D5678"

If we send the string "A8998", then the USD rate will be updated to 8998. Similarly if we want to update the price for GBP we should send "B1234" and the proce of GBP will be updated to 1234. So basically to communicate with the USD box we need to send "A" followed by 4 digits. Similarly for GBP, "B" followed by 4 digits and so on.

Below is the python code I am using to communicate with the Forex board:



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
            if len(user_input) != 5 or user_input[0] not in ['A', 'B', 'C', 'D'] or not user_input[1:].isdigit():
                print("Invalid command. Format: <A-D><4 digits> (e.g., A1234)")
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

Let me know if you understood and I'll proceed with my query.



Excellent! Now the issue is that the client is asking for 5 digits instead of the current 4 digit support. If the currency rate goes above 4 digits then a fifth digit needs to be added.

The issue is the LED modules that are being used in the Forex device have only 4 digits. How can I then add a fifth digit? I have multiple 4 digit LED modules that I can use.

I want to adopt the following approach (Recommended and Client Approved):
The current setup allows 4 digits per currency. I have some extra 4 digit LED modules (let's call them overflow modules the protocol for which is `Z`) that I can use but I do not want to use one WHOLE OVERFLOW LED MODULE for EACH currency. What I can do is that I can allot ONE DIGIT from the 4 DIGIT OVERFLOW MODULE for each currency. That way I can use A SINGLE 4 DIGIT OVERFLOW LED module for 4 DIFFERENT CURRENCIES and hence reduce the cost. So for USD (i.e. communication protocol `A`) I will allot the 4th digit of the overflow module. For GBP (i.e. communication protocol `B`) I will allot the 3rd digit of the overflow module. For EUR (i.e. communication protocol `C`) I will allot the 2nd digit of the overflow module and for CAD (i.e. communication protocol `D`) the 1st digit of the overflow module. The `Z` module will accept only 4 digits as usual but we are alloting each individual digit to all currencies.

For example:
Let's say currently I have 4 currencies (and hence 4 main LED modules i.e. `A for USD, `B` for GBP, `C` for EUR and `D` for CAN) in the device. Now if I want to add one more digit for all 4 currencies then I will use one overflow LED module (i.e. `Z`, containing 4 digits).

Here is how an example flow/logic goes.
Initially all modules i.e. main modules (`A`, `B`, `C`, `D`) and overflow modules (`Z`) will be empty.

1.) User input for USD is 12345.
    `A` will be set to 1234. Since the user input length is 5 digits, we need to update `Z`. The 4th digit of `Z` is alloted to 5th digit of `A`. Before updating `Z`, we need to first check the current value in it. If it contains any data in the 1st, 2nd or the 3rd digits then it needs to be preserved as is. So it will not change the values in the 1st, 2nd and 3rd digits and only the value in the 4th digit (as the 4th digit of `Z` is alloted to 5th digit of `A`) will be set. So `Z` will be xxx5 (where x represents any previous value). Therefore `A`=1234, `B`=xxxx, `C`=xxxx, `D`=xxxx and `Z`=xxx5.
2.) Set GBP=2345.
    `B` is set to 2345. Now since the user input length is 4 digits no need to update the overflow module i.e. `Z`. Check the current value of `Z`. From 1.) it is set to xxx5. Hence `Z` will be xx05 (where x represents any previous value). Therefore `A`=1234, `B`=2345, `C`=xxxx, `D`=xxxx and `Z`=xx05.
3.) Set EUR=34567.
    `C` is set to 3456. Now since the user input digit length is 5 digits, we need to update `Z`. The 2nd digit of `Z` is alloted to the 5th digit of `C`. First check the current value of `Z` from 2.). It is set to xx05. We only need to set the 2nd digit of Z and keep others unchanged. Hence `Z` will be x705 (where x represents any previous value). Therefore `A`=1234, `B`=2345, `C`=3456, `D`=xxxx and `Z`=x705.
4.) Set CAN=4567.
    `D` is set to 4567. Now since the user input length is 4 digits no need to update the overflow module i.e. `Z`. First check the current value of `Z` from 3.). It is set to x705. Hence `Z` will be 0705 (where x represents any previous value). Therefore `A`=1234, `B`=2345, `C`=3456, `D`=4567 and `Z`=0705.

At the end of the flow, these are the values:
`A`=1234, `B`=2345, `C`=3456, `D`=4567 and `Z`=0705.

In essence if the user input is 4 digit in lengh then only update the main modules i.e. A, B, C, D and set the corresponding `Z` digit to 0. But if the user input is 5 digits in length then update both the main modules as well as the overflow modules accordingly.
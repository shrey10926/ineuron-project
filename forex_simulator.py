"""
Forex LED Board Simulator
- Listens on a TCP port and accepts simple commands:
  Axxxx / Bxxxx / Cxxxx / Dxxxx  -> update main modules
  Zxxxx                          -> update overflow (Z) module (4 chars)
- Replies with "ACK\n" on success or "NACK\n" on failure (simulated).
- Modes:
    none         -> always ACK
    random_nack  -> randomly reply NACK with given rate
    drop_conn    -> randomly close connection after receiving command (simulate connection drop)
    delayed_ack  -> delay before ACK (simulate slow device)
"""
import argparse
import socket
import threading
import time
import random
import sys

HOST = "0.0.0.0"

class ForexSimulator:
    def __init__(self, port=20108, mode='none', rate=0.1, delay=1.0):
        self.port = port
        self.mode = mode
        self.rate = float(rate)
        self.delay = float(delay)

        # device state
        self.main_modules = {'A': '0000', 'B': '0000', 'C': '0000', 'D': '0000'}
        self.z_module = ['0', '0', '0', '0']  # positions [CAN, EUR, GBP, USD]

        self._shutdown = threading.Event()

    def start(self):
        print(f"[sim] Starting Forex simulator on port {self.port} (mode={self.mode}, rate={self.rate}, delay={self.delay})")
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, self.port))
        srv.listen(5)
        try:
            while not self._shutdown.is_set():
                try:
                    client_sock, addr = srv.accept()
                except OSError:
                    break
                print(f"[sim] Accepted connection from {addr}")
                t = threading.Thread(target=self._handle_client, args=(client_sock, addr), daemon=True)
                t.start()
        finally:
            srv.close()
            print("[sim] Server stopped")

    def _handle_client(self, sock, addr):
        with sock:
            sock.settimeout(2.0)
            while True:
                try:
                    data = sock.recv(1024)
                except socket.timeout:
                    continue
                except ConnectionResetError:
                    print(f"[sim] Connection reset by {addr}")
                    break

                if not data:
                    print(f"[sim] Client {addr} closed connection")
                    break

                try:
                    text = data.decode(errors='ignore').strip()
                except Exception:
                    text = ''
                if not text:
                    continue

                # Trim newline/CR if present
                text = text.replace('\r','').replace('\n','')
                print(f"[sim] Received: '{text}' from {addr}")

                # Basic validation: expect commands like A1234 or Z0123
                cmd = text.upper()
                # Simulator: allow multiple commands in a single recv – split by whitespace
                parts = cmd.split()
                for part in parts:
                    if not part:
                        continue
                    response, drop = self._process_command(part)
                    try:
                        if response is not None:
                            sock.sendall((response + '\n').encode())
                            print(f"[sim] Sent response: {response}")
                    except BrokenPipeError:
                        print(f"[sim] BrokenPipe when sending to {addr}")
                        drop = True

                    if drop:
                        print(f"[sim] Simulating connection drop for {addr}")
                        try:
                            sock.shutdown(socket.SHUT_RDWR)
                        except Exception:
                            pass
                        sock.close()
                        return

    def _process_command(self, cmd):
        """
        Process single command string and return (response_str_or_None, drop_connection_bool)
        """
        # simulate behavior based on mode
        drop_conn_now = False

        # Random drop simulation
        if self.mode == 'drop_conn' and random.random() < self.rate:
            # accept the command but immediately drop the connection (no response)
            print("[sim] [mode=drop_conn] dropping connection")
            return (None, True)

        # Random NACK simulation
        if self.mode == 'random_nack' and random.random() < self.rate:
            print("[sim] [mode=random_nack] simulating NACK for command:", cmd)
            return ("NACK", False)

        # Delayed ACK simulation
        if self.mode == 'delayed_ack' and self.delay > 0:
            print(f"[sim] [mode=delayed_ack] sleeping for {self.delay}s before responding")
            time.sleep(self.delay)

        # Process command
        if len(cmd) >= 5 and cmd[0] in ('A','B','C','D') and cmd[1:5].isdigit():
            code = cmd[0]
            digits = cmd[1:5]
            self.main_modules[code] = digits
            print(f"[sim] Updated main {code} -> {digits}")
            self._print_state()
            return ("ACK", False)

        if len(cmd) >= 5 and cmd[0] == 'Z' and cmd[1:5].isdigit():
            zdigits = cmd[1:5]
            # z_module is [CAN, EUR, GBP, USD] mapping order assumed by you
            # Here we just set full Z
            self.z_module = [zdigits[0], zdigits[1], zdigits[2], zdigits[3]]
            print(f"[sim] Updated Z -> {''.join(self.z_module)}")
            self._print_state()
            return ("ACK", False)

        # Unknown command
        print(f"[sim] Unknown or malformed command: '{cmd}'")
        return ("NACK", False)

    def _print_state(self):
        print("[sim] Current device state:")
        print("       Main modules:", self.main_modules)
        print("       Z module    :", ''.join(self.z_module))

def parse_args():
    p = argparse.ArgumentParser(description="Forex Board Simulator (TCP)")
    p.add_argument("--port", type=int, default=20108, help="Port to listen on (default 20108)")
    p.add_argument("--mode", choices=['none','random_nack','drop_conn','delayed_ack'], default='none',
                   help="Failure simulation mode")
    p.add_argument("--rate", type=float, default=0.1, help="Failure rate for random modes (0.0-1.0)")
    p.add_argument("--delay", type=float, default=1.0, help="Delay seconds for delayed_ack mode")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    sim = ForexSimulator(port=args.port, mode=args.mode, rate=args.rate, delay=args.delay)
    try:
        sim.start()
    except KeyboardInterrupt:
        print("\n[sim] Interrupted by user. Shutting down...")
        sys.exit(0)

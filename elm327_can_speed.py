import re
import serial
import serial.tools.list_ports
import threading
import time
import glob
import os
import platform


def find_elm327_port():
    """Auto-detect ELM327 serial port on Windows/Linux/Jetson."""
    ports_to_try = []

    # Try pyserial's port listing first
    try:
        for port_info in serial.tools.list_ports.comports():
            ports_to_try.append(port_info.device)
    except Exception:
        pass

    # On Linux/Jetson, also try common paths
    if platform.system() == "Linux":
        ports_to_try.extend([
            "/dev/ttyUSB0",
            "/dev/ttyUSB1",
            "/dev/ttyACM0",
            "/dev/ttyACM1",
            "/dev/ttyS0",
        ])
        # Also scan /dev/ for any serial devices
        ports_to_try.extend(glob.glob("/dev/ttyUSB*"))
        ports_to_try.extend(glob.glob("/dev/ttyACM*"))

    # Remove duplicates and non-existent ports
    ports_to_try = list(set(ports_to_try))
    ports_to_try = [p for p in ports_to_try if p and (platform.system() == "Windows" or os.path.exists(p))]

    return ports_to_try


class ELM327SpeedReader(threading.Thread):
    def __init__(self, port=None, baudrate=9600, callback=None):
        super().__init__(daemon=True)

        # Auto-detect port if not provided
        if port is None:
            available_ports = find_elm327_port()
            port = available_ports[0] if available_ports else "COM12"
            print(f"[ELM327] Auto-detected port: {port}")

        self.port = port
        self.baudrate = baudrate
        self.callback = callback
        self.running = False
        self.ser = None

    def send(self, cmd, read_timeout=2.0):
        """Send an AT/OBD command and wait for the '>' prompt or timeout."""
        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass

        self.ser.write((cmd + "\r").encode("ascii", errors="ignore"))
        self.ser.flush()

        deadline = time.time() + read_timeout
        raw = b""
        while time.time() < deadline:
            try:
                waiting = self.ser.in_waiting
            except Exception:
                break
            try:
                chunk = self.ser.read(waiting or 1)
            except Exception:
                break
            if chunk:
                raw += chunk
                if b">" in raw:
                    break
            else:
                time.sleep(0.01)

        return raw.decode("ascii", errors="ignore")

    def init_elm(self):
        self.send("ATZ", read_timeout=3.0)
        self.send("ATE0")
        self.send("ATL0")
        self.send("ATS0")
        self.send("ATH0")
        self.send("ATSP0")

    @staticmethod
    def parse_speed(resp):
        """
        Parse speed from PID 010D response.
        Works with both spaced ('41 0D 1E') and compact ('410D1E') formats,
        and even mixed text like 'SEARCHING...410D1E>>'.
        """
        cleaned = resp.upper()
        hex_stream = re.sub(r"[^0-9A-F]", "", cleaned)

        idx = hex_stream.find("410D")
        if idx == -1 or len(hex_stream) < idx + 6:
            return None

        speed_hex = hex_stream[idx + 4: idx + 6]
        try:
            return int(speed_hex, 16)
        except ValueError:
            return None

    def run(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.2,
                write_timeout=0.5,
            )
        except Exception as e:
            print(f"ELM327 serial open error: {e}")
            return

        self.init_elm()

        self.running = True

        while self.running:
            try:
                resp = self.send("010D", read_timeout=1.2)

                if not self.running:
                    break

                speed = self.parse_speed(resp)

                if speed is not None and self.callback is not None:
                    self.callback(speed)

            except Exception as e:
                print(f"ELM327 poll error: {e}")

            # ~100 ms pause between polls
            for _ in range(10):
                if not self.running:
                    break
                time.sleep(0.01)

    def stop(self):

        self.running = False

        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass

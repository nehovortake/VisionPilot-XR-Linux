import re
import serial
import serial.tools.list_ports
import threading
import time
import glob
import os
import platform
from typing import List, Optional, Tuple


COMMON_BAUDRATES = [38400, 9600, 115200, 57600]
COMMON_LINUX_PORTS = [
    "/dev/ttyUSB0",
    "/dev/ttyUSB1",
    "/dev/ttyUSB2",
    "/dev/ttyACM0",
    "/dev/ttyACM1",
    "/dev/ttyACM2",
    "/dev/ttyS0",
]


def find_elm327_ports() -> List[str]:
    """Return candidate serial ports for ELM327 on Windows/Linux/Jetson."""
    ports_to_try = []

    try:
        for port_info in serial.tools.list_ports.comports():
            dev = getattr(port_info, "device", None)
            desc = (getattr(port_info, "description", "") or "").lower()
            hwid = (getattr(port_info, "hwid", "") or "").lower()
            if dev:
                # Prefer typical USB/BT serial dongles.
                score = 0
                if any(k in desc for k in ["elm", "obd", "usb", "serial", "ch340", "cp210", "ftdi"]):
                    score += 2
                if any(k in hwid for k in ["usb", "ftdi", "cp210", "ch340"]):
                    score += 1
                ports_to_try.append((score, dev))
    except Exception:
        pass

    if platform.system() == "Linux":
        for p in COMMON_LINUX_PORTS:
            ports_to_try.append((0, p))
        for p in glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"):
            ports_to_try.append((0, p))

    # Keep existing Windows COM ports too
    dedup = {}
    for score, dev in ports_to_try:
        if not dev:
            continue
        if platform.system() != "Windows" and not os.path.exists(dev):
            continue
        dedup[dev] = max(score, dedup.get(dev, -999))

    return [dev for dev, _score in sorted(dedup.items(), key=lambda kv: (-kv[1], kv[0]))]


class ELM327SpeedReader(threading.Thread):
    def __init__(self, port=None, baudrate=None, callback=None, debug=True):
        super().__init__(daemon=True)
        self.callback = callback
        self.running = False
        self.ser = None
        self.debug = bool(debug)
        self.port = port
        self.baudrate = baudrate
        self.current_protocol = None
        self.last_valid_speed = 0
        self.last_response = ""
        self.protocol_candidates = ["0", "6", "8", "7"]  # auto, CAN11/500, CAN11/250, CAN29/500
        self._protocol_index = 0

    def _log(self, msg: str):
        if self.debug:
            print(msg)

    def send(self, cmd, read_timeout=2.0):
        if self.ser is None:
            return ""

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

        text = raw.decode("ascii", errors="ignore")
        self.last_response = text
        return text

    def _is_elm_alive(self) -> bool:
        resp = self.send("ATZ", read_timeout=3.0)
        self._log(f"[ELM327] ATZ  -> {repr(resp)}")
        upper = resp.upper()
        return any(k in upper for k in ["ELM", "OK", ">"])

    def _open_and_probe(self, port: str, baudrate: int) -> bool:
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=0.2,
                write_timeout=0.5,
            )
            time.sleep(1.0)
        except Exception as e:
            self._log(f"[ELM327] Open failed {port} @ {baudrate}: {e}")
            self.ser = None
            return False

        try:
            ok = self._is_elm_alive()
            if ok:
                self.port = port
                self.baudrate = baudrate
                self._log(f"[ELM327] Connected on {port} @ {baudrate}")
                return True
        except Exception as e:
            self._log(f"[ELM327] Probe failed {port} @ {baudrate}: {e}")

        try:
            self.ser.close()
        except Exception:
            pass
        self.ser = None
        return False

    def connect(self) -> bool:
        ports = [self.port] if self.port else find_elm327_ports()
        if not ports and self.port:
            ports = [self.port]
        baudrates = [self.baudrate] if self.baudrate else COMMON_BAUDRATES

        self._log(f"[ELM327] Candidate ports: {ports}")
        self._log(f"[ELM327] Candidate baudrates: {baudrates}")

        for port in ports:
            for baud in baudrates:
                if self._open_and_probe(port, int(baud)):
                    return True

        self._log("[ELM327] No working ELM327 port found")
        return False

    def init_elm(self):
        self._log("[ELM327] Initializing...")
        init_cmds = [
            ("ATZ", 3.0),
            ("ATE0", 1.0),
            ("ATL0", 1.0),
            ("ATS0", 1.0),
            ("ATH0", 1.0),
            ("ATCAF0", 1.0),
            ("ATSP0", 1.5),
            ("ATDPN", 1.0),
            ("0100", 2.0),
        ]
        for cmd, timeout in init_cmds:
            resp = self.send(cmd, read_timeout=timeout)
            self._log(f"[ELM327] {cmd:<5} -> {repr(resp)}")

    @staticmethod
    def parse_speed(resp):
        """
        Parse speed from PID 010D response.
        Accepts forms like:
        - 41 0D 1E
        - 410D1E
        - SEARCHING...\r410D1E\r>
        - 7E8 03 41 0D 1E
        """
        cleaned = (resp or "").upper()
        if any(bad in cleaned for bad in ["NO DATA", "STOPPED", "UNABLE TO CONNECT", "ERROR"]):
            return None

        hex_stream = re.sub(r"[^0-9A-F]", "", cleaned)

        # Prefer exact service+PID response.
        idx = hex_stream.find("410D")
        if idx != -1 and len(hex_stream) >= idx + 6:
            speed_hex = hex_stream[idx + 4: idx + 6]
            try:
                return int(speed_hex, 16)
            except ValueError:
                return None

        # Fallback for CAN frames with extra header bytes.
        m = re.search(r"(?:^|[0-9A-F])410D([0-9A-F]{2})", hex_stream)
        if m:
            try:
                return int(m.group(1), 16)
            except ValueError:
                return None
        return None

    def _set_protocol(self, proto: str):
        resp = self.send(f"ATSP{proto}", read_timeout=1.5)
        self.current_protocol = proto
        self._log(f"[ELM327] ATSP{proto} -> {repr(resp)}")
        verify = self.send("ATDPN", read_timeout=1.0)
        self._log(f"[ELM327] ATDPN -> {repr(verify)}")

    def _try_read_speed(self) -> Optional[int]:
        resp = self.send("010D", read_timeout=1.5)
        self._log(f"[ELM327] RAW 010D ({self.current_protocol}): {repr(resp)}")
        return self.parse_speed(resp)

    def _protocol_recovery(self) -> Optional[int]:
        # rotate through likely CAN protocols
        for _ in range(len(self.protocol_candidates)):
            proto = self.protocol_candidates[self._protocol_index % len(self.protocol_candidates)]
            self._protocol_index += 1
            self._set_protocol(proto)
            test = self.send("0100", read_timeout=2.0)
            self._log(f"[ELM327] 0100  -> {repr(test)}")
            speed = self._try_read_speed()
            if speed is not None:
                return speed
        return None

    def run(self):
        if not self.connect():
            return

        self.init_elm()
        self.current_protocol = "0"
        self.running = True
        no_data_count = 0

        while self.running:
            try:
                speed = self._try_read_speed()

                if not self.running:
                    break

                if speed is None:
                    no_data_count += 1
                    if no_data_count >= 3:
                        self._log("[ELM327] No valid speed response, trying protocol recovery...")
                        speed = self._protocol_recovery()
                        no_data_count = 0 if speed is not None else no_data_count
                else:
                    no_data_count = 0

                if speed is not None:
                    self.last_valid_speed = int(speed)
                    if self.callback is not None:
                        self.callback(int(speed))
                else:
                    # Keep GUI alive with explicit 0 when ECU keeps returning nothing.
                    if self.callback is not None:
                        self.callback(0)

            except Exception as e:
                self._log(f"[ELM327] Poll error: {e}")
                if self.callback is not None:
                    self.callback(0)

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
            self.ser = None

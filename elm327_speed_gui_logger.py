import os
import re
import time
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

# pip install pyserial
import serial
import serial.tools.list_ports

LOG_DIR = r"C:\Users\Minko\Desktop\DP\VisionPilot-XR Win\CAN_logs"


def ensure_log_dir() -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    return LOG_DIR


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def ascii_to_hex_string(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


class ELM327Reader:
    def __init__(self, log_callback, speed_callback, status_callback):
        self.log_callback = log_callback
        self.speed_callback = speed_callback
        self.status_callback = status_callback

        self.ser = None
        self.running = False
        self.thread = None
        self.log_file = None
        self.log_path = None
        self.serial_lock = threading.Lock()

    def open_log(self):
        ensure_log_dir()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = os.path.join(LOG_DIR, f"elm327_speed_log_{stamp}.txt")
        self.log_file = open(self.log_path, "a", encoding="utf-8")

    def write_log(self, line: str):
        try:
            if self.log_file:
                self.log_file.write(line + "\n")
                self.log_file.flush()
        except Exception:
            pass

        try:
            self.log_callback(line)
        except Exception:
            pass

    def send_cmd(self, cmd: str, read_timeout: float = 1.0) -> str:
        with self.serial_lock:
            ser = self.ser

        if not ser or not self.running:
            return ""

        payload = (cmd + "\r").encode("ascii", errors="ignore")

        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        try:
            ser.write(payload)
            ser.flush()
        except Exception as e:
            self.write_log(f"[{now_str()}] SERIAL_WRITE_ERROR : {e}")
            return ""

        self.write_log(f"[{now_str()}] REQUEST_ASCII : {cmd}")
        self.write_log(f"[{now_str()}] REQUEST_HEX   : {ascii_to_hex_string(payload)}")

        deadline = time.time() + read_timeout
        raw = b""

        while time.time() < deadline and self.running:
            try:
                waiting = ser.in_waiting
            except Exception:
                break

            try:
                chunk = ser.read(waiting or 1)
            except Exception as e:
                self.write_log(f"[{now_str()}] SERIAL_READ_ERROR  : {e}")
                break

            if chunk:
                raw += chunk
                if b">" in raw:
                    break
            else:
                time.sleep(0.01)

        response_ascii = raw.decode("ascii", errors="ignore").replace("\r", "\\r").replace("\n", "\\n")
        self.write_log(f"[{now_str()}] RESPONSE_ASCII: {response_ascii}")
        self.write_log(f"[{now_str()}] RESPONSE_HEX  : {ascii_to_hex_string(raw)}")

        return raw.decode("ascii", errors="ignore")

    @staticmethod
    def parse_speed_kmh(response: str):
        """
        Works with both:
          41 0D 1E
        and:
          410D1E
        and even mixed text like:
          SEARCHING...410D1E>>
        PID 0x0D returns speed in km/h directly.
        """
        cleaned = response.upper()
        hex_stream = re.sub(r"[^0-9A-F]", "", cleaned)

        idx = hex_stream.find("410D")
        if idx == -1 or len(hex_stream) < idx + 6:
            return None

        speed_hex = hex_stream[idx + 4: idx + 6]
        try:
            return int(speed_hex, 16)
        except ValueError:
            return None

    def initialize_elm327(self):
        init_cmds = [
            "ATZ",
            "ATE0",
            "ATL0",
            # ATS0 nechávam zámerne zapnuté, parser teraz zvláda aj compact odpovede
            "ATS0",
            "ATH0",
            "ATSP0",
        ]
        for cmd in init_cmds:
            if not self.running:
                break
            self.send_cmd(cmd, read_timeout=2.0)
            time.sleep(0.15)

    def connect(self, port: str, baudrate: int):
        self.open_log()
        self.write_log("=" * 70)
        self.write_log(f"[{now_str()}] START SESSION")
        self.write_log(f"[{now_str()}] PORT={port} BAUD={baudrate}")

        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=0.2,
            write_timeout=0.5
        )

        with self.serial_lock:
            self.ser = ser

        self.running = True
        self.status_callback(f"Pripojené: {port} @ {baudrate}")
        self.initialize_elm327()

    def start_polling(self):
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()

    def _poll_loop(self):
        while self.running:
            try:
                response = self.send_cmd("010D", read_timeout=1.2)

                if not self.running:
                    break

                speed = self.parse_speed_kmh(response)

                if speed is not None:
                    self.speed_callback(speed)
                    self.status_callback("Čítanie rýchlosti OK")
                    self.write_log(f"[{now_str()}] SPEED_KMH     : {speed}")
                else:
                    self.status_callback("Rýchlosť sa nepodarilo parsovať")
                    self.write_log(f"[{now_str()}] PARSE_INFO    : PID 010D not found in response")

            except Exception as e:
                self.write_log(f"[{now_str()}] POLL_ERROR    : {e}")
                self.status_callback(f"Chyba čítania: {e}")

            for _ in range(50):
                if not self.running:
                    break
                time.sleep(0.01)

    def disconnect(self):
        self.write_log(f"[{now_str()}] GUI INFO      : Disconnect requested")
        self.running = False

        thread = self.thread
        if thread and thread.is_alive():
            thread.join(timeout=1.5)
        self.thread = None

        with self.serial_lock:
            ser = self.ser
            self.ser = None

        if ser:
            try:
                ser.close()
            except Exception:
                pass

        self.status_callback("Odpojené")
        self.speed_callback(0)

        if self.log_file:
            try:
                self.write_log(f"[{now_str()}] END SESSION")
                self.write_log("=" * 70)
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("VisionPilot-XR | ELM327 OBD2 Speed Reader")
        self.geometry("760x520")
        self.minsize(760, 520)

        self.reader = ELM327Reader(
            log_callback=self.append_log,
            speed_callback=self.update_speed,
            status_callback=self.update_status,
        )

        self.create_widgets()
        self.refresh_ports()
        ensure_log_dir()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")

        ttk.Label(top, text="COM port:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.port_combo = ttk.Combobox(top, width=20, state="readonly")
        self.port_combo.grid(row=0, column=1, sticky="w")

        self.refresh_btn = ttk.Button(top, text="Obnoviť porty", command=self.refresh_ports)
        self.refresh_btn.grid(row=0, column=2, padx=8)

        ttk.Label(top, text="Baud:").grid(row=0, column=3, sticky="w", padx=(20, 6))
        self.baud_combo = ttk.Combobox(top, width=12, state="readonly")
        self.baud_combo["values"] = ("38400", "9600", "115200")
        self.baud_combo.set("9600")
        self.baud_combo.grid(row=0, column=4, sticky="w")

        self.connect_btn = ttk.Button(top, text="Pripojiť", command=self.connect)
        self.connect_btn.grid(row=0, column=5, padx=(20, 6))

        self.disconnect_btn = ttk.Button(top, text="Odpojiť", command=self.disconnect)
        self.disconnect_btn.grid(row=0, column=6)

        info = ttk.LabelFrame(self, text="Rýchlosť vozidla", padding=16)
        info.pack(fill="x", padx=12, pady=(0, 12))

        self.speed_var = tk.StringVar(value="-- km/h")
        self.speed_label = ttk.Label(
            info,
            textvariable=self.speed_var,
            font=("Segoe UI", 28, "bold")
        )
        self.speed_label.pack(anchor="center", pady=8)

        self.status_var = tk.StringVar(value="Nepripojené")
        self.status_label = ttk.Label(info, textvariable=self.status_var, font=("Segoe UI", 10))
        self.status_label.pack(anchor="center")

        path_frame = ttk.Frame(self, padding=(12, 0, 12, 8))
        path_frame.pack(fill="x")
        ttk.Label(
            path_frame,
            text=f"Logovanie do: {LOG_DIR}",
            font=("Segoe UI", 9)
        ).pack(anchor="w")

        log_frame = ttk.LabelFrame(self, text="Live log", padding=8)
        log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.log_text = tk.Text(log_frame, wrap="word", font=("Consolas", 10))
        self.log_text.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scroll.set)

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo["values"] = ports
        if ports:
            self.port_combo.set(ports[0])
        else:
            self.port_combo.set("")

    def append_log(self, line: str):
        def _append():
            try:
                self.log_text.insert("end", line + "\n")
                self.log_text.see("end")
            except Exception:
                pass
        self.after(0, _append)

    def update_speed(self, speed: int):
        def _set():
            try:
                if speed <= 0:
                    self.speed_var.set("0 km/h")
                else:
                    self.speed_var.set(f"{speed} km/h")
            except Exception:
                pass
        self.after(0, _set)

    def update_status(self, text: str):
        self.after(0, lambda: self.status_var.set(text))

    def connect(self):
        port = self.port_combo.get().strip()
        baud = self.baud_combo.get().strip()

        if not port:
            messagebox.showwarning("Chýba port", "Vyber COM port ELM327 zariadenia.")
            return

        try:
            baud_int = int(baud)
        except ValueError:
            messagebox.showerror("Chybný baudrate", "Baudrate musí byť číslo.")
            return

        try:
            self.reader.connect(port, baud_int)
            self.reader.start_polling()
            self.append_log(f"[{now_str()}] GUI INFO      : Polling PID 010D (Vehicle Speed)")
        except Exception as e:
            messagebox.showerror("Chyba pripojenia", str(e))
            self.append_log(f"[{now_str()}] GUI ERROR     : {e}")

    def disconnect(self):
        self.disconnect_btn.config(state="disabled")
        try:
            self.reader.disconnect()
        finally:
            self.disconnect_btn.config(state="normal")

    def on_close(self):
        try:
            self.reader.disconnect()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()

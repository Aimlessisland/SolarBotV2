import serial
import time

SERIAL_PORT = "COM6"
BAUD_RATE = 115200

def connect_port():
    choice = input(f"Initiate serial connection on {SERIAL_PORT}? (y/n): ").strip().lower()
    if choice != 'y':
        print("Skipped serial init (running in print-only mode).")
        return None

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)  # One-time Arduino Uno reset settle
        ser.reset_input_buffer()
        print(f"[CONNECTED] {SERIAL_PORT} @ {BAUD_RATE} ready!\n")
        return ser
    except Exception as e:
        print(f"[ERROR] Could not open {SERIAL_PORT}: {e}")
        return None

def send_cmd(ser, cmd):
    if ser is None:
        print(f"[OFFLINE PRINT] Would send: {cmd}")
        return

    ser.reset_input_buffer()
    ser.write(f"{cmd}\n".encode("utf-8"))
    print(f">>> SENT: {cmd}")

    # Listen and print everything Arduino replies until OK or 3s timeout
    start = time.time()
    while time.time() - start < 3.0:
        if ser.in_waiting > 0:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line:
                print(f"<<< ARDUINO: {line}")
            if line.upper() == "OK":
                break

if __name__ == "__main__":
    ser = connect_port()

    while True:
        cmd = input("\nEnter command (e.g. M1 100) or 'q' to quit: ").strip()
        if not cmd:
            continue
        if cmd.lower() == 'q':
            break
        send_cmd(ser, cmd.upper())

    if ser and ser.is_open:
        ser.close()
        print("Serial port closed.")
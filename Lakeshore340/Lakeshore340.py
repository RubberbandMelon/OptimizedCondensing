"""
Lakeshore340 Python API
by S. Kloos
Created on 06/30/2026
last mod. 06/30/2026
"""
import serial, time

class Lakeshore340:
    """
    Lakeshore 340 Temperature Controller API

    set serial communications terminator to 'LF' on the Lakeshore 340 for this to work properly.
    
    this code will only work if values 'C' and 'D' exist on the Lakeshore 340
    """
    def __init__(self, COMport, baud = 9600, bytesize = serial.SEVENBITS, parity = serial.PARITY_ODD, wait_time = 0.1):
        self.port = COMport
        self.is_open = False
        self.ID = 'LSCI,MODEL340'
        self.baud = baud
        self.bytesize = bytesize
        self.wait_time = wait_time
        self.parity = parity
        self.serial_connection = None

    def open(self):
        if self.is_open:
            print(f"Connection to Lakeshore 340 already open on port {self.port}.")
            return
        try:
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            self.is_open = True
            print(f"Connecting to Lakeshore 340 on port {self.port}...")
        except serial.SerialException as e:
            print(f"Failed to open connection to Lakeshore 340 on port {self.port}: {e}")
            return
        
        self.serial_connection.write(b'*IDN?\n')
        time.sleep(self.wait_time)
        IDReply = self.serial_connection.readline().decode().strip()
        if IDReply.rfind(self.ID) < 0:
            print(f"Error: Device ID mismatch. Expected {self.ID}, got {IDReply}")
            self.close()
        else:
            print(f"Successfully connected to Lakeshore 340 on port {self.port}. Device ID: {IDReply}")

    def close(self):
        if self.is_open:
            self.serial_connection.close()
            self.is_open = False
            print(f"Connection to Lakeshore 340 on port {self.port} closed.")
        else:
            print(f"No open connection to Lakeshore 340 on port {self.port} to close.")

    # ----------------------------------------------------
    # TEMPERATURE READINGS
    # if any value is -1, something went wrong with the reading
    # ----------------------------------------------------
    def read_temperature(self):
        measurement = {"A": -1, "B": -1, "C": -1, "D": -1, "Heater": -1}

        if self.is_open:
            self.serial_connection.write(b'KRDG? A\n')
            measurement["A"] = float(self.serial_connection.readline())
            time.sleep(self.wait_time)
            self.serial_connection.write(b'KRDG? B\n')
            measurement["B"] = float(self.serial_connection.readline())
            time.sleep(self.wait_time)
            self.serial_connection.write(b'KRDG? C\n')
            measurement["C"] = float(self.serial_connection.readline())
            time.sleep(self.wait_time)
            self.serial_connection.write(b'KRDG? D\n')
            measurement["D"] = float(self.serial_connection.readline())
            time.sleep(self.wait_time)
            self.serial_connection.write(b'HTR?\n')
            measurement["Heater"] = float(self.serial_connection.readline().replace("%", ""))
            time.sleep(self.wait_time)

        else:
            print(f"Error: Connection to Lakeshore 340 on port {self.port} is not open.")
        
        print(f"Temp readings from Lakeshore: {measurement}")
        return measurement
    
    # ----------------------------------------------------
    # SORB SETPOINT
    # ----------------------------------------------------
    def set_sorb_setpoint(self, setpoint):
        if self.is_open:
            old_setpoint = self.read_sorb_setpoint()
            self.serial_connection.write(f'SETP 1,{setpoint}\n'.encode())
            time.sleep(self.wait_time)
            print(f"Changed Lakeshore sorb setpoint from {old_setpoint} to {setpoint}.")
        else:
            print(f"Error: Connection to Lakeshore 340 on port {self.port} is not open.")

    def read_sorb_setpoint(self):
        if self.is_open:
            self.serial_connection.write(b'SETP? 1\n')
            setpoint = float(self.serial_connection.readline())
            print(f"Current Lakeshore sorb setpoint: {setpoint}")
            time.sleep(self.wait_time)
            return setpoint
        else:
            print(f"Error: Connection to Lakeshore 340 on port {self.port} is not open.")
            return -1

    # ----------------------------------------------------
    # HEATER RANGE
    # refer to table 1-6 of the Lakeshore 340 manual for valid range values
    # ----------------------------------------------------
    def set_heater_range(self, heater_range):
        if self.is_open:
            if heater_range not in [0, 1, 2, 3, 4, 5]:
                print(f"Error: Invalid heater range {heater_range}. Valid values are 0, 1, 2, 3, 4, or 5.")
                return
            else:
                old_range = self.read_heater_range()
                self.serial_connection.write(f'RANGE {heater_range}\n'.encode())
                time.sleep(self.wait_time)
                print(f"Changed Lakeshore heater range from {old_range} to {heater_range}.")
        else:
            print(f"Error: Connection to Lakeshore 340 on port {self.port} is not open.")

    def read_heater_range(self):
        if self.is_open:
            self.serial_connection.write(b'RANGE?\n')
            heater_range = int(self.serial_connection.readline())
            print(f"Current Lakeshore heater range: {heater_range}")
            time.sleep(self.wait_time)
            return heater_range
        else:
            print(f"Error: Connection to Lakeshore 340 on port {self.port} is not open.")
            return -1
"""
Lakeshore340 Python API
by S. Kloos
Created on 06/30/2026
last mod. 06/30/2026
"""
import time
import serial
from deprecated import deprecated
from loguru import logger

logger = logger.bind(component="Lakeshore340")

class Lakeshore340:
    """
    Lakeshore 340 Temperature Controller API

    set serial communications terminator to 'LF' on the Lakeshore 340 for this to work properly.
    """
    def __init__(self, COMport, baud = 9600, wait_time = 0.1, bytesize=serial.SEVENBITS, parity=serial.PARITY_ODD,):
        self.port = COMport
        self.is_open = False
        self.ID = 'LSCI,MODEL340'
        self.baud = baud
        self.bytesize = bytesize
        self.parity = parity
        self.wait_time = wait_time
        self.serial_connection = None
        logger.debug('Lakeshore340 initialized')

    def open(self):
        if self.is_open:
            logger.debug(f'Connection to Lakeshore 340 already open on port {self.port}')
            return True

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
            logger.debug(f'opening connection to Lakeshore340 on port {self.port}')

        except serial.SerialException as e:
            logger.critical(f'Unable to open serial connection on port {self.port}: {e}')
            return False

        self.serial_connection.write(b"*IDN?\n")
        self.serial_connection.flush()
        time.sleep(self.wait_time)

        IDReply = (
            self.serial_connection.readline()
            .decode("ascii", errors="replace")
            .strip()
        )

        if self.ID not in IDReply:
            logger.critical(f'Devide ID missmatch on Lakeshore340 connection: expected {self.ID} but got {IDReply}')
            self.close()
            return False

        logger.success(f'successfully connected to Lakeshore 340 on port {self.port}')
        return True

    def close(self):
        if self.is_open:
            self.serial_connection.close()
            self.is_open = False
            logger.warning(f'closed connection to Lakeshore340 on port {self.port}')
        else:
            logger.warning(f'No open connection to Lakeshore340 on port {self.port} to close')

    # ----------------------------------------------------
    # GENERAL FUNCTION FOR READING VALUES
    # 
    # commands (list) : for example ['KRDG? A', 'KRDG? B', etc.]
    # returns : dict = for example {'KRDG? A' : a_value, 'KRDG? B' : b_value, etc.}
    # ----------------------------------------------------
    def read_values(self, commands):
        measurement = {'timestamp' : time.time()}

        #check if commands is single string, if yes: insert into list
        if isinstance(commands, str):
            commands = [commands]

        logger.trace(f'Lakeshore340 received commands: {commands}')

        if not self.is_open:
            logger.error(f'Connection to Lakeshore340 on port {self.port} is not open')
            for command in commands:
                measurement[command] = -1
            return measurement

        for command in commands: 
            self.serial_connection.write(f'{command}\n'.encode())
            self.serial_connection.flush()
            logger.trace('Send request to Lakeshore340 via serial connection')
            reply = self.serial_connection.readline().decode("ascii", errors="replace").strip()
            logger.trace(f'Got reply from Lakeshore340: {reply}')
            time.sleep(self.wait_time)

            try:
                measurement[command] = float(reply.replace("%", ""))
            except ValueError:
                logger.error(f'Lakeshore340 reply to command={command} is not numeric, reply={reply}')
                measurement[command] = -1

        logger.trace(f'Lakeshore.read_values returns measurement={measurement}')
        return measurement

    # ----------------------------------------------------
    # GENERAL FUNCTION FOR SETTING VALUES
    # 
    # commands (list) : for example ['SETP 1,12.0', 'RANGE 3', etc.]
    # returns : None
    # ----------------------------------------------------
    def set_values(self, commands):
        if not self.is_open:
            print(f"Error: Connection to Lakeshore 340 on port {self.port} is not open.")
            return None

        #check if commands is single string, if yes: insert into list
        if isinstance(commands, str):
            commands = [commands]

        for command in commands:
            self.serial_connection.write(f'{command}\n'.encode())
            self.serial_connection.flush()
            time.sleep(self.wait_time)
        
        return None

    # ----------------------------------------------------
    # TEMPERATURE READINGS
    # if any value is -1, something went wrong with the reading
    # ----------------------------------------------------
    @deprecated
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
            measurement["Heater"] = float(self.serial_connection.readline().decode().strip().replace("%", ""))
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

    @deprecated
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
    # 
    # refer to table 1-6 of the Lakeshore 340 manual for valid range values
    # ----------------------------------------------------
    def set_heater_range(self, heater_range):
        if not self.is_open:
            print(f"Error: Connection to Lakeshore 340 on port {self.port} is not open.")
            return False

        try:
            heater_range = int(heater_range)
        except (TypeError, ValueError):
            print(f"Error: Invalid heater range {heater_range!r}.")
            return False

        if heater_range not in range(6):
            print(
                f"Error: Invalid heater range {heater_range}. "
                f"Valid values are 0 through 5."
            )
            return False

        old_range = self.read_heater_range()
        self.set_values(f"RANGE {heater_range}")

        print(f"Changed Lakeshore heater range from {old_range} to {heater_range}.")
        return True

    @deprecated
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
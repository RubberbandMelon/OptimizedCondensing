from .Motor import Motor
from .LinearPotentiometer import LinearPotentiometer
import time

from loguru import logger

MOTOR_REVS_PER_SECOND = 0.5

class Valve:
    def __init__(
        self, 
        name, 
        pulse_pin, 
        dir_pin,
        enable_pin,
        CHANNEL,
        adc = None,
        ADC_ADRESSES = (0x68, 0x68),
        power_pin = 19,
        valve_OPEN=2.0,
        valve_CLOSED=0.0
    ):
        self.name = name
        self.linked_valve = None
        self.motor = Motor(pulse_pin, dir_pin, enable_pin, 800, name = self.name)
        self.status = None
        self.ad_converter = adc

        self.poti = LinearPotentiometer(
            adc = self.ad_converter,
            ADC_ADRESSES = ADC_ADRESSES,
            CHANNEL = CHANNEL,
            power_pin = power_pin,
            valve_OPEN=valve_OPEN,
            valve_CLOSED=valve_CLOSED
        )

        if self.ad_converter is None:
            self.ad_converter = self.poti.adc

        self.logger = logger.bind(component=f"Valve_{self.name}")

    def link_other_valve(self, linked_valve):
        if isinstance(linked_valve, Valve) and linked_valve is not self:
            self.linked_valve = linked_valve
            self.logger.debug(f'valve {self.name} received valve {self.linked_valve.name} as linked valve')
        else:
            self.logger.error(f'linked_valve must be a different instance of type Valve, but given type={type(linked_valve)}')
        
    def open_valve(self, override = False):
        if self.linked_valve is None:
            self.logger.error(f'valve {self.name} was not linked at the time of opening request')
            return
        if self.is_open() and not override:
            self.logger.warning(f'tried opening valve {self.name}, but it is already open!')
            return
        self.motor.turn(1030, MOTOR_REVS_PER_SECOND)
        time.sleep(1)
        if self.is_open() and not override:
            self.logger.debug(f'valve {self.name} is now open')
        else if not override:
            self.logger.error(f'valve {self.name} failed to open!')
            raise ValveSecurityException(f'valve {self.name} failed to open and is at position {self.poti.get_position()}', valve_name = self.name, error_code = 1, )

    def close_valve(self, override = False):
        if self.linked_valve is None:
            self.logger.error(f'valve {self.name} was not linked at the time of closing request')
            return
        if self.linked_valve.is_open() and not override:
            self.logger.error(f'tried closing valve {self.name}, but linked valve {self.linked_valve.name} is already closed! aborting!')
            raise ValveSecurityException(f'tried closing valve {self.name}, but linked valve {self.linked_valve.name} is already closed! aborting!', valve_name = self.name)
        if self.is_closed() and not override:
            self.logger.warning(f'tried closing valve {self.name}, but it is already closed!')
            return
        self.motor.turn(-1030, MOTOR_REVS_PER_SECOND)
        time.sleep(1)
        if self.is_closed() and not override:
#            self.logger.debug(f'valve {self.name} is now closed')
#        else if not override:
#            self.logger.error(f'valve {self.name} failed to close!')
#            raise ValveSecurityException(f'valve {self.name} failed to close!', valve_name = self.name, error_code = 2)

    def is_open(self):
        if abs(self.poti.get_position()) < 0.1:
            return True
        return False

    def is_closed(self):
        if abs(self.poti.get_position()-1) < 0.1:
            return True
        return False

    def read_calibration_voltage(self, samples=10):
        values = []
        for _ in range(samples):
            values.append(self.poti.read_voltage())
        return sum(values) / len(values)


    def set_position_calibration(self, open_voltage, closed_voltage):
        self.poti.set_calibration(
            valve_OPEN=open_voltage,
            valve_CLOSED=closed_voltage
        )

class ValveSecurityException(Exception):
    def __init__(self, message, valve_name = None, error_code = None):
        self.message = message
        self.valve_name = valve_name
        self.error_code = error_code

        details = []
        if self.valve_name:
            details.append(f'valve_name={self.valve_name}')
        if self.error_code:
            details.append(f'error_code={self.error_code}')
        
        full_message = self.message
        if details:
            full_message += f"({', '.join(details)})"

        super().__init__(full_message)

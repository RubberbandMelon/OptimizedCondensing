from Lakeshore340.Lakeshore340 import Lakeshore340
from LogClient.LogClient import LogClient
import threading
import time
import numpy
from dataclasses import dataclass
import logging

settings = {
    'Lakeshore340_COMport' : 'COM3',
    'Lakeshore340_baud' : 9600,
    'Lakeshore340_wait_time' : 0.1
}

@dataclass
class Measurement:
    value: float
    timestamp: float 

@dataclass
class Command:
    new_value : float
    timestamp : float

class Lakeshore340Manager:

    def __init__(self):
        # internal variables for handling measurements and setpoints
        self.measurement = Measurement(value = 0, timestamp = time.time())
        self.setpoint = 0
        self.heater_range = 0
        # Lakeshore variables
        self.COMport = settings['Lakeshore340_COMport']
        self.baud = settings['Lakeshore340_baud']
        self.wait_time = settings['Lakeshore340_wait_time']
        self.lakeshore = Lakeshore340(self.COMport, baud = self.baud, wait_time = self.wait_time)
        # LogClient variables
#        self.cl = LogClient(host = 'http://127.0.0.1:5000/')
#        self.cl_devType = 'Lakeshore340'
#        self.cl_version = '1.0'
#        self.cl.initDevice(self.cl_devType, self.cl_version)
        # threading variables (locks, conditions, etc.)
        self.lock = threading.Lock()
        self.change_setpoint_event = threading.Event()
        self.change_heater_range_event = threading.Event()
        self.kill_event = threading.Event()
        self.measurement_condition = threading.Condition()

    def measurement_loop(self):
        self.lakeshore.open()
        while not self.kill_event.is_set():
            waited_intervals = 5
            with self.measurement_condition:
                self.measurement = Measurement(self.lakeshore.read_temperature(), time.time())
                self.measurement_condition.notify_all()
                print(f'Lakeshore: \tvalue={self.measurement.value},\t setpoint = {self.setpoint}')

            if self.change_setpoint_event.is_set():
                self.lakeshore.set_sorb_setpoint(self.setpoint)
                self.change_setpoint_event.clear()
                waited_intervals += waited_intervals

            if self.change_heater_range_event.is_set():
                self.lakeshore.set_heater_range(self.heater_range)
                self.change_heater_range_event.clear()
                waited_intervals += waited_intervals

#            cl.onlinePing() 
            time.sleep(1-waited_intervals*self.wait_time)

        self.lakeshore.close()

    def wait_for_next_measurement(self, last_timestamp):
        with self.measurement_condition:
            self.measurement_condition.wait_for(lambda: self.measurement.timestamp > last_timestamp or self.kill_event.is_set())
            return self.measurement

    def set_setpoint(self, command : Command):
        self.setpoint = command.new_value
        self.change_setpoint_event.set()

    def set_heater_range(self, command : Command):
        self.heater_range = command.new_value
        self.change_heater_range_event.set()

    def kill(self):
        self.kill_event.set()


if __name__ == '__main__':
    lsman = Lakeshore340Manager()
    lsman_thread = threading.Thread(target = lsman.measurement_loop)
    logging.info('Initialized Lakeshore340 Manager')
    lsman_thread.start()
    logging.info('Started Lakeshore340 Manager and measurement_loop')
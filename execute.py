from Lakeshore340.Lakeshore340 import Lakeshore340
from LogClient.LogClient import LogClient
import threading
import time
import numpy
from dataclasses import dataclass
import logging
import copy

settings = {
    'Lakeshore340_COMport' : '/dev/ttyUSB0',
    'Lakeshore340_baud' : 9600,
    'Lakeshore340_wait_time' : 0.1,
    '1K_TEMP_COMMAND' : 'KRDG? x'
    # TODO: hardcode sorb pump temperature
}

# TODO: binary Labmonitor measurement for condensing

@dataclass
class Command:
    new_value : float
    timestamp : float

class Lakeshore340Manager:
    def __init__(self):
        # internal variables for handling measurements and setpoints
        self.measurement = {'timestamp' : time.time()}
        self.setpoint = 0
        self.heater_range = 0
        # Lakeshore variables
        self.COMport = settings['Lakeshore340_COMport']
        self.baud = settings['Lakeshore340_baud']
        self.wait_time = settings['Lakeshore340_wait_time']
        self.lakeshore = Lakeshore340(self.COMport, baud = self.baud, wait_time = self.wait_time)
        # threading variables (locks, conditions, etc.)
        self.data_lock = threading.Lock()
        self.change_setpoint_event = threading.Event()
        self.change_heater_range_event = threading.Event()
        self.kill_event = threading.Event()
        self.measurement_condition = threading.Condition()
        self.clman = None

    def measurement_loop(self, logclient_manager):
        if not self.lakeshore.open():
            print("ERROR: Unable to connect to Lakeshore340! Shutting down manager...")
            return 
        self.clman = logclient_manager

        while not self.kill_event.is_set():
            with self.measurement_condition:
                # get active measurements and their settings from the Labmonitor= copy.copy(self.clman.active_measurements)
                with self.data_lock:
                    active_measurements = copy.deepcopy(self.clman.active_measurements)
                    measurement_params = copy.deepcopy(self.clman.measurement_params)

                # create list of all new measurements
                new_measurement = {'timestamp' : time.time()}
                for measID in active_measurements:
                    params = measurement_params[measID]
                    command = params['command']
                    value = self.lakeshore.read_values(command)[command]

                    new_measurement[measID] = value

                # save new measurements to object varibles
                self.measurement = new_measurement
                self.measurement_condition.notify_all()

            # check for setpoint changes
            if self.change_setpoint_event.is_set():
                self.lakeshore.set_sorb_setpoint(self.setpoint)
                self.change_setpoint_event.clear()

            # check for heater range changes
            if self.change_heater_range_event.is_set():
                self.lakeshore.set_heater_range(self.heater_range)
                self.change_heater_range_event.clear()

            # sleep so long that the loops runs once every second
            elapsed_time = time.time() - self.measurement['timestamp']
            time.sleep(max(0, 1.0 - elapsed_time))

        self.lakeshore.close()

    def wait_for_next_measurement(self, last_timestamp):
        with self.measurement_condition:
            self.measurement_condition.wait_for(lambda: self.measurement['timestamp'] > last_timestamp or self.kill_event.is_set())
            return self.measurement

    def set_setpoint(self, command : Command):
        self.setpoint = command.new_value
        self.change_setpoint_event.set()

    def set_heater_range(self, command : Command):
        try:
            self.heater_range = int(command.new_value)
            self.change_heater_range_event.set()
        except:
            print("ERROR: heater range must be an integer!")

    def kill(self):
        self.kill_event.set()

class LogClientManager:
    def __init__(self):
        # LogClient variables
        self.cl = LogClient(host = 'http://127.0.0.1:5000/')
        self.cl_devType = 'Condense RaspberryPi'
        self.cl_version = '1.0'
        self.cl.initDevice(self.cl_devType, self.cl_version)
        self.onlinePing_interval = 1.0

        self.lsman = None
        self.kill_event = threading.Event()

        # create and initialize list of active measurements and dictionary of measurements
        self.active_measurements = self.cl.getActiveMeasurements()
        self.measurement_params = {}
        self.next_update_times = {'ping' : time.time() + self.onlinePing_interval}
        for measID in self.active_measurements:
            self.measurement_params[measID] = self.cl.getMeasurementOptions(measID)
            self.next_update_times[measID] = time.time() + float(self.measurement_params[measID]["interval"])

    def logging_loop(self, lakeshore_manager):
        self.lsman = lakeshore_manager
        while not self.kill_event.is_set():
            # onlinePing 
            if self.next_update_times['ping'] <= time.time():
                self.next_update_times['ping'] = time.time() + self.onlinePing_interval
                if self.cl.onlinePing():
                    # get new data from Labmonitor server via LogClient
                    new_active_measurements = self.cl.getActiveMeasurements()
                    new_measurement_params = {}
                    for measID in new_active_measurements:
                        new_measurement_params[measID] = self.cl.getMeasurementOptions(measID)
                        # create entry in next_update_times if measID is new
                        if measID not in self.next_update_times:
                            self.next_update_times[measID] = time.time() + float(new_measurement_params[measID]["interval"])
                    
                    # set internal variables to the new values
                    with self.lsman.data_lock:
                        self.active_measurements = new_active_measurements
                        self.measurement_params = new_measurement_params

            # iterate over all measID
            for measID in self.active_measurements:
                # check if a value update is due
                if self.next_update_times[measID] <= time.time():
                    # instantly schedule the next update
                    self.next_update_times[measID] = time.time() + self.measurement_params[measID]['interval']
                    try:
                        value = self.lsman.measurement[measID]
                        try:
                            self.cl.addLog(measID,value) 
                        except:
                            print(f'ERROR: clman unable to log measID={measID}, value={value:.3f}')
                    except:
                        print(f'ERROR: clman unable to read measurment with measID={measID} from lsman')
            
            time.sleep(0.05) # do this to prevent this loop from taking aaaaall cpu load

    def kill(self):
        self.kill_event.set()


if __name__ == '__main__':
    lsman = Lakeshore340Manager()
    clman = LogClientManager()
    lsman_thread = threading.Thread(target = lsman.measurement_loop, args = (clman,))
    clman_thread = threading.Thread(target = clman.logging_loop, args = (lsman,))
    logging.info('Initialized Lakeshore340 Manager')
    lsman_thread.start()
    clman_thread.start()
    logging.info('Started Lakeshore340 Manager and measurement_loop')
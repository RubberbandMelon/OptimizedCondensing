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
    '1K_TEMP_COMMAND' : 'KRDG? X',
    'measurement_interval' : 1.0
}

# TODO: binary Labmonitor measurement for condensing

@dataclass
class Command:
    new_value : float
    timestamp : float
    
@dataclass
class Measurement_1K:
    value : float
    timestamp : float

class Lakeshore340Manager:
'''
Manager to wrap the Lakeshore340 class. Enables control via threading
Run Thread with a measurement_loop(LogClientManager)

functions:
    - __init(self)__: usual behavior, defines variables and creates objects for lakeshore, conditions, locks
    - measurement_loop(self, logclient_manager): loop that fetches reads data using the Lakeshore340
    - wait_for_next_measurement(self, last_measurement_time): uses condition to return new measurement once its available
    - wait_for_next_1K_TEMP(self, last_timestamp): uses condititon to return new 1K TEMP once its available
    - set_setpoint(self, command): set sorb setpoint in next measurement loop
    - set_heater_range(self, command): set heater range in next measurement loop
    - kill(self): stop the thread
'''
    def __init__(self):
    '''
    initiate object variables

    returns: None
    '''
        # internal variables for handling measurements and setpoints
        self.measurement = {'timestamp' : time.time()}
        self.setpoint = 0
        self.heater_range = 0
        self.measurement_1K = Measurement_1K(value = -1, timestamp = time.time())
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
    '''
    thread-compatible measurement loop. 
    use threading.Thread(target = lsman.measurement_loop, args = (clman,))

    Arguments:
        - LogClientManager: pass this object so communication with Labmonitor is possible

    Behaviour:
        #1 open Lakeshore340 connection and initialize internal LogClientManager variable 
        #2 loop dies if kill() is called
        #3 grab measurement_condition to prevent malfunctionous data transfer between thread
        #4 grab measID and measurement conditions from LogClientManager
        #5 iterate over measID and measure using measurement conditions
            #5.1 Error if measID doesnt have any matching measurement conditions
            #5.2 Error if measurement conditions doesnt contain any command
            #5.3 read value from Lakeshore340 using the command from Labmonitor
           writes measurement to 
           self.measurements = {
               'timestamp' : latest timestamp,
               'COMMAND SET IN LABMONITOR' : value,
               'ANOTHER COMMAND' : value,
               'YET ANOTHER COMMAND' : value
           }
           if value = -1, something went wrong!
        #6 1K TEMP Fallback - hardcoded section
            #6.1 If 1K TEMP is already measured, copy it to internal variable measurement_1K
            #6.2 If not, read 1K TEMP from Lakeshore340 and save it to internal variable measurement_1K
        #7 Release measurement_condition and notify about that
        #8 change sorb setpoint if event is set
        #9 change heater range if event is set
        #10 sleep so long that measurements happen at measurement_interval
    Returns:
        - None
    '''
        #1 open Lakeshore340 connection and initialize internal LogClientManager variable 
        if not self.lakeshore.open():
            print("ERROR: Unable to connect to Lakeshore340! Shutting down manager...")
            return 
        self.clman = logclient_manager

        #2 loop dies if kill() is called
        while not self.kill_event.is_set():

            #3 grab measurement_condition to prevent malfunctionous data transfer between thread
            with self.measurement_condition:
                #4 grab measID and measurement conditions from LogClientManager
                with self.data_lock:
                    active_measurements = copy.deepcopy(self.clman.active_measurements)
                    measurement_params = copy.deepcopy(self.clman.measurement_params)

                new_measurement = {'timestamp' : time.time()}
    
                #5 iterate over measID and measure using measurement conditions
                for measID in active_measurements:
    
                    #5.1 Error if measID doesnt have any matching measurement conditions
                    if measID not in measurement_params:
                        new_measurement[measID] = -1
                        print(f'ERROR: measID {measID} does not have any measurement paramters!')
                        continue

                    #5.2 Error if measurement conditions doesnt contain any command
                    params = measurement_params[measID]
                    if 'command' not in params:
                        new_measurement[measID] = -1
                        print(f'ERROR: measurement parameters for measID {measID} doesnt contain a command!')
                        continue

                    #5.3 read value from Lakeshore340 using the command from Labmonitor
                    command = params['command']
                    reply = self.lakeshore.read_values(command)
                    if isinstance(reply, dict):
                        value = reply.get(command, -1)
                    else:
                        value = -1
                    new_measurement[measID] = value

                #5.3 Save the new measurement to the object variable
                self.measurement = new_measurement

                #6 1K TEMP Fallback - hardcoded section
                COMMAND_1K_TEMP = settings['1K_TEMP_COMMAND']
                measID_1K_TEMP = [
                    measID
                    for measID, params in measurement_params.items()
                    if params.get("command", "").strip().upper() == COMMAND_1K_TEMP.strip().upper()
                ]
                #6.1 If 1K TEMP is already measured, copy it to internal variable measurement_1K
                if measID_1K_TEMP:
                    self.measurement_1K = Measurement_1K(
                        value = self.measurement.get(measID_1K_TEMP[0], -1),
                        timestamp = self.measurement['timestamp']
                    )
                #6.2 If not, read 1K TEMP from Lakeshore340 and save it to internal variable measurement_1K
                else:
                    print('WARNING: 1K temp is not measured ')
                    reply_measurement_1K = self.lakeshore.read_values(COMMAND_1K_TEMP)
                    if isinstance(reply_measurement_1K, dict):
                        value_1K = reply_measurement_1K.get(COMMAND_1K_TEMP, -1)
                        timestamp_1K = reply_measurement_1K.get("timestamp", time.time())
                    else:
                        value_1K = -1
                        timestamp_1K = time.time()
                        print('ERROR: Lakeshore didnt return a dict on 1K request')

                    self.measurement_1K = Measurement_1K(
                        value=value_1K,
                        timestamp=timestamp_1K
                    )

                #7 Release measurement_condition and notify about that
                self.measurement_condition.notify_all()

            #8 change sorb setpoint if event is set
            if self.change_setpoint_event.is_set():
                self.lakeshore.set_sorb_setpoint(self.setpoint)
                self.change_setpoint_event.clear()

            #9 change heater range if event is set
            if self.change_heater_range_event.is_set():
                self.lakeshore.set_heater_range(self.heater_range)
                self.change_heater_range_event.clear()

            #10 sleep so long that measurements happen at measurement_interval
            elapsed_time = time.time() - self.measurement['timestamp']
            time.sleep(max(0, settings['measurement_interval'] - elapsed_time))

        self.lakeshore.close()

    def wait_for_next_measurement(self, last_timestamp):
    '''
    waits for new measurement and returns it

    Arguments:
        - last_timestamp: timestamp of the last measurement the requester has

    Returns:
        - dict: self.measurements = {
               'timestamp' : latest timestamp,
               'COMMAND SET IN LABMONITOR' : value,
               'ANOTHER COMMAND' : value,
               'YET ANOTHER COMMAND' : value
           } 
    '''
        with self.measurement_condition:
            self.measurement_condition.wait_for(lambda: self.measurement['timestamp'] > last_timestamp or self.kill_event.is_set())
            return self.measurement

    def wait_for_next_1K_TEMP(self, last_timestamp):
    '''
    waits for new 1K TEMP measurement and returns it

    Arguments:
        - last_timestamp: timestamp of the last 1K TEMP measurement the requester has

    Returns:
        Measurement object: value = 1K TEMP, timestamp = timestamp of measurement
    '''
        with self.measurement_condition:
            self.measurement_condition.wait_for(lambda: self.measurement_1K.timestamp > last_timestamp or self.kill_event.is_set())
            return self.measurement_1K

    def set_setpoint(self, command : Command):
    '''
    sets sorb setpoint on the next measurement loop

    Arguments:
        - Command: new_value = new sorb setpoint, timestamp: time of the change request

    Returns:
        None
    '''
        self.setpoint = command.new_value
        self.change_setpoint_event.set()

    def set_heater_range(self, command : Command):
    '''
    sets heater range on the next measurement loop

    Arguments:
        - Command: new_value = new heater range, timestamp: time of the change request

    Returns:
        None
    '''
        try:
            self.heater_range = int(command.new_value)
            self.change_heater_range_event.set()
        except:
            print("ERROR: heater range must be an integer!")

    def kill(self):
    '''
    kills the measurement loop and thread
    '''
        self.kill_event.set()

class LogClientManager:
'''
Manager to wrap the LogClient class. Enables control via threading.
Run Thread with loggingloop(Lakeshore340Manager)

functions:
    - __init__(self): initializes internal variables
    - logging_loop(self, Lakeshore340Manager): loop that fetches measurement conditions from the Labmonitor and pushes value updates
    - kill(self): stop the thread
'''

    def __init__(self):
    '''
    initiate object variables

    returns: None
    '''
        # LogClient object and variables
        self.cl = LogClient(host = 'http://127.0.0.1:5000/')
        self.cl_devType = 'Condenser RaspberryPi'
        self.cl_version = '1.0'
        self.cl.initDevice(self.cl_devType, self.cl_version)
        self.onlinePing_interval = 1.0

        # objects from threading and cross-thread data transfer
        self.lsman = None
        self.kill_event = threading.Event()

        # initialize list of active measurements, dictionary of measurement parameters and dictionary of next upload times  
        self.active_measurements = self.cl.getActiveMeasurements()
        self.measurement_params = {}
        self.next_update_times = {'ping' : time.time() + self.onlinePing_interval}
        # iterate over all measID to initiate their measurement parameters and their next upload time
        for measID in self.active_measurements:
            self.measurement_params[measID] = self.cl.getMeasurementOptions(measID)
            self.next_update_times[measID] = time.time() + float(self.measurement_params[measID]["interval"])

    def logging_loop(self, lakeshore_manager):
    '''
    thread-compatible logging loop. 
    use threading.Thread(target = clman.logging_loop, args = (lsman,))

    Arguments:
        - Lakeshore340Manager: pass this object so measurements can be fetched from the Lakeshore340Manager

    Behaviour:
        #1 initialize internal Lakeshore340Manager object
        #2 end the loop if kill() was called
        #3 

    Returns:
        None
    '''

        #1 initialize internal Lakeshore340Manager object
        self.lsman = lakeshore_manager
        #2 end the loop if kill() was called
        while not self.kill_event.is_set():
            #3 onlinePing
            #3.1 check if onlinePing is due
            if self.next_update_times['ping'] <= time.time():
                #3.2 immediately schedule the next onlinePing after self.onlinePing_interval
                self.next_update_times['ping'] = time.time() + float(self.onlinePing_interval)
                #3.3 call onlinePing()
                if self.cl.onlinePing():
                    #3.4 if onlinePing() returns True, download new active measurements
                    new_active_measurements = self.cl.getActiveMeasurements()
                    new_measurement_params = {}
                    #3.5 iterate over new active measurements to save new measurement parameters
                    for measID in new_active_measurements:
                        new_measurement_params[measID] = self.cl.getMeasurementOptions(measID)
                        #3.6 schedule next upload time, if a new measID enters the active measurements
                        if measID not in self.next_update_times:
                            self.next_update_times[measID] = time.time() + float(new_measurement_params[measID]["interval"])
                    
                    #3.7 save new measurement IDs/parameters to internal variables under data_lock 
                    with self.lsman.data_lock:
                        self.active_measurements = new_active_measurements
                        self.measurement_params = new_measurement_params

            #4 iterate over all measID
            for measID in self.active_measurements:
                #4.1 check if upload is due for the respective measID
                if self.next_update_times[measID] <= time.time():
                    #4.2 if True, schedule next measurement after set interval from Labmonitor 
                    self.next_update_times[measID] = time.time() + float(self.measurement_params[measID]['interval'])
                    #4.3 grab measurement from Lakeshore340Manager and log it into the Labmonitor
                    try:
                        value = self.lsman.measurement.get(measID, -1)
                        try:
                            self.cl.addLog(measID,value) 
                        except:
                            print(f'ERROR: clman unable to log measID={measID}, value={value}')
                    except:
                        print(f'ERROR: clman unable to read measurment with measID={measID} from lsman')
            
            #5 sleep for 0.05 s to not overload the processor with this loop
            time.sleep(0.05)

    def kill(self):
        '''
        kills the logging loop and thread
        '''
        self.kill_event.set()


if __name__ == '__main__':
    # initiate manager objects
    lsman = Lakeshore340Manager()
    clman = LogClientManager()
    # initiate threads
    lsman_thread = threading.Thread(target = lsman.measurement_loop, args = (clman,))
    clman_thread = threading.Thread(target = clman.logging_loop, args = (lsman,))
    logging.info('Initialized Lakeshore340 Manager')
    # start threads
    lsman_thread.start()
    clman_thread.start()
    logging.info('Started Lakeshore340 Manager and measurement_loop')
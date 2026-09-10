from Lakeshore340.Lakeshore340 import Lakeshore340
from LogClient.LogClient import LogClient
from Valve.Valve import Valve
import threading
import time
import numpy as np
from dataclasses import dataclass
import copy
from loguru import logger
import sys
from pathlib import Path

settings = {
    'Lakeshore340_COMport' : '/dev/ttyUSB0',
    'Lakeshore340_baud' : 9600,
    'Lakeshore340_wait_time' : 0.1, # due to hardware limitations, must be > 0.1 seconds
    '1K_TEMP_COMMAND' : 'KRDG? B',
    'SORB_TEMP_COMMAND' : 'KRDG? A',
    'measurement_interval' : 1.0, # start measuring all Lakeshore data every 1 second. change to 0 for continuous measuring

    # motor pinout
    'VALVE_SORB_PULSE' : 17,
    'VALVE_SORB_DIR' : 27,
    'VALVE_SORB_ENA' : 22,
    'VALVE_1K_PULSE' : 5,
    'VALVE_1K_DIR' :  6,
    'VALVE_1K_ENA' : 13,

    # poti pinout
    'ADC_ADDRESSES' : (0x68, 0x68), # do NOT change to (0x68, 0x69) because 0x69 is burnt out!
    'POTI_POWER' : 19, # +3.3 V pin for potis
    'VALVE_SORB_CHANNEL' : 7,
    'VALVE_1K_CHANNEL' : 8,

    # valve position calibration
    'VALVE_SORB_OPEN' : 2,
    'VALVE_SORB_CLOSED' : 0.2,
    'VALVE_1K_OPEN' : 2,
    'VALVE_1K_CLOSED' : 0.2,

    # averaging to get mean 1K temp. mean temp + threshold is how low the 1K TEMP must go to commence the condense 
    '1K_AVERAGING_DURATION': 120, # number of measurements, by default: number = seconds
    '1K_THRESHOLD' : 0.05, # how much higher than the average should 1K TEMP be?
    'TEMP_SORB_TOLERANCE' : 0.1 # tolerance for sorb temperature checks
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

@dataclass
class Measurement_SORB_TEMP:
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
        self.measurement_sorb_temp = Measurement_SORB_TEMP(value = -1, timestamp = time.time())
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

        logger.debug('Lakeshore340Manager initiated')
        

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
            #7 SROB TEMP Fallback - hardcoded section
                #7.1 If SORB TEMP is already measured, copy it to internal variable measurement_SORB_TEMP
                #7.2 If not, read SORB TEMP from Lakeshore340 and save it to internal variable measurement_SORB_TEMP
            #8 Release measurement_condition and notify about that
            #9 change sorb setpoint if event is set
            #10 change heater range if event is set
            #11 sleep so long that measurements happen at measurement_interval
        Returns:
            - None
        '''
        logger.debug('started measurement_loop thread')
        self.clman = logclient_manager

        #1 open Lakeshore340 connection and initialize internal LogClientManager variable 
        if not self.lakeshore.open():
            logger.critical('Unable to open Lakeshore340 connection!')
            logger.critical('Shutting down measurement loop')
            self.clman.kill()
            return 
        logger.info('opened connection to Lakeshore340')

        #2 loop dies if kill() is called
        while not self.kill_event.is_set():
            #3 grab measurement_condition to prevent malfunctionous data transfer between thread
            with self.measurement_condition:
                #4 grab measID and measurement conditions from LogClientManager
                with self.data_lock:
                    active_measurements = copy.deepcopy(self.clman.active_measurements)
                    measurement_params = copy.deepcopy(self.clman.measurement_params)
                    logger.trace(f'measurement_loop : {len(active_measurements)} total measIDs in Lakeshore340Manager: {active_measurements}')

                new_measurement = {'timestamp' : time.time()}
    
                #5 iterate over measID and measure using measurement conditions
                for measID in active_measurements:
                    logger.trace(f'measID={measID} : started measurement')

                    #5.1 Error if measID doesnt have any matching measurement conditions
                    if measID not in measurement_params:
                        new_measurement[measID] = -1
                        logger.error(f'measID={measID} : does not have any measurement conditions!')
                        continue
                    logger.trace(f'measID={measID} : found measurement conditions')

                    #5.2 Error if measurement conditions doesnt contain any command
                    params = measurement_params[measID]
                    if 'command' not in params:
                        new_measurement[measID] = -1
                        logger.error(f'measID={measID} : measurement condition does not contain a command!')
                        continue
                    command = params['command']
                    logger.trace(f"measID={measID}: found command={command} {params.get('unit', '')}")

                    #5.3 read value from Lakeshore340 using the command from Labmonitor
                    reply = self.lakeshore.read_values(command)
                    logger.trace(f'measID={measID} : received reply from Lakeshore340, reply={reply}')
                    if isinstance(reply, dict):
                        value = reply.get(command, -1)
                        logger.trace(f'measID={measID} : measured value={value}')
                    else:
                        value = -1
                        logger.error(f'measID={measID} : Lakeshore340 did not return a dictionary!')
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
                    logger.trace('1K TEMP FALLBACK: found 1K TEMP measurement')

                #6.2 If not, read 1K TEMP from Lakeshore340 and save it to internal variable measurement_1K
                else:
                    logger.warning('1K TEMP FALLBACK: 1K temp is not measured! reverting to fallback measurement')
                    reply_measurement_1K = self.lakeshore.read_values(COMMAND_1K_TEMP)
                    if isinstance(reply_measurement_1K, dict):
                        value_1K = reply_measurement_1K.get(COMMAND_1K_TEMP, -1)
                        timestamp_1K = reply_measurement_1K.get("timestamp", time.time())
                    else:
                        value_1K = -1
                        timestamp_1K = time.time()
                        logger.error('1K TEMP FALLBACK: Lakeshore340 did not return a dictionary on fallback 1K request')

                    self.measurement_1K = Measurement_1K(
                        value=value_1K,
                        timestamp=timestamp_1K
                    )
                    logger.trace(f'1K TEMP FALLBACK: measured 1K TEMP = {self.measurement_1K.value} K')

                #7 SORB TEMP Fallback - hardcoded section
                COMMAND_SORB_TEMP = settings['SORB_TEMP_COMMAND']
                measID_SORB_TEMP = [
                    measID
                    for measID, params in measurement_params.items()
                    if params.get("command", "").strip().upper() == COMMAND_SORB_TEMP.strip().upper()
                ]

                #7.1 If SORB TEMP is already measured, copy it to internal variable measurement_sorb_temp
                if measID_SORB_TEMP:
                    self.measurement_sorb_temp = Measurement_SORB_TEMP(
                        value = self.measurement.get(measID_SORB_TEMP[0], -1),
                        timestamp = self.measurement['timestamp']
                    )
                    logger.trace('SORB TEMP FALLBACK: found SORB TEMP measurement')

                #7.2 If not, read SORB TEMP from Lakeshore340 and save it to internal variable measurement_sorb_temp
                else:
                    logger.warning('SORB TEMP FALLBACK: sorb temp is not measured! reverting to fallback measurement')
                    reply_measurement_sorb_temp = self.lakeshore.read_values(COMMAND_SORB_TEMP)
                    if isinstance(reply_measurement_sorb_temp, dict):
                        value_sorb_temp = reply_measurement_sorb_temp.get(COMMAND_SORB_TEMP, -1)
                        timestamp_sorb_temp = reply_measurement_sorb_temp.get("timestamp", time.time())
                    else:
                        value_sorb_temp = -1
                        timestamp_sorb_temp = time.time()
                        logger.error('SORB TEMP FALLBACK: Lakeshore340 did not return a dictionary on fallback sorb temp request')

                    self.measurement_sorb_temp = Measurement_SORB_TEMP(
                        value=value_sorb_temp,
                        timestamp=timestamp_sorb_temp
                    )
                    logger.trace(f'SORB TEMP FALLBACK: measured SORB TEMP = {self.measurement_sorb_temp.value} K')

                #8 Release measurement_condition and notify about that
                logger.trace('measurement_loop : released measurement_condition and notified all threads that measurement is done')
                self.measurement_condition.notify_all()

            #9 change sorb setpoint if event is set
            if self.change_setpoint_event.is_set():
                logger.debug(f'info : registered new sorb setpoint = {self.setpoint} K. sending request to Lakeshore340')
                self.lakeshore.set_sorb_setpoint(self.setpoint)
                logger.success(f'sorb setpoint set to {self.setpoint} K')
                self.change_setpoint_event.clear()

            #10 change heater range if event is set
            if self.change_heater_range_event.is_set():
                logger.debug(f'info : registered new heater range = {self.heater_range}. sending request to Lakeshore340')
                self.lakeshore.set_heater_range(self.heater_range)
                logger.success(f'heater range set to {self.heater_range}')
                self.change_heater_range_event.clear()

            #11 sleep so long that measurements happen at measurement_interval
            elapsed_time = time.time() - self.measurement['timestamp']
            sleep_time = max(0, settings['measurement_interval'] - elapsed_time)
            logger.trace(f'measurement_loop : sleeping for {sleep_time} s')
            time.sleep(sleep_time)

        logger.info('closing connection to Lakeshore340')
        self.lakeshore.close()
        logger.debug('killed measurement_loop thread')

        with self.measurement_condition:
            self.measurement_condition.notify_all()

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
            logger.trace('Now measurement done and now handed to requester!')
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
            logger.trace('New 1K measurement done and now handed to requester!')
            return self.measurement_1K

    def wait_for_next_SORB_TEMP(self, last_timestamp):
        '''
        waits for new SORB TEMP measurement and returns it

        Arguments:
            - last_timestamp: timestamp of the last SORB TEMP measurement the requester has

        Returns:
            Measurement object: value = SORB TEMP, timestamp = timestamp of measurement
        '''
        with self.measurement_condition:
            self.measurement_condition.wait_for(lambda: self.measurement_sorb_temp.timestamp > last_timestamp or self.kill_event.is_set())
            logger.trace('New SORB TEMP measurement done and now handed to requester!')
            return self.measurement_sorb_temp

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
            if self.heater_range > 5 or self.heater_range < 0:
                logger.error(f'heater range must be an integer between 0 and 5! given value = {self.heater_range}') 
                return
            self.change_heater_range_event.set()
        except:
            logger.error(f'heater range must be an interger between 0 and 5! given type = {type(command.new_value)}')

    def kill(self):
        '''
        kills the measurement loop and thread
        '''
        logger.debug('setting Lakeshore340Manager.kill_event')
        self.kill_event.set()

class LogClientManager:
    '''
    Manager to wrap the LogClient class. Enables control via threading.
    Run Thread with loggerloop(Lakeshore340Manager)

    functions:
        - __init__(self): initializes internal variables
        - logger_loop(self, Lakeshore340Manager): loop that fetches measurement conditions from the Labmonitor and pushes value updates
        - kill(self): stop the thread
    '''

    def __init__(self):
        '''
        initiate object variables

        returns: None
        '''
        # LogClient object and variables
        self.cl = LogClient(host = 'http://labmonitor.fmq.uni-stuttgart.de:8000/')
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
        logger.debug(f'initialized LogClientManager object with devType={self.cl_devType} and version={self.cl_version}')
        logger.trace(f'received initial measurement params: {len(self.active_measurements)} total measurements with conditions={self.measurement_params}')

    def logger_loop(self, lakeshore_manager):
        '''
        thread-compatible logger loop. 
        use threading.Thread(target = clman.logger_loop, args = (lsman,))

        Arguments:
            - Lakeshore340Manager: pass this object so measurements can be fetched from the Lakeshore340Manager

        Behaviour:
            #1 initialize internal Lakeshore340Manager object
            #2 end the loop if kill() was called
            #3 

        Returns:
            None
        '''

        logger.debug('starting logger_loop')

        #1 initialize internal Lakeshore340Manager object
        self.lsman = lakeshore_manager
        #2 end the loop if kill() was called
        while not self.kill_event.is_set():
            #3 onlinePing
            #3.1 check if onlinePing is due
            if self.next_update_times['ping'] <= time.time():
                #3.2 immediately schedule the next onlinePing after self.onlinePing_interval
                self.next_update_times['ping'] = time.time() + float(self.onlinePing_interval)
                logger.trace(f"onlinePing is due, next scheduled ping at {self.next_update_times['ping']}")
                
                #3.3 call onlinePing()
                if self.cl.onlinePing():
                    #3.4 if onlinePing() returns True, download new active measurements
                    new_active_measurements = self.cl.getActiveMeasurements()
                    new_measurement_params = {}
                    logger.debug(f'measurement parameters changed, {len(new_active_measurements)} total measurements: {new_active_measurements}')
                    #3.5 iterate over new active measurements to save new measurement parameters
                    for measID in new_active_measurements:
                        new_measurement_params[measID] = self.cl.getMeasurementOptions(measID)
                        logger.debug(f'new parameters for measID={measID}: {new_measurement_params[measID]}')
                        #3.6 schedule next upload time, if a new measID enters the active measurements
                        if measID not in self.next_update_times:
                            logger.debug(f'this measurement previously did not exist: measID = {measID}')
                            self.next_update_times[measID] = time.time() + float(new_measurement_params[measID]["interval"])
                    
                    #3.7 save new measurement IDs/parameters to internal variables under data_lock 
                    with self.lsman.data_lock:
                        self.active_measurements = new_active_measurements
                        self.measurement_params = new_measurement_params
                        logger.trace('saved new measurements to LogClientManager internal variables')

            #4 iterate over all measID
            for measID in self.active_measurements:

                #4.1 check if upload is due for the respective measID
                if self.next_update_times[measID] <= time.time():

                    #4.2 if True, schedule next measurement after set interval from Labmonitor 
                    self.next_update_times[measID] = time.time() + float(self.measurement_params[measID]['interval'])
                    logger.trace(f'upload for measID={measID} is due, next measurement at {self.next_update_times[measID]}')

                    #4.3 grab measurement from Lakeshore340Manager and log it into the Labmonitor
                    try:
                        value = self.lsman.measurement.get(measID, -1)
                        try:
                            self.cl.addLog(measID,value) 
                        except:
                            logger.error(f'LogClientManager is unable to log measID={measID}, value={value} to Labmonitor')
                    except:
                        logger.error(f'LogClientManager is unable to read measurement with measID={measID} from LakeshoreManager')
            
            #5 sleep for 0.05 s to not overload the processor with this loop
            time.sleep(0.05)
        logger.info('Thread LogClientManager shut down')

    def kill(self):
        '''
        kills the logger loop and thread
        '''
        self.kill_event.set()
        logger.debug('Set LogClientManager.kill_event')

class CondenseSequence():
    '''
    Class that houses the condense sequence

    functions:
        - run(self, lsman, clman): executes the condense sequence
        - ramp_step(self, setpoint): set setpoint and waits until sorb reaches it and TEMP_1K_upper_bound
    '''

    def __init__(self):
        # === condense parameters ===

        self.valve_sorb = Valve(
            name = 'VALVE_SORB', 
            pulse_pin = settings['VALVE_SORB_PULSE'],
            dir_pin = settings['VALVE_SORB_DIR'],
            CHANNEL = settings['VALVE_SORB_CHANNEL'],
            valve_OPEN = settings['VALVE_SORB_OPEN'],
            valve_CLOSED = settings['VALVE_SORB_CLOSED'],
            ADC_ADRESSES = settings['ADC_ADDRESSES']    
        )
        self.valve_1K = Valve(
            name = 'VALVE_1K', 
            pulse_pin = settings['VALVE_1K_PULSE'],
            dir_pin = settings['VALVE_1K_DIR'],
            CHANNEL = settings['VALVE_1K_CHANNEL'],
            valve_OPEN = settings['VALVE_1K_OPEN'],
            valve_CLOSED = settings['VALVE_1K_CLOSED'],
            ADC_ADRESSES = settings['ADC_ADDRESSES'],
            adc = self.valve_sorb.ad_converter
        )
        self.valve_sorb.link_other_valve(self.valve_1K)
        self.valve_1K.link_other_valve(self.valve_sorb)
        self.lsman = None
        self.clman = None
        logger.debug('CondenseSequence initialized!')

    def run(self, lsman, clman):
        self.lsman = lsman
        self.clman = clman

        TEMP_1K = lsman.wait_for_next_1K_TEMP(time.time())
        TEMP_SORB = lsman.wait_for_next_SORB_TEMP(time.time())

        # get mean 1K temp and set upper bound for 1K temp
        self.TEMP_1K_upper_bound = self.get_mean_1K_temp() + settings['1K_THRESHOLD']
        logger.info(f'1K TEMP upper bound set to {self.TEMP_1K_upper_bound} K')

        '''2. on LakeShore controller: set ”heater range” to 4 W'''
        lsman.set_heater_range(Command(4, time.time()))
        logger.debug('heater range set to 4')

        ''' 3. set ”setpoint” for Tsorb to 15 K −> wait until T1K < 1.95 K  
            4. increase to 20 K wait again until T1K < 1.95 K               
                       ... 25 K ...                                         '''
        self.ramp_step(13.0)

        logger.info('Opening 1K valve')
        self.valve_1K.open_valve()
        logger.success('1K valve is open!')
        self.ask_for_confirm()

        for setpoint in range(14,26):
            self.ramp_step(setpoint)

        ''' 5. open 1K-valve on manifold and close sorb-valve (remember to open the 1K-valve before closing the 
            sorb-valve, they should never both be closed.)  '''

        logger.info('closing sorb valve!')
        self.valve_sorb.close_valve()
        logger.success('sorb valve closed!')
        self.ask_for_confirm()

        ''' 6. continue increasing the temperature increase to 30 K wait again until T1K < 1.95 K
                                                        ... 35 K ...                                '''
        for setpoint in range(26, 51):
            self.ramp_step(setpoint)

#        ''' 7. once T_sorb = 35 K is stable, set directly to 50 K setpoint'''
#        # store T_sorb of the last 60 measurements and check if it is always within TEMP_SORB_TOLERANCE of 35 K
#        last_60_SORB_TEMP = np.full(60, 1e7, dtype = float)
#        latest_timestamp = time.time()
#        while not all(abs(last_60_SORB_TEMP - 35.0) <= self.TEMP_SORB_TOLERANCE):
#            logger.trace(f'35 K stability condition not fullfilled yet, largest = {max(last_60_SORB_TEMP)}, smallest = {min(last_60_SORB_TEMP)}')
#            # move each entry one index up
#            last_60_SORB_TEMP[:-1] = last_60_SORB_TEMP[1:]
#            latest_sorb_measurement = lsman.wait_for_next_SORB_TEMP(latest_timestamp)
#
#            # store latest measurement into last index
#            last_60_SORB_TEMP[-1] = latest_sorb_measurement.value
#            latest_timestamp = latest_sorb_measurement.timestamp

        # set setpoint to 50 K
        logger.info('sorb reached 50 K')
        time.sleep(2700) # wait 45 minutes at T_SORB = 50 K

#        ''' 8. once Tsorb = 50 K is reached, set setpoint back to 12 K'''
#        # wait for SORB to reach setpoint 50 K
#        TEMP_SORB = lsman.wait_for_next_SORB_TEMP(time.time())
#        while TEMP_SORB.value < 50.0:
#            TEMP_SORB = lsman.wait_for_next_SORB_TEMP(TEMP_SORB.timestamp)
#        logger.info('reached 50 K sorb temp')

        # set setpoint to 12 K and heater range to 3 (400 mW)
        lsman.set_setpoint(Command(12.0, time.time()))
        lsman.set_heater_range(Command(3, time.time()))
        logger.info('heater range set to 3 and sorb setpoint to 12 K')

        # opening/closing valves
        logger.info('opening sorb valve')
        self.valve_sorb.open_valve()
        logger.info('sorb valve opened')
        self.ask_for_confirm()

        ''' 10. once Tsorb < 40K, open sorb-valve on manifold and close 1K-valve'''
        # wait for SORB to go under 40 K
        TEMP_SORB = lsman.wait_for_next_SORB_TEMP(time.time())
        while TEMP_SORB.value == -1 or TEMP_SORB.value >= 40.0:
            TEMP_SORB = lsman.wait_for_next_SORB_TEMP(TEMP_SORB.timestamp)
        logger.info('Sorb temp under 40 K')

        logger.info('closing 1K valve')
        self.valve_1K.close_valve()
        logger.info('1K valve closed')
        self.ask_for_confirm()

    def ramp_step(self, setpoint):
        '''
        ramps sorb to setpoint and waits till sorb reached that temp, also checks if 1K TEMP is < 1K_TEMP_upper_bound

        Arguments:
            - setpoint (float) : new setpoint

        Returns:
            None
        '''
        self.lsman.set_setpoint(Command(setpoint, time.time()))
        logger.info(f'sent request to change setpoint to {setpoint}')

        # wait for SORB to reach setpoint
        TEMP_SORB = self.lsman.wait_for_next_SORB_TEMP(time.time())
        while abs(TEMP_SORB.value - setpoint) > settings['TEMP_SORB_TOLERANCE']:
            TEMP_SORB = self.lsman.wait_for_next_SORB_TEMP(TEMP_SORB.timestamp)
        logger.debug(f'sorb reached setpoint={setpoint}')

        # wait for 1K to go under TEMP_1K_upper_bound
        TEMP_1K = self.lsman.wait_for_next_1K_TEMP(time.time())
        while TEMP_1K.value < 0 or TEMP_1K.value >= self.TEMP_1K_upper_bound:
            TEMP_1K = self.lsman.wait_for_next_1K_TEMP(TEMP_1K.timestamp)
        logger.debug(f'1K TEMP under {self.TEMP_1K_upper_bound} K ')
        return

    def ask_for_confirm(self):
        confirmation = ''
        while confirmation != 'confirm':
            confirmation = input('Type confirm to confirm that both valves are open:')

    def get_mean_1K_temp(self):
        logger.debug(f'Averaging 1K TEMP over {settings["1K_AVERAGING_DURATION"]} measurements...')
        # generate array buffering 1K Temps
        measurement_buffer = np.full(settings['1K_AVERAGING_DURATION'], -1, dtype = float)
        latest_1K_timestamp = time.time()
        while not np.all(measurement_buffer > 0):
            measurement_buffer[:-1] = measurement_buffer[1:]
            latest_1K_measurement = self.lsman.wait_for_next_1K_TEMP(latest_1K_timestamp)
            measurement_buffer[-1] = latest_1K_measurement.value
            latest_1K_timestamp = latest_1K_measurement.timestamp

        mean_value = np.mean(measurement_buffer)
        logger.trace(f'calculated mean 1K Temp = {mean_value} K')
        return mean_value



if __name__ == '__main__':

    logger.configure(extra={"component": "execute"})
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[component]: <22}</cyan> | "
        "<level>{message}</level>"
    )
    # setup logger
    Path("logs").mkdir(parents=True, exist_ok=True)
    # create log file
    logger.remove()
    logger.add(
        "logs/execute.log",
        format = log_format,
        level='TRACE',
        rotation="100 MB",
        retention="14 days",
        compression="zip",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
    # create console log output
    logger.add(
        sys.stderr,
        format = log_format,
        level = 'DEBUG',
        colorize = True
    )

    # initiate manager objects
    logger.debug('initiating manager objects')
    lsman = Lakeshore340Manager()
    clman = LogClientManager()
    condense_sequence = CondenseSequence()
    # initiate threads
    logger.debug('initiating manager threads')
    lsman_thread = threading.Thread(target = lsman.measurement_loop, args = (clman,))
    clman_thread = threading.Thread(target = clman.logger_loop, args = (lsman,))
    # start threads
    logger.debug('starting manager threads')
    lsman_thread.start()
    clman_thread.start()
    


    try:
        while True:
            commandline_input = input("Type condense to start condense:")
            if commandline_input.strip().lower() == "condense":
                condense_thread = threading.Thread(
                    target=condense_sequence.run,
                    args=(lsman, clman),
                    name="CondenseSequence",
                )
                condense_thread.start()
                condense_thread.join()

    except KeyboardInterrupt:
        logger.warning("Keyboard interrupt received, shutting down")
        lsman.kill()
        clman.kill()

        lsman_thread.join()
        clman_thread.join()

        logger.info("All manager threads stopped")
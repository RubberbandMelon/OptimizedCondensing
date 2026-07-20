import threading
import time
import numpy
from dataclasses import dataclass 
import queue

@dataclass
class Measurement:
    value: float
    timestamp: float 

@dataclass
class SetpointCommand:
    setpoint : float
    timestamp : float


class SimulatedDevice:
    def __init__(self):
        self.measurement = Measurement(value = 0, timestamp = time.time())
        self.setpoint = 0
        self.new_setpoint = 0
        self.lock = threading.Lock()
        self.change_setpoint_event = threading.Event()
        self.kill_event = threading.Event()

        self.command_queue = queue.Queue()

        self.measurement_condition = threading.Condition()

    def measurement_loop(self):
        while not self.kill_event.is_set():

            with self.measurement_condition:
                new_measurement = Measurement(value = self.measurement.value + 1, timestamp = time.time())
                self.measurement = new_measurement
                self.measurement_condition.notify_all()
                print(f'Device: \tvalue={new_measurement.value},\t setpoint = {self.setpoint}')

            if self.change_setpoint_event.is_set():
                self.setpoint = self.new_setpoint
                self.change_setpoint_event.clear()

            time.sleep(1)

    def wait_for_next_measurement(self, last_timestamp):
        with self.measurement_condition:
            self.measurement_condition.wait_for(lambda: self.measurement.timestamp > last_timestamp or self.kill_event.is_set())
            return self.measurement

    def set_setpoint(self, setpoint_command : SetpointCommand):
        self.new_setpoint = setpoint_command.setpoint
        print(f"Device: \tReceived Command to change setpoint to {self.new_setpoint}")
        self.change_setpoint_event.set()

    def kill(self):
        self.kill_event.set()

class SimulatedSequence:
    def __init__(self, device):
        self.device = device
        self.kill_event = threading.Event()

    def start_sequence(self):
        print('Sequence:\tStarted sequence!')
        last_timestamp = time.time()
        while not self.kill_event.is_set():
            latest_measurement = self.device.wait_for_next_measurement(last_timestamp)
            print(f'Sequence: \tNew Measurement! with value = {latest_measurement.value}')
            last_timestamp = latest_measurement.timestamp

            if latest_measurement.value == 10:
                self.device.set_setpoint(SetpointCommand(setpoint = 2, timestamp = time.time()))
    
    def kill(self):
        self.kill_event.set()



if __name__ == '__main__':
    device = SimulatedDevice()
    sequence = SimulatedSequence(device)
    device_thread = threading.Thread(target = device.measurement_loop, args = ())
    sequence_thread = threading.Thread(target = sequence.start_sequence, args = ())
    print('Main: \t\tCreated Device')
    device_thread.start()
    print('Main: \t\tStarted Started Measuring on device')
    input("\nMain: \t\tPress Enter key to start sequence...\n")
    sequence_thread.start()
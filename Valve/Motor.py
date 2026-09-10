import time
import math
import RPi.GPIO as GPIO
from loguru import logger


INITIALIZE_GAP = 200e-3     # 200 milliseconds, mandatory t1 time
DIR_PULSE_GAP = 10e-6       # 10 microseconds, mandatory t2 time

class Motor:
    """
    Motor class

    Usage:
        construct object
        init()
        turn(degrees)
        cleanup()
    """

    def __init__(self, pulse_pin, dir_pin, enable_pin, pulses_per_rev, name = None):

        #Use BCM GPIO numbering
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # define variables
        self.pulse_pin = pulse_pin
        self.dir_pin = dir_pin
        self.enable_pin = enable_pin
        self.pulses_per_rev = pulses_per_rev

        # GPIO setup
        GPIO.setup(self.pulse_pin, GPIO.OUT)
        GPIO.setup(self.dir_pin, GPIO.OUT)
        GPIO.setup(self.enable_pin, GPIO.OUT)
        GPIO.output(self.pulse_pin, GPIO.LOW)
        GPIO.output(self.dir_pin, GPIO.LOW)
        GPIO.output(self.enable_pin, GPIO.HIGH) # disable driver

        if name is not None:
            self.logger = logger.bind(component=f"Motor_{name}")
        else:
            self.logger = logger.bind(component="Motor")

        self.logger.debug(f"Motor initialized with {self.pulses_per_rev} pulses per revolution")

        time.sleep(INITIALIZE_GAP)  

    def turn(self, degree, revs_per_second):
        if revs_per_second <= 0:
            self.logger.error(f"revs_per_second must be greater than zero, given={revs_per_second}")
            raise ValueError(f"revs_per_second must be greater than zero, given={revs_per_second}")

        number_of_pulses = abs(round(self.pulses_per_rev * degree / 360.0))
        pulse_frequency = self.pulses_per_rev * revs_per_second

        # speed check
        if pulse_frequency > 5e5:
            self.logger.error(f'chosen pulse frequency is too fast! given={pulse_frequency} Hz, maximum=500 kHz')
            return
        
        half_pulse_duration = 1/(2*pulse_frequency)

        # enable driver
        GPIO.output(self.enable_pin, GPIO.LOW)
        time.sleep(0.2)

        # turn direction
        if degree > 0:
            GPIO.output(self.dir_pin, GPIO.HIGH)
        else:
            GPIO.output(self.dir_pin, GPIO.LOW)
        time.sleep(DIR_PULSE_GAP)  

        self.logger.trace('motor starts turning...')
        for _ in range(number_of_pulses):
            GPIO.output(self.pulse_pin, GPIO.HIGH)
            time.sleep(half_pulse_duration)

            GPIO.output(self.pulse_pin, GPIO.LOW)
            time.sleep(half_pulse_duration)
        self.logger.trace('motor turn complete!')

        # disable driver
        time.sleep(0.2)
        GPIO.output(self.enable_pin, GPIO.HIGH)

    def cleanup(self):
        GPIO.output(self.enable_pin, GPIO.LOW)
        self.logger.debug('Motor was shut down')

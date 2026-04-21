import time
import math
import RPi.GPIO as GPIO

class Motor:
    """
    Motor class

    Usage:
        construct object
        init()
        turn(degrees)
        cleanup()
    """

    def __init__(self, pulse_pin, dir_pin, enable_pin, pulses_per_rev):

        #Use BCM GPIO numbering
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)


        self.pulse_pin = pulse_pin
        self.dir_pin = dir_pin
        self.enable_pin = enable_pin
        self.pulses_per_rev = pulses_per_rev

    def init(self):
        GPIO.setup(self.pulse_pin, GPIO.OUT)
        GPIO.setup(self.dir_pin, GPIO.OUT)
        GPIO.setup(self.enable_pin, GPIO.OUT)

        GPIO.output(self.pulse_pin, GPIO.LOW)
        GPIO.output(self.dir_pin, GPIO.LOW)

        GPIO.output(self.enable_pin, GPIO.HIGH)
        time.sleep(200e-6)  # 200 microseconds, mandatory t1 time

    def turn(self, degree):
        number_of_pulses = abs(round(self.pulses_per_rev * degree / 360.0))

        if degree < 0:
            GPIO.output(self.dir_pin, GPIO.HIGH)
        else:
            GPIO.output(self.dir_pin, GPIO.LOW)

        time.sleep(10e-6)  # 10 microseconds, mandatory t2 time

        for _ in range(number_of_pulses):
            GPIO.output(self.pulse_pin, GPIO.HIGH)
            time.sleep(5e-6)  # 5 microseconds, mandatory t3 time

            GPIO.output(self.pulse_pin, GPIO.LOW)
            time.sleep(1000e-6)  # 1000 microseconds, mandatory t4 time

    def cleanup(self):
        GPIO.output(self.enable_pin, GPIO.LOW)

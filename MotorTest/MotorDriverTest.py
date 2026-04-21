#!/usr/bin/env python3

import time
import math
import RPi.GPIO as GPIO

import Motor

# pulse = GPIO23, dir = GPIO24, enable = GPIO25
motor1 = Motor.Motor(23, 24, 25, 800)

def main():
    print("starting script...")

    motor1.init()
    print("motor1 initialization complete!")

    try:
        while True:
            user_input = input("Enter degrees to turn: ")

            try:
                degrees = float(user_input)
            except ValueError:
                print("Invalid input. Enter a number.")
                continue

            motor1.turn(degrees)
            print(f"Motor turned {degrees} degrees")

    except KeyboardInterrupt:
        print("\nStopping script...")

    finally:
        motor1.cleanup()
        GPIO.cleanup()
        print("GPIO cleaned up.")


if __name__ == "__main__":
    main()

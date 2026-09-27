import time
import sys
from pathlib import Path

from loguru import logger

from .Valve import Valve
from .CalibrationManager import CalibrationManager


# =========================================================
# Settings
# =========================================================

VALVE_SORB_PULSE = 4
VALVE_SORB_DIR = 27
VALVE_SORB_ENA = 22
VALVE_SORB_CHANNEL = 8

VALVE_1K_PULSE = 5
VALVE_1K_DIR = 6
VALVE_1K_ENA = 13
VALVE_1K_CHANNEL = 7

ADC_ADDRESSES = (0x68, 0x69)

POTI_POWER = 19

MOTOR_REVS_PER_SECOND = 800


# =========================================================
# Main
# =========================================================

def main():

    logger.info("Starting valve test")

    calibration = CalibrationManager(
        Path(__file__).parent / "calibration.json"
    )

    cal = calibration.get()

    logger.info(
        f"Loaded calibration:\n{cal}"
    )


    # -----------------------------------------------------
    # Create valves
    # -----------------------------------------------------

    valve_sorb = Valve(
        name="VALVE_SORB",

        pulse_pin=VALVE_SORB_PULSE,
        dir_pin=VALVE_SORB_DIR,
        enable_pin=VALVE_SORB_ENA,

        CHANNEL=VALVE_SORB_CHANNEL,

        ADC_ADRESSES=ADC_ADDRESSES,
        power_pin=POTI_POWER,

        valve_OPEN=cal["sorb"]["open"],
        valve_CLOSED=cal["sorb"]["closed"],
    )


    valve_1K = Valve(
        name="VALVE_1K",

        pulse_pin=VALVE_1K_PULSE,
        dir_pin=VALVE_1K_DIR,
        enable_pin=VALVE_1K_ENA,

        CHANNEL=VALVE_1K_CHANNEL,

        ADC_ADRESSES=ADC_ADDRESSES,
        power_pin=POTI_POWER,

        adc=valve_sorb.ad_converter,

        valve_OPEN=cal["1k"]["open"],
        valve_CLOSED=cal["1k"]["closed"],
    )


    valve_sorb.link_other_valve(valve_1K)
    valve_1K.link_other_valve(valve_sorb)


    logger.info("Valve objects initialized")


    # -----------------------------------------------------
    # First switch:
    #
    # SORB OPEN
    # 1K CLOSED
    #
    # ->
    #
    # 1K OPEN
    # SORB CLOSED
    #
    # -----------------------------------------------------

    logger.warning(
        "Switching valves: opening 1K valve"
    )
#    while True:
        #print("1K ADC:", id(valve_1K.poti.adc))
        #print("SORB ADC:", id(valve_sorb.poti.adc))

        #print("1K channel:", valve_1K.poti.CHANNEL)
        #print("SORB channel:", valve_sorb.poti.CHANNEL)
        #print(f'2V: {valve_sorb.poti.convert_voltages_to_positions(2)}\n0V: {valve_sorb.poti.convert_voltages_to_positions(0)}')
        #print(f'SORB: {valve_sorb.poti.read_voltage()}')
        #print(f'1K: {valve_1K.poti.read_voltage()}\n')

        #voltage_sorb = valve_sorb.poti.read_voltage()
        #position_sorb = valve_sorb.poti.convert_voltages_to_positions(voltage_sorb)
        #voltage_1K = valve_1K.poti.read_voltage()
        #position_1K = valve_1K.poti.convert_voltages_to_positions(voltage_1K)
        #print(f'SORB: \t{voltage_sorb:.3f} V, \tpos = {valve_sorb.poti.convert_voltages_to_positions(voltage_sorb):.3f}, \tis open? {valve_sorb.is_open(mute = True)}, is closed? {valve_sorb.is_closed(mute=False)}')
        #print(f'1K: \t{voltage_1K:.3f} V, \tpos = {valve_1K.poti.convert_voltages_to_positions(voltage_1K):.3f}, \tis open? {valve_1K.is_open(mute = True)}, is closed? {valve_1K.is_closed(mute=False)}\n')

        #print("CH7:", valve_sorb.poti.adc.read_voltage(7))
        #print("CH7:", valve_sorb.poti.adc.read_voltage(7))
        #print("CH8:", valve_sorb.poti.adc.read_voltage(8))
        #print("CH8:", valve_sorb.poti.adc.read_voltage(8))
        #print('')

#        print(f'SORB\tis open? {valve_sorb.is_open()}, \tis closed? {valve_sorb.is_closed()}\n1K\tis open? {valve_1K.is_open()}, \tis closed? {valve_1K.is_closed()}\n')
#        time.sleep(1)

    valve_1K.open_valve()

    print(f'SORB: {valve_sorb.poti.get_position():.3f}, \n1K: {valve_1K.poti.get_position():.3f}')

    logger.warning(
        "Switching valves: closing SORB valve"
    )
    print(f'SORB: {valve_sorb.poti.get_position():.3f}, \n1K: {valve_1K.poti.get_position():.3f}')

    valve_sorb.close_valve(
    )
    print(f'SORB: {valve_sorb.poti.get_position():.3f}, \n1K: {valve_1K.poti.get_position():.3f}')


    logger.success(
        "Valves switched:"
        " SORB CLOSED, 1K OPEN"
    )
    print(f'SORB: {valve_sorb.poti.get_position():.3f}, \n1K: {valve_1K.poti.get_position():.3f}')


    time.sleep(10)


    # -----------------------------------------------------
    # Second switch:
    #
    # SORB CLOSED
    # 1K OPEN
    #
    # ->
    #
    # SORB OPEN
    # 1K CLOSED
    #
    # -----------------------------------------------------

    logger.warning(
        "Returning valves: opening SORB valve"
    )
    print(f'SORB: {valve_sorb.poti.get_position():.3f}, \n1K: {valve_1K.poti.get_position():.3f}')

    valve_sorb.open_valve(
    )
    print(f'SORB: {valve_sorb.poti.get_position():.3f}, \n1K: {valve_1K.poti.get_position():.3f}')


    logger.warning(
        "Returning valves: closing 1K valve"
    )
    print(f'SORB: {valve_sorb.poti.get_position():.3f}, \n1K: {valve_1K.poti.get_position():.3f}')

    valve_1K.close_valve(
    )
    print(f'SORB: {valve_sorb.poti.get_position():.3f}, \n1K: {valve_1K.poti.get_position():.3f}')


    logger.success(
        "Finished:"
        " SORB OPEN, 1K CLOSED"
    )
    print(f'SORB: {valve_sorb.poti.get_position():.3f}, \n1K: {valve_1K.poti.get_position():.3f}')


if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:

        logger.warning(
            "Interrupted by user"
        )

        sys.exit(1)

    except Exception:

        logger.exception(
            "Valve test failed"
        )

        sys.exit(1)

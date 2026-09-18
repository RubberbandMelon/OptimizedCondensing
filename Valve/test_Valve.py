import time
import sys
from pathlib import Path

from loguru import logger

from Valve import Valve
from CalibrationManager import CalibrationManager


# =========================================================
# Settings
# =========================================================

VALVE_SORB_PULSE = 5
VALVE_SORB_DIR = 6
VALVE_SORB_ENA = 22
VALVE_SORB_CHANNEL = 5

VALVE_1K_PULSE = 23
VALVE_1K_DIR = 24
VALVE_1K_ENA = 13
VALVE_1K_CHANNEL = 6

ADC_ADDRESSES = (0x68, 0x68)

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

    valve_1K.open_valve(
        override=True
    )


    logger.warning(
        "Switching valves: closing SORB valve"
    )

    valve_sorb.close_valve(
        override=True
    )


    logger.success(
        "Valves switched:"
        " SORB CLOSED, 1K OPEN"
    )


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

    valve_sorb.open_valve(
        override=True
    )


    logger.warning(
        "Returning valves: closing 1K valve"
    )

    valve_1K.close_valve(
        override=True
    )


    logger.success(
        "Finished:"
        " SORB OPEN, 1K CLOSED"
    )


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
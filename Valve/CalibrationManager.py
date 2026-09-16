import json
import threading
from pathlib import Path


DEFAULT_CALIBRATION = {
    "sorb": {
        "open": 2.0,
        "closed": 0.2,
    },
    "1k": {
        "open": 2.0,
        "closed": 0.2,
    },
}

class CalibrationManager:

    def __init__(self, filename="calibration.json"):
        self.path = Path(filename)
        self.lock = threading.Lock()

        self.data = self._load()


    def _load(self):

        if not self.path.exists():
            self._write(DEFAULT_CALIBRATION)
            return DEFAULT_CALIBRATION.copy()

        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)


    def _write(self, data):

        # write temporary file first
        temp_path = self.path.with_suffix(".tmp")

        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                indent=4
            )

        # replace old calibration only after write succeeded
        temp_path.replace(self.path)


    def get(self):

        with self.lock:
            return {
                valve: values.copy()
                for valve, values in self.data.items()
            }


    def get_valve(self, valve):

        with self.lock:
            return self.data[valve].copy()


    def set_value(self, valve, position, voltage):

        if valve not in ("sorb", "1k"):
            raise ValueError(f"Unknown valve: {valve}")

        if position not in ("open", "closed"):
            raise ValueError(f"Unknown calibration position: {position}")

        voltage = float(voltage)

        if not 0 <= voltage <= 2.048:
            raise ValueError(
                f"Calibration voltage outside ADC range: {voltage} V"
            )

        with self.lock:

            new_data = {
                name: values.copy()
                for name, values in self.data.items()
            }

            new_data[valve][position] = voltage

            open_voltage = new_data[valve]["open"]
            closed_voltage = new_data[valve]["closed"]

            if abs(open_voltage - closed_voltage) < 0.05:
                raise ValueError(
                    "OPEN and CLOSED calibration are too close together"
                )

            self._write(new_data)
            self.data = new_data

        return voltage

    def set_all(self, calibration):

        sorb_open = float(calibration["sorb"]["open"])
        sorb_closed = float(calibration["sorb"]["closed"])

        one_k_open = float(calibration["1k"]["open"])
        one_k_closed = float(calibration["1k"]["closed"])

        # plausibility checks

        for voltage in (
            sorb_open,
            sorb_closed,
            one_k_open,
            one_k_closed
        ):
            if not 0 <= voltage <= 2.048:
                raise ValueError(
                    f"Calibration voltage outside ADC range: {voltage}"
                )

        if abs(sorb_open - sorb_closed) < 0.05:
            raise ValueError(
                "SORB OPEN and CLOSED calibration too close"
            )

        if abs(one_k_open - one_k_closed) < 0.05:
            raise ValueError(
                "1K OPEN and CLOSED calibration too close"
            )

        new_data = {
            "sorb": {
                "open": sorb_open,
                "closed": sorb_closed
            },
            "1k": {
                "open": one_k_open,
                "closed": one_k_closed
            }
        }

        with self.lock:
            self._write(new_data)
            self.data = new_data



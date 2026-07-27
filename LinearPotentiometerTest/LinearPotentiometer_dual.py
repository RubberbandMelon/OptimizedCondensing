from ADCDifferentialPi import ADCDifferentialPi
import time

class LinearPotentiometer:
    '''
    LinearPotentiometer class for the Optimized Condense. KTP-10-L will be used.

    Calibration advice: 
    - The ADC only measures voltages between 0 and 2.048 V.
    - Set OPEN to a value, where you are happy with the openness of the valve.
    - Set CLOSE to a value, where you are happy with the closedness of the valve.
    - Position is dimensioned as 0 = your CLOSED voltage, 1 = your OPEN voltage, and values in between are linearly interpolated.
    '''
    
    def __init__(self, init_dict = {
        "ADC_ADDRESS_1":    0x68,   # I2C address of the ADC Differential Pi board
        "ADC_ADDRESS_2":    0x68,   # the chip on 0x69 is broken, only use channel 5-8 !
        "linear_poti1_CHANNEL":   5,      # channel on which Linear Poti 1 is connected
        "linear_poti2_CHANNEL":   6,      # channel on which Linear Poti 2 is connected
        "valve1_OPEN":      0.0,    # calibration: voltage reading when valve 1 is open
        "valve1_CLOSE":     2.0,    # calibration: voltage reading when valve 1 is closed
        "valve2_OPEN":      0.0,    # calibration: voltage reading when valve 2 is open
        "valve2_CLOSE":     2.0     # calibration: voltage reading when valve 2 is closed
    
    }):
        self.ADC_ADDRESS_1 = init_dict["ADC_ADDRESS_1"]
        self.ADC_ADDRESS_2 = init_dict["ADC_ADDRESS_2"]
        self.linear_poti1_CHANNEL = init_dict["linear_poti1_CHANNEL"]
        self.linear_poti2_CHANNEL = init_dict["linear_poti2_CHANNEL"]
        self.valve1_OPEN = init_dict["valve1_OPEN"]
        self.valve1_CLOSE = init_dict["valve1_CLOSE"]   
        self.valve2_OPEN = init_dict["valve2_OPEN"]
        self.valve2_CLOSE = init_dict["valve2_CLOSE"]

        self.adc = ADCDifferentialPi(self.ADC_ADDRESS_1, self.ADC_ADDRESS_2)
        
    def read_voltages(self, channel):
        voltage = self.adc.read_voltage(channel)
        print(f"Voltage reading from channel {channel}: {voltage} V")
        return voltage
    
    def convert_voltages_to_positions(self, voltage, valve_open, valve_close):
        span = valve_open - valve_close
        position = (voltage - valve_close) / span
        return position
        
    def get_positions(self):
        voltage1 = self.read_voltages(self.linear_poti1_CHANNEL)
        voltage2 = self.read_voltages(self.linear_poti2_CHANNEL)

        position1 = self.convert_voltages_to_positions(voltage1, self.valve1_OPEN, self.valve1_CLOSE)
        position2 = self.convert_voltages_to_positions(voltage2, self.valve2_OPEN, self.valve2_CLOSE)

        return position1, position2


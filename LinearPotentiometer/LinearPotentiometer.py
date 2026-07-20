from ADCDifferentialPi import ADCDifferentialPi
import time

class LinearPotentiometer:
    '''
    LinearPotentiometer class for the Optimized Condense on the Unisoku 1300. Potis of type KTP-10-L will be used.

    Calibration advice: 
    - The ADC only measures voltages between 0 and 2.048 V. Build a voltage divider acordingly
    - Set valveX_OPEN to a value, where you are happy with the openness of the valve.
    - Set valveX_CLOSE to a value, where you are happy with the closedness of the valve.
    - Position is dimensioned as 0 = your CLOSED voltage, 1 = your OPEN voltage, and values in between are linearly interpolated.
    
    CODE ADVICSE:
    - for better stability, use a single instance of the ADC object by passing it to the next LinaerPotentiometer object you define
    - you can get said adc object from your first LinearPotentiometer instance with 'linear_potentiometer.adc'

    author: Simon Kloos, Institute for Functional Matter and Quantum Technologies, University of Stuttgart, Germany
    created: 2024-07-08
    last-updated: 2026-07-15
    '''
    
    def __init__(
        self, 
        adc = None,                     # if you aleady have on LinearPotentiometer object, you can pass the adc object to the next one to avoid multiple instances of the ADC class
        ADC_ADRESSES = (0x68, 0x68),    # I2C address of the ADC Differential Pi board. the chip on 0x69 is broken, only use channel 5-8 !
        CHANNEL = 5,        # channel on which Linear Poti 1 is connected
        valve_OPEN = 0.0,               # calibration: voltage reading when valve 1 is open
        valve_CLOSED = 2.0,             # calibration: voltage reading when valve 1 is closed
    ):
        self.ADC_ADDRESS_1 = ADC_ADRESSES[0]
        self.ADC_ADDRESS_2 = ADC_ADRESSES[1]
        self.CHANNEL = CHANNEL
        self.valve_OPEN = valve_OPEN
        self.valve_CLOSE = valve_CLOSED

        if adc is None:
            self.adc = ADCDifferentialPi(self.ADC_ADDRESS_1, self.ADC_ADDRESS_2)
        else:
            self.adc = adc

    def read_voltages(self, mute = True):
        voltage = self.adc.read_voltage(self.CHANNEL)
        if not mute:
            print(f"Voltage reading from channel {self.CHANNEL}: {voltage:.3f} V")
        return voltage
    
    def convert_voltages_to_positions(self):
        span = self.valve_OPEN - self.valve_CLOSE
        position = (self.voltage - self.valve_CLOSE) / span
        return position
        
    def get_positions(self, mute = True):
        voltage = self.read_voltages(mute = True)
        position = self.convert_voltages_to_positions(voltage)
        print(f"Position of ADC CHANNEL {self.CHANNEL}: {position:.3f} at {voltage:.3f} V.")
        return position


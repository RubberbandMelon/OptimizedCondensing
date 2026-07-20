from LinearPotentiometer import LinearPotentiometer
import time

def test_linear_potentiometer():
    # Create an instance of the LinearPotentiometer class
    linear_pot_CH5 = LinearPotentiometer(
        ADC_ADRESSES=(0x68, 0x68),
        CHANNEL=5,
        valve_OPEN=0.0,
        valve_CLOSED=2.0
    )
    linear_pot_CH6 = LinearPotentiometer(
        ADC_ADRESSES=(0x68, 0x68),
        CHANNEL=6,
        valve_OPEN=0.0,
        valve_CLOSED=1.0,
        adc = linear_pot_CH5.adc  # Use the same ADC instance for both potentiometers
    )

    # Read voltages and positions multiple times
    while True:
        position_CH5 = linear_pot_CH5.get_positions(mute=False)
        position_CH6 = linear_pot_CH6.get_positions(mute=False)
        print(f"Position CH5: {position_CH5:.3f} at {linear_pot_CH5.voltage:.3f} V\nPosition CH6: {position_CH6:.3f} at {linear_pot_CH6.voltage:.3f} \n")
        time.sleep(1)  # Wait for 1 second before the next reading
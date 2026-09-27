from smbus2 import SMBus, i2c_msg
import time


def read_channel(bus, address, channel):

    # One-shot, 12-bit, PGA x1
    #
    # CH1 = 00
    # CH2 = 01
    # CH3 = 10
    # CH4 = 11

    config = 0x80 | ((channel - 1) << 5)

    print(f"    writing config 0x{config:02X}", flush=True)

    # Start one-shot conversion
    bus.write_byte(address, config)

    # 12-bit conversion takes ~4.17 ms
    time.sleep(0.005)

    while True:

        msg = i2c_msg.read(address, 3)
        bus.i2c_rdwr(msg)

        data = list(msg)

        # Third byte is configuration
        returned_config = data[2]

        if not (returned_config & 0x80):
            break

        time.sleep(0.001)

    # 12-bit signed result
    raw = ((data[0] & 0x0F) << 8) | data[1]

    if raw & 0x800:
        raw -= 0x1000

    voltage = raw * 0.001

    return voltage, returned_config


with SMBus(1) as bus:

    for address in (0x68, 0x69):

        print(f"\n=== ADC 0x{address:02X} ===")

        for channel in range(1, 5):

            print(
                f"Reading ADC 0x{address:02X}, "
                f"CH{channel}...",
                flush=True
            )

            try:
                voltage, config = read_channel(
                    bus,
                    address,
                    channel
                )

                print(
                    f"CH{channel}: "
                    f"{voltage:.4f} V, "
                    f"returned config=0x{config:02X}"
                )

            except Exception as e:

                print(
                    f"ERROR: {type(e).__name__}: {e}"
                )

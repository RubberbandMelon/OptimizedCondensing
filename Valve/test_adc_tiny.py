from smbus2 import SMBus, i2c_msg
import time

with SMBus(1) as bus:

    address = 0x68

    print("starting conversion", flush=True)
    bus.write_byte(address, 0x80)

    start = time.monotonic()

    while True:
        msg = i2c_msg.read(address, 3)
        bus.i2c_rdwr(msg)

        data = list(msg)

        elapsed = time.monotonic() - start

        print(
            f"{elapsed:.3f} s: {data}",
            flush=True
        )

        # RDY = 0 -> conversion complete
        if not (data[2] & 0x80):
            print("CONVERSION READY")
            break

        if elapsed > 2:
            print("TIMEOUT")
            break

        time.sleep(0.01)

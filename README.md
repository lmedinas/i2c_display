# I2C Display Hello World

Small Python program for a common HD44780-compatible LCD with an I2C backpack.

If the text is longer than the display width, it scrolls automatically.

## Files

- `hello_i2c_display.py` prints `Hello World` on the first line.

## Install

```bash
sudo apt install python3-smbus
```

Or, if you prefer, install the fallback module:

```bash
pip install smbus2
```

On Raspberry Pi or similar Linux systems, also make sure I2C is enabled.

## Run

```bash
python3 hello_i2c_display.py
```

You can also set the bus, address, or text explicitly:

```bash
python3 hello_i2c_display.py --bus 1 --address 0x27 --text "Hello World"
```

Show a blinking heart on the second line:

```bash
python3 hello_i2c_display.py --blink-heart --text "Hello World"
```

Blink the whole display on and off:

```bash
python3 hello_i2c_display.py --blink-display --text "Hello World"
```

## Notes

- The script uses I2C bus `1` by default.
- If no address is provided, it tries `0x27` and `0x3F`.
- Long text scrolls across the first line automatically.
- If your display still does not respond, check the real address with `i2cdetect -y 1`.

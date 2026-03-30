# I2C Display program build for my Raspberry PI.

Small Python program for a common HD44780-compatible LCD with an I2C backpack.

If the text is longer than the display width, it scrolls automatically.
You can optionally show the current time on line 4 in `HH:MM:SS` format.

## Files

- `funny_i2c_display.py` prints `Hello World` on the first line.
- It can also update the fourth line with the current time.

## Install (using Raspberry Pi OS)

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
python3 funny_i2c_display.py
```

You can also set the bus, address, or text explicitly:

```bash
python3 funny_i2c_display.py --bus 1 --address 0x27 --text "Hello World"
```

Show the time on the fourth line:

```bash
python3 funny_i2c_display.py --text "Hello World" --show-time
```

Show a blinking heart on the second line:

```bash
python3 funny_i2c_display.py --blink-heart --text "Hello World"
```

Blink the whole display on and off:

```bash
python3 funny_i2c_display.py --blink-display --text "Hello World"
```

Check help command for more information:

```bash
python3 funny_i2c_display.py --help
```

## Notes

- The script uses I2C bus `1` by default.
- If no address is provided, it tries `0x27` and `0x3F`.
- Long text scrolls across the first line automatically.
- `--show-time` enables a live clock on the fourth line in `HH:MM:SS` format.
- The fourth line uses 20x4-style LCD addressing.
- If your display still does not respond, check the real address with `i2cdetect -y 1`.

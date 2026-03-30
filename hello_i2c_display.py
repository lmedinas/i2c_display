#!/usr/bin/env python3
"""Show 'Hello World' on a common HD44780 I2C LCD."""

import argparse
from time import sleep

try:
    from smbus import SMBus
except ImportError:
    try:
        from smbus2 import SMBus
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: smbus or smbus2\n"
            "Install one of them before running the script."
        ) from exc


LCD_WIDTH = 16
LCD_CHR = 1
LCD_CMD = 0

LCD_LINE_1 = 0x80
LCD_LINE_2 = 0xC0
LCD_CGRAM = 0x40

LCD_BACKLIGHT = 0x08
ENABLE = 0x04

E_PULSE = 0.0005
E_DELAY = 0.0005
HEART_CHAR = chr(0)


class I2cLcd:
    def __init__(self, bus_id: int = 1, address: int = 0x27) -> None:
        try:
            self.bus = SMBus(bus_id)
        except FileNotFoundError as exc:
            raise SystemExit(
                f"I2C bus /dev/i2c-{bus_id} was not found.\n"
                "Enable I2C first, or pass the correct bus with --bus."
            ) from exc
        self.address = address
        self._init_display()

    def _write_byte(self, data: int) -> None:
        self.bus.write_byte(self.address, data | LCD_BACKLIGHT)

    def _toggle_enable(self, data: int) -> None:
        sleep(E_DELAY)
        self._write_byte(data | ENABLE)
        sleep(E_PULSE)
        self._write_byte(data & ~ENABLE)
        sleep(E_DELAY)

    def _send(self, bits: int, mode: int) -> None:
        high = mode | (bits & 0xF0)
        low = mode | ((bits << 4) & 0xF0)

        self._write_byte(high)
        self._toggle_enable(high)
        self._write_byte(low)
        self._toggle_enable(low)

    def _init_display(self) -> None:
        for command in (0x33, 0x32, 0x06, 0x0C, 0x28, 0x01):
            self._send(command, LCD_CMD)
        sleep(E_DELAY)

    def write_line(self, text: str, line: int) -> None:
        self._send(line, LCD_CMD)
        formatted = text.ljust(LCD_WIDTH)[:LCD_WIDTH]
        for char in formatted:
            self._send(ord(char), LCD_CHR)

    def create_char(self, location: int, pattern: list[int]) -> None:
        location &= 0x07
        self._send(LCD_CGRAM | (location << 3), LCD_CMD)
        for row in pattern[:8]:
            self._send(row, LCD_CHR)

    def clear(self) -> None:
        self._send(0x01, LCD_CMD)
        sleep(E_DELAY)

    def display_on(self) -> None:
        self._send(0x0C, LCD_CMD)

    def display_off(self) -> None:
        self._send(0x08, LCD_CMD)

    def close(self) -> None:
        self.clear()
        self.bus.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bus", type=int, default=1, help="I2C bus number, default: 1")
    parser.add_argument(
        "--address",
        type=lambda value: int(value, 0),
        default=None,
        help="I2C device address, e.g. 0x27 or 0x3F",
    )
    parser.add_argument(
        "--text",
        default="Hello World",
        help="Text to display on the first line",
    )
    parser.add_argument(
        "--blink-heart",
        action="store_true",
        help="Blink a custom heart on the second line until interrupted",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Blink interval in seconds, default: 0.5",
    )
    parser.add_argument(
        "--blink-display",
        action="store_true",
        help="Blink the whole display on and off until interrupted",
    )
    return parser.parse_args()


def detect_address(bus_id: int) -> int:
    candidates = (0x27, 0x3F)
    try:
        bus = SMBus(bus_id)
    except FileNotFoundError as exc:
        raise SystemExit(
            f"I2C bus /dev/i2c-{bus_id} was not found.\n"
            "Enable I2C first, or pass the correct bus with --bus."
        ) from exc

    try:
        for address in candidates:
            try:
                bus.write_quick(address)
                return address
            except OSError:
                continue
    finally:
        bus.close()

    raise SystemExit(
        "No LCD found at the common I2C addresses 0x27 or 0x3F.\n"
        "Run i2cdetect to find the correct address and pass it with --address."
    )


def scroll_frames(text: str) -> list[str]:
    if len(text) <= LCD_WIDTH:
        return [text]

    padded = f"{text}{' ' * LCD_WIDTH}"
    return [padded[index:index + LCD_WIDTH] for index in range(len(padded) - LCD_WIDTH + 1)]


def scroll_text(lcd: I2cLcd, text: str, line: int, interval: float) -> None:
    frames = scroll_frames(text)
    if len(frames) == 1:
        lcd.write_line(text, line)
        return

    while True:
        for frame in frames:
            lcd.write_line(frame, line)
            sleep(interval)


def blink_heart(lcd: I2cLcd, text: str, interval: float) -> None:
    heart_pattern = [
        0b00000,
        0b01010,
        0b11111,
        0b11111,
        0b11111,
        0b01110,
        0b00100,
        0b00000,
    ]
    lcd.create_char(0, heart_pattern)
    frames = scroll_frames(text)
    frame_index = 0

    while True:
        lcd.write_line(frames[frame_index], LCD_LINE_1)
        lcd.write_line(f"   {HEART_CHAR}   :)", LCD_LINE_2)
        sleep(interval)
        lcd.write_line(frames[frame_index], LCD_LINE_1)
        lcd.write_line("        :)", LCD_LINE_2)
        sleep(interval)
        frame_index = (frame_index + 1) % len(frames)


def blink_display(lcd: I2cLcd, text: str, interval: float) -> None:
    frames = scroll_frames(text)

    while True:
        for frame in frames:
            lcd.write_line(frame, LCD_LINE_1)
            lcd.write_line("", LCD_LINE_2)
            lcd.display_on()
            sleep(interval)
            lcd.display_off()
            sleep(interval)


def main() -> None:
    args = parse_args()
    address = args.address if args.address is not None else detect_address(args.bus)
    lcd = I2cLcd(bus_id=args.bus, address=address)
    try:
        if args.blink_heart:
            blink_heart(lcd, args.text, args.interval)
        elif args.blink_display:
            blink_display(lcd, args.text, args.interval)
        else:
            lcd.write_line("", LCD_LINE_2)
            scroll_text(lcd, args.text, LCD_LINE_1, args.interval)
    except KeyboardInterrupt:
        lcd.display_on()
        lcd.clear()
    finally:
        lcd.close()


if __name__ == "__main__":
    main()

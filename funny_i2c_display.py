import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
import time
from time import sleep, monotonic

LCD_WIDTH = 16
LCD_CHR = 1
LCD_CMD = 0

LCD_LINE_1 = 0x80
LCD_LINE_2 = 0xC0
LCD_LINE_3 = 0x94
LCD_LINE_4 = 0xD4
LCD_CGRAM = 0x40

LCD_BACKLIGHT = 0x08
ENABLE = 0x04

E_PULSE = 0.0005
E_DELAY = 0.0005
HEART_CHAR = chr(0)
COUNTDOWN_PATTERN = re.compile(r"^(\d+):([0-1]\d):([0-5]\d):([0-5]\d)$")


class I2cLcd:
    def __init__(self, bus_id: int = 1, address: int = 0x27) -> None:
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
    parser.add_argument(
        "--show-time",
        action="store_true",
        help="Show the current time on the fourth line",
    )
    parser.add_argument(
        "--uptime",
        action="store_true",
        help="Show system uptime on the fourth line",
    )
    parser.add_argument(
        "--show-tokens",
        action="store_true",
        help="Show Codex token percentage on the third line",
    )
    parser.add_argument(
        "--show-resources",
        action="store_true",
        help="Show CPU and RAM usage on the third line",
    )
    parser.add_argument(
        "--countdown",
        type=parse_countdown_arg,
        help="Countdown in DD:HH:MM:SS format",
    )
    return parser.parse_args()


def detect_address(bus_id: int) -> int:
    from smbus import SMBus
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


def format_time() -> str:
    now = datetime.now()
    return now.strftime("%H:%M:%S")


def parse_countdown_arg(value: str) -> str:
    if not COUNTDOWN_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError("countdown must use DD:HH:MM:SS")
    return value


def get_seconds_from_countdown(countdown_str: str) -> int:
    match = COUNTDOWN_PATTERN.fullmatch(countdown_str)
    if not match:
        raise ValueError("countdown must use DD:HH:MM:SS")

    days, hours, minutes, seconds = map(int, match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def format_seconds_to_countdown(total_seconds: float) -> str:
    remaining_seconds = max(0, int(total_seconds))
    days, remainder = divmod(remaining_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days:02}:{hours:02}:{minutes:02}:{seconds:02}"


def get_system_uptime() -> str:
    """Fetches system uptime."""
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            seconds = int(uptime_seconds % 60)
            if days > 0:
                return f"{days}d {hours:02}:{minutes:02}:{seconds:02}"
            return f"{hours:02}:{minutes:02}:{seconds:02}"
    except Exception:
        return "Err"

def get_system_resources() -> str:
    """Fetches CPU and RAM usage using /proc filesystem."""
    try:
        # CPU usage (simplified via top to get a reliable snapshot)
        cpu_cmd = subprocess.run(["top", "-bn1"], capture_output=True, text=True, timeout=5)
        cpu_match = re.search(r"%Cpu\(s\):\s+([\d.]+)\s+us", cpu_cmd.stdout)
        cpu_pct = int(float(cpu_match.group(1))) if cpu_match else 0

        # RAM usage via /proc/meminfo
        mem_info = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    mem_info[parts[0].strip()] = int(parts[1].split()[0])
        
        mem_total = mem_info.get("MemTotal", 0)
        mem_avail = mem_info.get("MemAvailable", mem_info.get("MemFree", 0))
        mem_used_pct = 0 if mem_total == 0 else round(((mem_total - mem_avail) / mem_total) * 100)

        return f"CPU: {cpu_pct}% RAM: {mem_used_pct}%"
    except Exception:
        return "CPU: Err RAM: Err"


def get_token_text(token_cache: dict) -> str:
    return token_cache.get("value", "")


def update_status_lines(
    lcd: I2cLcd,
    show_time: bool,
    uptime_enabled: bool,
    show_tokens: bool,
    show_resources: bool,
    token_cache: dict,
    resource_cache: dict,
    interval: float,
) -> None:
    line_3 = ""
    line_4 = ""

    if show_resources:
        line_3 = get_system_resources()
    elif show_tokens:
        line_3 = get_token_text(token_cache)

    if uptime_enabled:
        line_4 = get_system_uptime()
    elif show_time:
        line_4 = format_time()

    lcd.write_line(line_3, LCD_LINE_3)
    lcd.write_line(line_4, LCD_LINE_4)


def scroll_frames(text: str) -> list[str]:
    if len(text) <= LCD_WIDTH:
        return [text]

    padded_text = f"{text}{' ' * LCD_WIDTH}"
    return [
        padded_text[index:index + LCD_WIDTH]
        for index in range(len(padded_text) - LCD_WIDTH + 1)
    ]


def scroll_text(
    lcd: I2cLcd,
    text: str,
    line: int,
    interval: float,
    show_time: bool,
    uptime_enabled: bool,
    show_tokens: bool,
    token_cache: dict,
    show_resources: bool,
    resource_cache: dict,
) -> None:
    frames = scroll_frames(text)

    while True:
        for frame in frames:
            lcd.write_line(frame, line)
            update_status_lines(
                lcd,
                show_time,
                uptime_enabled,
                show_tokens,
                show_resources,
                token_cache,
                resource_cache,
                interval,
            )
            sleep(interval)

def run_countdown_mode(
    lcd: I2cLcd,
    text: str,
    total_seconds: float,
    interval: float,
    show_time: bool,
    uptime_enabled: bool,
    show_tokens: bool,
    token_cache: dict,
    show_resources: bool,
    resource_cache: dict,
) -> None:
    """Displays text on line 1 and a countdown on line 2."""
    start_time = monotonic()
    while True:
        elapsed = monotonic() - start_time
        remaining = max(0, total_seconds - elapsed)

        lcd.write_line(text, LCD_LINE_1)
        lcd.write_line(format_seconds_to_countdown(remaining), LCD_LINE_2)
        update_status_lines(
            lcd, show_time, uptime_enabled, show_tokens, show_resources,
            token_cache, resource_cache, interval
        )

        if remaining <= 0:
            lcd.write_line(text, LCD_LINE_1)
            lcd.write_line("00:00:00:00", LCD_LINE_2)
            update_status_lines(
                lcd, show_time, uptime_enabled, show_tokens, show_resources,
                token_cache, resource_cache, interval
            )
            break

        sleep(interval)


def blink_heart(lcd: I2cLcd, text: str, interval: float, show_time: bool, 
               uptime_enabled: bool, show_tokens: bool, token_cache: dict, 
               show_resources: bool, resource_cache: dict) -> None:
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
        lcd.write_line("", LCD_LINE_3)
        update_status_lines(lcd, show_time, uptime_enabled, show_tokens, show_resources, token_cache, resource_cache, interval)
        sleep(interval)
        lcd.write_line(frames[frame_index], LCD_LINE_1)
        lcd.write_line("        :)", LCD_LINE_2)
        lcd.write_line("", LCD_LINE_3)
        update_status_lines(lcd, show_time, uptime_enabled, show_tokens, show_resources, token_cache, resource_cache, interval)
        sleep(interval)
        frame_index = (frame_index + 1) % len(frames)


def blink_display(lcd: I2cLcd, text: str, interval: float, show_time: bool, 
                 uptime_enabled: bool, show_tokens: bool, token_cache: dict, 
                 show_resources: bool, resource_cache: dict) -> None:
    frames = scroll_frames(text)

    while True:
        for frame in frames:
            lcd.write_line(frame, LCD_LINE_1)
            lcd.write_line("", LCD_LINE_2)
            lcd.write_line("", LCD_LINE_3)
            update_status_lines(lcd, show_time, uptime_enabled, show_tokens, show_resources, token_cache, resource_cache, interval)
            lcd.display_on()
            sleep(interval)
            lcd.display_off()
            sleep(interval)


def main() -> None:
    args = parse_args()
    address = args.address if args.address is not None else detect_address(args.bus)
    lcd = I2cLcd(bus_id=args.bus, address=address)
    
    token_cache = {
        'last_update': 0,
        'value': "",
        'frames': [""],
        'frame_index': 0,
        'last_frame_at': 0.0,
    }
    resource_cache = {
        'last_update': 0,
        'value': "",
    }
    
    try:
        if args.countdown:
            total_seconds = get_seconds_from_countdown(args.countdown)
            run_countdown_mode(lcd, args.text, total_seconds, args.interval, args.show_time, args.uptime, args.show_tokens, token_cache, args.show_resources, resource_cache)
        elif args.blink_heart:
            blink_heart(lcd, args.text, args.interval, args.show_time, args.uptime, args.show_tokens, token_cache, args.show_resources, resource_cache)
        elif args.blink_display:
            blink_display(lcd, args.text, args.interval, args.show_time, args.uptime, args.show_tokens, token_cache, args.show_resources, resource_cache)
        else:
            lcd.write_line("", LCD_LINE_2)
            lcd.write_line("", LCD_LINE_3)
            scroll_text(lcd, args.text, LCD_LINE_1, args.interval, args.show_time, args.uptime, args.show_tokens, token_cache, args.show_resources, resource_cache)
    except KeyboardInterrupt:
        lcd.display_on()
        lcd.clear()
    finally:
        lcd.close()


if __name__ == "__main__":
    main()

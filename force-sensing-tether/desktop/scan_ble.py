"""Scan for nearby BLE devices and print each name and address.

Use this to find the address to pass as --address to the other desktop scripts.

Usage:
    python3 scan_ble.py [--timeout 8.0]
"""

import argparse
import asyncio

from bleak import BleakScanner


async def main(timeout: float = 8.0) -> None:
    """Scan for timeout seconds and print each device found."""
    devices = await BleakScanner.discover(timeout=timeout)
    for d in devices:
        print(f"Name={d.name}  Address={d.address}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List nearby BLE devices.")
    parser.add_argument("--timeout", type=float, default=8.0,
                        help="Scan time in seconds (default: 8.0).")
    asyncio.run(main(parser.parse_args().timeout))

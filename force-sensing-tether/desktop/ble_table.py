"""Connect to the ESP32 over BLE, log each reading to CSV, and show a live table.

A background thread runs the bleak client and pushes readings onto a queue;
the Tkinter UI polls that queue every 100 ms. Reconnects automatically if the
connection drops.

Shared state (the BLE address, CSV path, and reading queue) lives in one
TableSession object that is passed to each function, instead of module-level
globals. tkinter and bleak are imported inside the functions that use them,
so the logging helpers can be imported and tested without a display or
Bluetooth stack.

Usage:
    python3 ble_table.py [--address 88:57:21:84:96:BE] [--csv pot_log.csv]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# ===== CONFIG (defaults; each can be overridden on the command line) =====
# Replace with your board's address (run scan_ble.py to find it)
ESP32_ADDRESS = "88:57:21:84:96:BE"
TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
CSV_FILE = "pot_log.csv"
MAX_ROWS = 200  # how many rows to keep visible in the table
# ==================


@dataclass
class TableSession:
    """Settings plus the thread-safe pipe from the BLE thread to the UI thread."""

    address: str = ESP32_ADDRESS
    csv_file: str = CSV_FILE
    ui_queue: queue.Queue[tuple[str, str]] = field(default_factory=queue.Queue)


def ensure_csv_header(csv_file: str) -> None:
    """Create csv_file with a header row if it doesn't exist yet."""
    try:
        open(csv_file, "r").close()
    except FileNotFoundError:
        with open(csv_file, "w", newline="") as f:
            csv.writer(f).writerow(["timestamp_local", "pot_value"])


def handle_notify(session: TableSession, sender: object, data: bytearray) -> None:
    """BLE callback: print the reading, append it to the CSV, and queue it for the UI."""
    ts = datetime.now().isoformat(timespec="seconds")

    # Expect ESP32 is sending text like "2384"
    val_str = data.decode("utf-8", errors="replace").strip()

    # Print in terminal
    print(ts, val_str)

    # Log to CSV
    with open(session.csv_file, "a", newline="") as f:
        csv.writer(f).writerow([ts, val_str])

    # Send to UI
    session.ui_queue.put((ts, val_str))


async def ble_loop(session: TableSession) -> None:
    """Connect, subscribe to TX notifications, and retry forever on disconnect."""
    from bleak import BleakClient

    ensure_csv_header(session.csv_file)

    def on_notify(sender: object, data: bytearray) -> None:
        handle_notify(session, sender, data)

    while True:
        try:
            print("Connecting to ESP32...")
            async with BleakClient(session.address, timeout=15.0) as client:
                print("Connected. Subscribing...")
                await client.start_notify(TX_CHAR_UUID, on_notify)
                print("Subscribed. Waiting for values... (Ctrl+C to stop)")

                while client.is_connected:
                    await asyncio.sleep(1)

        except Exception as e:
            print("BLE error:", e)

        print("Disconnected. Retrying in 2 seconds...")
        await asyncio.sleep(2)


def run_ble_in_thread(session: TableSession) -> None:
    """Run the asyncio BLE loop (target for the worker thread)."""
    asyncio.run(ble_loop(session))


class LiveTableApp:
    """Tkinter window with a status line and a scrolling table of readings."""

    def __init__(self, root: Any, session: TableSession):
        import tkinter as tk
        from tkinter import ttk

        self.root = root
        self.session = session
        self.root.title("ESP32 BLE Live Data")
        self.root.geometry("520x420")

        # Status line
        self.status_var = tk.StringVar(value="Starting BLE...")
        status = ttk.Label(root, textvariable=self.status_var)
        status.pack(padx=10, pady=(10, 0), anchor="w")

        # Table (Treeview)
        columns = ("timestamp", "value")
        self.tree = ttk.Treeview(root, columns=columns, show="headings", height=18)
        self.tree.heading("timestamp", text="Timestamp (local)")
        self.tree.heading("value", text="Pot Value")

        self.tree.column("timestamp", width=320, anchor="w")
        self.tree.column("value", width=140, anchor="center")

        self.tree.pack(padx=10, pady=10, fill="both", expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.place(in_=self.tree, relx=1.0, rely=0, relheight=1.0, anchor="ne")

        # Start polling queue for new rows
        self.root.after(100, self.poll_queue)

    def poll_queue(self) -> None:
        """Move any queued readings into the table, then reschedule."""
        updated = False

        while True:
            try:
                ts, val_str = self.session.ui_queue.get_nowait()
            except queue.Empty:
                break

            updated = True

            # Insert new row at bottom
            self.tree.insert("", "end", values=(ts, val_str))

            # Limit rows (keep newest MAX_ROWS)
            children = self.tree.get_children()
            if len(children) > MAX_ROWS:
                for item in children[: len(children) - MAX_ROWS]:
                    self.tree.delete(item)

            # Auto-scroll to newest
            self.tree.yview_moveto(1.0)

        if updated:
            self.status_var.set("Receiving data...")

        self.root.after(100, self.poll_queue)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Log ESP32 BLE readings to CSV and a live table.")
    p.add_argument("--address", default=ESP32_ADDRESS,
                   help=f"ESP32 BLE address (default: {ESP32_ADDRESS}).")
    p.add_argument("--csv", default=CSV_FILE,
                   help=f"CSV log that every reading is appended to (default: {CSV_FILE}).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    session = TableSession(address=args.address, csv_file=args.csv)

    import tkinter as tk  # imported here so the helpers above work without a display

    # Start BLE worker thread
    t = threading.Thread(target=run_ble_in_thread, args=(session,), daemon=True)
    t.start()

    # Start UI (pop-up window)
    root = tk.Tk()
    app = LiveTableApp(root, session)  # noqa: F841  (keep a reference while the UI runs)
    root.mainloop()


if __name__ == "__main__":
    main()

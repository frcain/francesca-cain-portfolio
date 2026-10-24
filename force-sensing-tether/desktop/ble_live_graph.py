"""Live BLE force display for the tether demo.

Connects to the ESP32, smooths each raw ADC reading with a running median,
subtracts it from a fixed baseline, and shows the values in a live plot and table.
The "force" value is a baseline-relative signal in ADC counts; no newton
calibration is applied. Every reading is appended to the CSV log. Each
connection is a "run"; when the board disconnects (or Stop / space is pressed)
the run is saved to the graphs folder as a PNG graph and a per-run CSV.

Shared state (queues, graph data, run number, smoothing window, settings)
lives in one SessionState object that is passed to each function, instead of
module-level globals.

Keys: Space = save run and quit, Esc or q = quit without saving.

tkinter, matplotlib, and bleak are imported inside the functions that use
them, so the signal-processing helpers (raw_to_force) can be imported and
tested without a display or Bluetooth stack.

Usage:
    python3 ble_live_graph.py [--address 88:57:21:85:FB:02] [--csv pot_log.csv]
                              [--graphs-dir graphs] [--baseline 3520]
"""

import argparse
import asyncio
import csv
import os
import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime

# CONFIG (defaults; each can be overridden on the command line)
# Replace with your board's address (run scan_ble.py to find it)
ESP32_ADDRESS   = "88:57:21:85:FB:02"
TX_CHAR_UUID    = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
CSV_FILE        = "pot_log.csv"
GRAPHS_DIR      = "graphs"
MAX_ROWS        = 200

# Signal processing
# Baseline offset in ADC counts: use 3320 when powered from a laptop,
# 3520 on battery/wall outlet.
BASELINE_ADC    = 3520
SMOOTH_WINDOW   = 10       # running-median window (readings)
FORCE_LABEL     = "Force signal (ADC counts from baseline)"

# COLORS
C_BG            = "#2b2b2b"
C_GRAPH_BG      = "#3c3c3c"
C_PLOT_LINE     = "#e63946"
C_PLOT_DOT      = "#ff6b6b"
C_GRID          = "#555555"
C_AXIS_LABEL    = "#dddddd"
C_TITLE         = "#ffffff"
C_SPINE         = "#555555"
C_STATUS_FG     = "#dddddd"
C_TABLE_BG      = "#3c3c3c"
C_TABLE_FG      = "#ffffff"
C_TABLE_HEAD_BG = "#2b2b2b"
C_TABLE_HEAD_FG = "#dddddd"
C_TABLE_SEL     = "#555555"


@dataclass
class SessionState:
    """Everything the BLE thread and the UI share for one app session.

    The BLE thread fills the queues and graph lists; the Tkinter thread reads
    them. graph_lock guards the four graph lists. Settings from the command
    line (address, CSV path, graphs folder, baseline) live here too, so no
    function needs module-level globals.
    """

    address: str = ESP32_ADDRESS
    csv_file: str = CSV_FILE
    graphs_dir: str = GRAPHS_DIR
    baseline: float = BASELINE_ADC

    ui_queue: queue.Queue[tuple[str, str, float | None]] = field(default_factory=queue.Queue)
    event_queue: queue.Queue[str] = field(default_factory=queue.Queue)

    graph_times: list[float] = field(default_factory=list)
    graph_forces: list[float] = field(default_factory=list)
    graph_raw: list[str] = field(default_factory=list)   # raw ADC values, saved per-run
    graph_ts: list[str] = field(default_factory=list)    # timestamps, saved per-run
    graph_lock: threading.Lock = field(default_factory=threading.Lock)

    run_number: int = 0
    smooth_buf: list[float] = field(default_factory=list)

    def start_new_run(self) -> None:
        """Count a new run and clear the graph data and smoothing window."""
        self.run_number += 1
        with self.graph_lock:
            self.graph_times.clear()
            self.graph_forces.clear()
            self.graph_raw.clear()
            self.graph_ts.clear()
        self.smooth_buf.clear()

    def add_point(self, time_s: float, force: float, raw: str, ts: str) -> None:
        """Append one reading to the current run's graph data."""
        with self.graph_lock:
            self.graph_times.append(time_s)
            self.graph_forces.append(force)
            self.graph_raw.append(raw)
            self.graph_ts.append(ts)

    def snapshot(self) -> tuple[list[float], list[float], list[str], list[str]]:
        """Copies of (times, forces, raws, timestamps), taken under the lock."""
        with self.graph_lock:
            return (list(self.graph_times), list(self.graph_forces),
                    list(self.graph_raw), list(self.graph_ts))


def raw_to_force(raw_str: str, buf: list[float], baseline: float = BASELINE_ADC) -> float | None:
    """Median of the last SMOOTH_WINDOW raw readings, subtracted from a fixed baseline.

    Returns None if the reading isn't a number. The result is in ADC counts
    relative to the baseline (no newton calibration is applied here), and is
    what gets plotted and logged as "force".

    buf is the running window of recent readings; it is updated in place
    (non-numeric readings leave it unchanged). This is a pure function of its
    arguments, so it can be tested in isolation.
    """
    try:
        raw = float(raw_str)
        buf.append(raw)
        if len(buf) > SMOOTH_WINDOW:
            buf.pop(0)
        mid = sorted(buf)[len(buf) // 2]
        median = (-1 * mid) + baseline
        return median
    except ValueError:
        return None


def handle_notify(state: SessionState, sender: object, data: bytearray) -> None:
    """BLE callback: convert the reading, queue it for the UI, and append it to CSV."""
    now = datetime.now()
    ts  = now.isoformat(timespec="seconds")
    val = data.decode("utf-8", errors="replace").strip()
    force = raw_to_force(val, state.smooth_buf, state.baseline)
    print(ts, val, f"-> {force:.2f}" if force is not None else "")
    state.ui_queue.put((ts, val, force))
    if force is not None:
        state.add_point(now.timestamp(), force, val, ts)
    with open(state.csv_file, "a", newline="") as f:
        csv.writer(f).writerow([ts, val, f"{force:.4f}" if force is not None else ""])


def ensure_csv_header(csv_file: str) -> None:
    """Create csv_file with a header row if it doesn't exist yet."""
    try:
        open(csv_file, "r").close()
    except FileNotFoundError:
        with open(csv_file, "w", newline="") as f:
            csv.writer(f).writerow(["timestamp", "raw", "force"])


async def ble_loop(state: SessionState) -> None:
    """Create the CSV header if needed, then connect and reconnect forever."""
    from bleak import BleakClient

    ensure_csv_header(state.csv_file)

    def on_notify(sender: object, data: bytearray) -> None:
        handle_notify(state, sender, data)

    while True:
        try:
            print("Connecting...")
            async with BleakClient(state.address, timeout=15.0) as client:
                await client.start_notify(TX_CHAR_UUID, on_notify)
                state.event_queue.put("connected")
                print("Connected.")
                while client.is_connected:
                    await asyncio.sleep(1)
        except Exception as e:
            print("BLE error:", e)
        state.event_queue.put("disconnected")
        print("Disconnected. Retrying in 2s...")
        await asyncio.sleep(2)


def run_ble(state: SessionState) -> None:
    """Run the asyncio BLE loop (target for the worker thread)."""
    asyncio.run(ble_loop(state))


def run_base_name(run_number: int, t0: float) -> str:
    """File name stem for a saved run, e.g. run_003_20260301_141500."""
    timestamp_str = datetime.fromtimestamp(t0).strftime("%Y%m%d_%H%M%S")
    return f"run_{run_number:03d}_{timestamp_str}"


def save_graph(state: SessionState) -> None:
    """Save the current run as a PNG graph and a per-run CSV in state.graphs_dir."""
    import matplotlib.pyplot as plt

    times, forces, raws, tss = state.snapshot()
    if len(times) < 2:
        return

    run_number = state.run_number
    t0 = times[0]
    xs = [t - t0 for t in times]
    base_name = run_base_name(run_number, t0)

    # Save PNG
    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_GRAPH_BG)
    ax.tick_params(colors=C_AXIS_LABEL, labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(C_SPINE)
    ax.set_xlabel("Time (s)", color=C_AXIS_LABEL, fontsize=9)
    ax.set_ylabel(FORCE_LABEL, color=C_AXIS_LABEL, fontsize=9)
    run_start = datetime.fromtimestamp(t0).strftime('%Y-%m-%d %H:%M:%S')
    ax.set_title(f"Run {run_number}  -  {run_start}", color=C_TITLE, fontsize=11, pad=8)
    ax.grid(True, color=C_GRID, linestyle="--", linewidth=0.5)
    ax.plot(xs, forces, color=C_PLOT_LINE, linewidth=1.8)
    ax.scatter(xs, forces, color=C_PLOT_DOT, s=18, zorder=5)
    png_path = os.path.join(state.graphs_dir, base_name + ".png")
    fig.savefig(png_path, dpi=150, bbox_inches="tight", facecolor=C_BG)
    plt.close(fig)
    print(f"Saved graph -> {png_path}")

    # Save per-run CSV ("force_counts": baseline-relative ADC counts, not newtons)
    csv_path = os.path.join(state.graphs_dir, base_name + ".csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "time_s", "raw", "force_counts"])
        for ts, t, raw, force in zip(tss, xs, raws, forces):
            writer.writerow([ts, f"{t:.3f}", raw, f"{force:.4f}"])
    print(f"Saved CSV   -> {csv_path}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live BLE force display for the tether demo.")
    p.add_argument("--address", default=ESP32_ADDRESS,
                   help=f"ESP32 BLE address (default: {ESP32_ADDRESS}).")
    p.add_argument("--csv", default=CSV_FILE,
                   help=f"CSV log that every reading is appended to (default: {CSV_FILE}).")
    p.add_argument("--graphs-dir", default=GRAPHS_DIR,
                   help=f"Folder for per-run PNG and CSV files (default: {GRAPHS_DIR}).")
    p.add_argument("--baseline", type=float, default=BASELINE_ADC,
                   help=f"Baseline in ADC counts (default: {BASELINE_ADC}; "
                        "3320 is typical when powered from a laptop).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    state = SessionState(
        address=args.address,
        csv_file=args.csv,
        graphs_dir=args.graphs_dir,
        baseline=args.baseline,
    )

    # GUI imports live here so the helpers above can be imported without a display.
    import tkinter as tk
    from tkinter import ttk

    import matplotlib

    matplotlib.use("TkAgg")
    import matplotlib.animation as animation
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

    os.makedirs(state.graphs_dir, exist_ok=True)

    # UI
    root = tk.Tk()
    root.title("ESP32 BLE Live Data")
    root.geometry("720x720")
    root.configure(bg=C_BG)

    status_var = tk.StringVar(value="Starting BLE...")
    tk.Label(root, textvariable=status_var, bg=C_BG, fg=C_STATUS_FG,
             font=("Courier New", 10)).pack(anchor="w", padx=12, pady=(10, 0))

    def stop_run() -> None:
        """Save the current run and close the window."""
        save_graph(state)
        root.destroy()

    tk.Button(root, text="Stop", command=stop_run,
              bg="#e63946", fg="white", font=("Courier New", 10),
              relief="flat", padx=10).pack(anchor="w", padx=12, pady=(5, 0))

    fig, ax = plt.subplots(figsize=(7, 3))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_GRAPH_BG)
    ax.tick_params(colors=C_AXIS_LABEL, labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(C_SPINE)
    ax.set_xlabel("Time (s)", color=C_AXIS_LABEL, fontsize=9)
    ax.set_ylabel(FORCE_LABEL, color=C_AXIS_LABEL, fontsize=9)
    ax.set_title("Live Force Reading", color=C_TITLE, fontsize=11, pad=8)
    ax.grid(True, color=C_GRID, linestyle="--", linewidth=0.5)
    plot_line, = ax.plot([], [], color=C_PLOT_LINE, linewidth=1.8)
    plot_dots  = ax.scatter([], [], color=C_PLOT_DOT, s=18, zorder=5)

    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.get_tk_widget().pack(fill="x", padx=10, pady=(6, 0))

    frame = tk.Frame(root, bg=C_BG)
    frame.pack(fill="both", expand=True, padx=10, pady=8)

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("T.Treeview", background=C_TABLE_BG, fieldbackground=C_TABLE_BG,
                    foreground=C_TABLE_FG, font=("Courier New", 9), rowheight=22)
    style.configure("T.Treeview.Heading", background=C_TABLE_HEAD_BG,
                    foreground=C_TABLE_HEAD_FG, font=("Courier New", 9, "bold"))
    style.map("T.Treeview", background=[("selected", C_TABLE_SEL)])

    tree = ttk.Treeview(frame, columns=("timestamp", "raw", "force"),
                        show="headings", height=10, style="T.Treeview")
    tree.heading("timestamp", text="Timestamp")
    tree.heading("raw",       text="Raw Value")
    tree.heading("force",     text="Force signal (counts)")
    tree.column("timestamp", width=280)
    tree.column("raw",   width=140, anchor="center")
    tree.column("force", width=140, anchor="center")

    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def animate(_frame: int) -> None:
        """Redraw the live plot from the latest data (called by FuncAnimation)."""
        times, forces, _, _ = state.snapshot()
        if not times:
            return
        t0 = times[0]
        xs = [t - t0 for t in times]
        plot_line.set_data(xs, forces)
        plot_dots.set_offsets(list(zip(xs, forces)))
        ax.set_xlim(0, max(xs[-1], 1))
        y_pad = max(1.0, (max(forces) - min(forces)) * 0.15)
        ax.set_ylim(max(0, min(forces) - y_pad), max(forces) + y_pad)
        canvas.draw_idle()

    # keep a reference so the animation isn't garbage collected
    ani = animation.FuncAnimation(  # noqa: F841
        fig, animate, interval=100, blit=False, cache_frame_data=False
    )

    def update() -> None:
        """Handle connect/disconnect events and new readings, then reschedule."""
        while True:
            try:
                event = state.event_queue.get_nowait()
            except queue.Empty:
                break
            if event == "connected":
                state.start_new_run()
                for item in tree.get_children():
                    tree.delete(item)
                ax.set_title(f"Live Force Reading  -  Run {state.run_number}",
                             color=C_TITLE, fontsize=11, pad=8)
                status_var.set(f"Run {state.run_number} started...")
            elif event == "disconnected":
                save_graph(state)
                status_var.set(f"Run {state.run_number} saved. Waiting for reconnect...")

        while True:
            try:
                ts, val, force = state.ui_queue.get_nowait()
            except queue.Empty:
                break
            tree.insert("", "end", values=(ts, val, f"{force:.2f}" if force is not None else "-"))
            children = tree.get_children()
            if len(children) > MAX_ROWS:
                for item in children[: len(children) - MAX_ROWS]:
                    tree.delete(item)
            tree.yview_moveto(1.0)
            status_var.set(f"Run {state.run_number}  -  {len(state.graph_times)} points")

        root.after(100, update)

    root.bind("<Escape>", lambda e: root.destroy())
    root.bind("<q>", lambda e: root.destroy())
    root.bind("<space>", lambda e: stop_run())

    threading.Thread(target=run_ble, args=(state,), daemon=True).start()
    root.after(100, update)
    root.mainloop()


if __name__ == "__main__":
    main()

# Force-Sensing Vertebral Body Tether

Software for a prototype force-sensing vertebral body tether for pediatric scoliosis, built as a team senior capstone in Carnegie Mellon's Department of Biomedical Engineering (2025 to 2026). An ESP32 reads the conditioned load cell signal and streams it over Bluetooth Low Energy to a laptop, which smooths the readings and displays them live. I developed the electronics and Bluetooth system.

## About the "force" values

The desktop app does not convert readings to newtons. Its "force" value is a smoothed, baseline-relative signal in ADC counts: the median of the last 10 raw readings, subtracted from a fixed baseline (3520 counts by default; about 3320 when the board is powered from a laptop). It rises as load increases, but no load-cell calibration is applied. Plots and per-run CSVs label it accordingly.

## Project structure

- `firmware/Bluetooth_UART_DeepSleep/`: ESP32 sketch (Arduino C++). Sets up a BLE UART service, waits up to 30 seconds for a connection, streams analog readings as BLE notifications every 120 ms, then enters deep sleep for 10 seconds before waking to advertise again. Constants are grouped at the top, and setup, advertising, sending, and sleep are separate functions.
- `desktop/scan_ble.py`: Scans for nearby BLE devices to find the ESP32's address.
- `desktop/ble_table.py`: Connects with `bleak`, logs incoming readings to CSV, and shows them in a live Tkinter table. Settings and the reading queue live in a `TableSession` object.
- `desktop/ble_live_graph.py`: Demo app. Smooths raw ADC readings with a running median, converts them to the baseline-relative force signal, plots it in real time, logs timestamped raw and force values to CSV, and saves a graph and CSV of each run. Shared state (queues, graph data, run number, smoothing window, settings) lives in a `SessionState` object that is passed to each function instead of module-level globals. `raw_to_force` is a pure function that takes the smoothing window and baseline as arguments.

In both apps, tkinter, bleak, and matplotlib are imported inside the functions that use them, so the logic can be imported and tested without a display or Bluetooth stack.

## Install

Firmware: Arduino IDE with ESP32 board support.

Desktop: from the repository root, `pip install -e ".[tether]"` (adds `bleak` to the core packages, which include `matplotlib`; Tkinter comes with most Python installs).

## Run

```bash
cd desktop
python3 scan_ble.py                                   # find the board's address
python3 ble_live_graph.py --address 88:57:21:85:FB:02 --baseline 3520
python3 ble_table.py --address 88:57:21:84:96:BE
```

Defaults are the addresses and file names the scripts were written with (`pot_log.csv`, `graphs/`). Use `--help` for all options.

## Tests

From the repository root: `python3 -m pytest -q tests/test_tether_signal.py`. Covers the running-median window, spike rejection, baseline subtraction, handling of non-numeric readings, the BLE callbacks' CSV logging (called directly with fake data), run resets, and saving a run's graph and CSV. No Bluetooth hardware or display is needed.

The firmware has no automated tests and is not compiled in CI. The most recent edit only reorganized it (named constants and functions, same values and order of operations) and has not been recompiled or run on a board since.

"""Tests for the tether desktop apps' pure logic (no Bluetooth or display needed)."""

import csv
import sys

import ble_live_graph as g
import ble_table


def test_modules_import_without_gui_or_bluetooth():
    # tkinter and bleak are imported lazily inside main() / ble_loop(),
    # so importing the modules does not pull them in.
    assert "tkinter" not in sys.modules
    assert "bleak" not in sys.modules
    assert callable(g.raw_to_force)
    assert callable(ble_table.handle_notify)


def test_single_reading_is_baseline_minus_raw():
    buf = []
    assert g.raw_to_force("3500", buf=buf) == 3520 - 3500
    assert buf == [3500.0]


def test_custom_baseline():
    assert g.raw_to_force("3300", buf=[], baseline=3320) == 20


def test_non_numeric_returns_none_and_leaves_buffer():
    buf = [3400.0]
    assert g.raw_to_force("garbage", buf=buf) is None
    assert buf == [3400.0]


def test_running_median_rejects_spike():
    buf = []
    for _ in range(5):
        g.raw_to_force("3400", buf=buf)
    # one large spike does not move the median
    assert g.raw_to_force("100", buf=buf) == 3520 - 3400


def test_window_keeps_last_ten_readings():
    buf = []
    for value in range(1, 13):
        g.raw_to_force(str(value), buf=buf)
    assert buf == [float(v) for v in range(3, 13)]
    assert len(buf) == g.SMOOTH_WINDOW


def test_median_uses_upper_middle_for_even_count():
    buf = []
    g.raw_to_force("10", buf=buf)
    # sorted [10, 20]; index len // 2 = 1 -> 20
    assert g.raw_to_force("20", buf=buf) == 3520 - 20


def test_default_baseline_is_3520():
    assert g.raw_to_force("3500", []) == 20


# ---------- SessionState and the BLE callback (ble_live_graph) ----------

def test_handle_notify_logs_queues_and_records_point(tmp_path):
    state = g.SessionState(csv_file=str(tmp_path / "log.csv"), baseline=3320)
    g.handle_notify(state, None, bytearray(b"3300\n"))
    g.handle_notify(state, None, bytearray(b"oops"))

    ts, raw, force = state.ui_queue.get_nowait()
    assert (raw, force) == ("3300", 20)
    assert state.ui_queue.get_nowait()[1:] == ("oops", None)
    assert state.graph_forces == [20]
    assert state.graph_raw == ["3300"]
    assert state.smooth_buf == [3300.0]

    rows = list(csv.reader((tmp_path / "log.csv").read_text().splitlines()))
    assert rows[0][1:] == ["3300", "20.0000"]
    assert rows[1][1:] == ["oops", ""]


def test_ensure_csv_header_only_once(tmp_path):
    path = str(tmp_path / "log.csv")
    g.ensure_csv_header(path)
    g.ensure_csv_header(path)
    assert (tmp_path / "log.csv").read_text().splitlines() == ["timestamp,raw,force"]


def test_start_new_run_clears_data_and_counts():
    state = g.SessionState()
    state.add_point(1.0, 5.0, "3515", "t")
    state.smooth_buf.append(3515.0)
    state.start_new_run()
    assert state.run_number == 1
    assert state.snapshot() == ([], [], [], [])
    assert state.smooth_buf == []


def test_sessions_do_not_share_state():
    a, b = g.SessionState(), g.SessionState()
    a.add_point(1.0, 5.0, "3515", "t")
    assert b.graph_times == []
    assert a.ui_queue is not b.ui_queue


def test_save_graph_writes_png_and_csv(tmp_path):
    state = g.SessionState(graphs_dir=str(tmp_path))
    state.start_new_run()
    state.add_point(100.0, 10.0, "3510", "2026-01-01T00:00:00")
    state.add_point(100.5, 12.0, "3508", "2026-01-01T00:00:00")
    g.save_graph(state)

    base = g.run_base_name(1, 100.0)
    assert base.startswith("run_001_")
    assert (tmp_path / f"{base}.png").exists()
    rows = list(csv.reader((tmp_path / f"{base}.csv").read_text().splitlines()))
    assert rows[0] == ["timestamp", "time_s", "raw", "force_counts"]
    assert rows[2] == ["2026-01-01T00:00:00", "0.500", "3508", "12.0000"]


def test_save_graph_skips_runs_with_fewer_than_two_points(tmp_path):
    state = g.SessionState(graphs_dir=str(tmp_path))
    state.add_point(100.0, 10.0, "3510", "t")
    g.save_graph(state)
    assert list(tmp_path.iterdir()) == []


# ---------- ble_table ----------

def test_ble_table_logs_and_queues(tmp_path):
    session = ble_table.TableSession(csv_file=str(tmp_path / "pot.csv"))
    ble_table.ensure_csv_header(session.csv_file)
    ble_table.handle_notify(session, None, bytearray(b" 2384 "))

    ts, value = session.ui_queue.get_nowait()
    assert value == "2384"
    rows = list(csv.reader((tmp_path / "pot.csv").read_text().splitlines()))
    assert rows[0] == ["timestamp_local", "pot_value"]
    assert rows[1] == [ts, "2384"]


def test_parse_args_defaults_unchanged():
    args = g.parse_args([])
    assert (args.address, args.csv, args.graphs_dir, args.baseline) == (
        "88:57:21:85:FB:02", "pot_log.csv", "graphs", 3520
    )
    t = ble_table.parse_args([])
    assert (t.address, t.csv) == ("88:57:21:84:96:BE", "pot_log.csv")

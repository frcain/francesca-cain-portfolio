"""Tests for the braille lookup and embossing logic, using fake drivers (no hardware)."""

import braille_embosser as be


class FakeColumn:
    """Records each driver call instead of moving a servo."""

    def __init__(self, name, log):
        self.name = name
        self.log = log

    def set_pins(self, pins_high):
        self.log.append((self.name, "set", be.pins_to_pattern(pins_high)))

    def emboss(self, dwell_ms):
        self.log.append((self.name, "emboss", dwell_ms))

    def reset(self):
        self.log.append((self.name, "reset"))


class FakeTape:
    def __init__(self, log):
        self.log = log

    def advance_column_gap(self):
        self.log.append(("tape", "gap"))

    def advance_intercell(self):
        self.log.append(("tape", "cell"))

    def newline(self):
        self.log.append(("tape", "newline"))


def make_embosser(**cfg):
    log = []
    emb = be.BrailleEmbosser(
        FakeColumn("L", log), FakeColumn("R", log), FakeTape(log), be.EmbossConfig(**cfg)
    )
    return emb, log


def cell_patterns(log):
    """Collapse a step log into (left_pattern, right_pattern) per embossed cell."""
    sets = [entry for entry in log if entry[1] == "set"]
    return [(sets[i][2], sets[i + 1][2]) for i in range(0, len(sets), 2)]


def test_braille_map_letters():
    assert be.BRAILLE_MAP["a"] == {1}
    assert be.BRAILLE_MAP["h"] == {1, 2, 5}
    assert be.BRAILLE_MAP["z"] == {1, 3, 5, 6}
    assert be.BRAILLE_MAP[" "] == set()
    # every lowercase letter is mapped
    assert all(chr(c) in be.BRAILLE_MAP for c in range(ord("a"), ord("z") + 1))


def test_digits_map_to_a_through_j():
    assert be.DIGIT_TO_LETTER["1"] == "a"
    assert be.DIGIT_TO_LETTER["0"] == "j"
    assert len(be.DIGIT_TO_LETTER) == 10


def test_pins_to_pattern():
    assert be.pins_to_pattern(set()) == 0
    assert be.pins_to_pattern({1}) == 0b100
    assert be.pins_to_pattern({2}) == 0b010
    assert be.pins_to_pattern({3}) == 0b001
    assert be.pins_to_pattern({1, 2}) == 6
    assert be.pins_to_pattern({1, 3}) == 5
    assert be.pins_to_pattern({1, 2, 3}) == 7


def test_split_dots_to_columns():
    assert be.split_dots_to_columns({2, 4, 6}) == ({2}, {1, 3})
    assert be.split_dots_to_columns(set()) == (set(), set())
    assert be.split_dots_to_columns({1, 2, 3, 4, 5, 6}) == ({1, 2, 3}, {1, 2, 3})


def test_emboss_cell_step_order():
    emb, log = make_embosser(dwell_ms_left=30, dwell_ms_right=40)
    emb.emboss_cell(be.BRAILLE_MAP["h"])  # left {1,2} -> 6, right {2} -> 2
    assert log == [
        ("L", "set", 6),
        ("L", "emboss", 30),
        ("tape", "gap"),
        ("R", "set", 2),
        ("R", "emboss", 40),
        ("tape", "cell"),
    ]


def test_emboss_text_capital_and_letters():
    emb, log = make_embosser()
    emb.emboss_text("Hi")
    # capital indicator {6} -> right column bottom, then h, then i
    assert cell_patterns(log) == [(0, 1), (6, 2), (2, 4)]


def test_emboss_text_number_run_uses_one_indicator():
    emb, log = make_embosser()
    emb.emboss_text("12")
    # number indicator {3,4,5,6} -> left {3}=1, right {1,2,3}=7; then a, b
    assert cell_patterns(log) == [(1, 7), (4, 0), (6, 0)]


def test_unknown_char_is_blank_cell():
    emb, log = make_embosser()
    emb.emboss_text("#")
    assert cell_patterns(log) == [(0, 0)]


def test_newline_and_soft_wrap():
    emb, log = make_embosser(wrap_cols=2)
    emb.emboss_text("abc\nd")
    tape_moves = [e[1] for e in log if e[0] == "tape" and e[1] == "newline"]
    # one soft wrap after "ab", one explicit newline
    assert tape_moves == ["newline", "newline"]
    assert len(cell_patterns(log)) == 4


def test_sanitize_text_collapses_whitespace():
    assert be.sanitize_text("hi\tthere   friend") == "hi there friend"


def test_console_drivers_emit_expected_lines():
    lines = []
    be.set_output_handler(lines.append)
    try:
        emb = be.BrailleEmbosser(
            be.ConsoleColumn("LEFT"), be.ConsoleColumn("RIGHT"), be.ConsoleTape()
        )
        emb.emboss_text("a")
    finally:
        be.set_output_handler(print)

    assert lines[0] == "[LEFT] SET dots=[1] -> pattern=100 (pos=4)"
    assert lines[1].startswith("[LEFT] EMBOSS dwell=30ms, servo_pos=4")
    assert lines[2] == "[TAPE] gap between columns"
    assert lines[3] == "[RIGHT] SET dots={} -> pattern=000 (pos=0)"
    assert lines[-1] == "[TAPE] advance to next cell"
    assert len(lines) == 6


def test_main_demo_runs(capsys):
    be.main([])
    out = capsys.readouterr().out
    assert "[TAPE] NEW LINE" in out  # demo text wraps at 16 cells
    assert "dwell=35ms" in out

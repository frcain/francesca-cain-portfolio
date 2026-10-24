"""Convert plain text from OCR into actuator steps that emboss 6-dot braille.

Steps:
  1. Look up each character in a dict: char -> set of dots {1-6}.
  2. Split those dots into a LEFT column (1,2,3) and a RIGHT column
     (4,5,6, remapped to 1,2,3).
  3. For each cell: set pins (encoded as a 3-bit servo position), emboss,
     and move the tape between columns and cells.

Usage:
    python3 braille_embosser.py [file.txt] [--dwell-ms 35] [--wrap-cols 16]

With no file, a built-in demo string is embossed using console drivers.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional, Protocol, Set, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Central output helper (swap the handler to send output elsewhere, e.g. on the Pi)

_OutputHandler = Callable[[str], None]
_output_handler: _OutputHandler = print


def set_output_handler(fn: _OutputHandler) -> None:
    """Swap output sink for all driver messages (Raspberry Pi)."""
    global _output_handler
    _output_handler = fn


def _emit(msg: str) -> None:
    """Single choke point for ALL output from this module."""
    _output_handler(msg)

# ──────────────────────────────────────────────────────────────────────────────
# Basic braille mapping (uncontracted, Grade 1)

BRAILLE_MAP: Dict[str, Set[int]] = {
    " ": set(),  # blank, no dots

    # letters
    "a": {1}, "b": {1, 2}, "c": {1, 4}, "d": {1, 4, 5}, "e": {1, 5},
    "f": {1, 2, 4}, "g": {1, 2, 4, 5}, "h": {1, 2, 5}, "i": {2, 4}, "j": {2, 4, 5},
    "k": {1, 3}, "l": {1, 2, 3}, "m": {1, 3, 4}, "n": {1, 3, 4, 5}, "o": {1, 3, 5},
    "p": {1, 2, 3, 4}, "q": {1, 2, 3, 4, 5}, "r": {1, 2, 3, 5}, "s": {2, 3, 4},
    "t": {2, 3, 4, 5}, "u": {1, 3, 6}, "v": {1, 2, 3, 6}, "w": {2, 4, 5, 6},
    "x": {1, 3, 4, 6}, "y": {1, 3, 4, 5, 6}, "z": {1, 3, 5, 6},

    # punctuation
    ".": {2, 5, 6}, ",": {2}, ";": {2, 3}, ":": {2, 5}, "!": {2, 3, 5},
    "?": {2, 3, 6}, "-": {3, 6}, "'": {3}, "\"": {5, 6}, "/": {3, 4},

    # parentheses
    "(": {1, 2, 6},
    ")": {3, 4, 5},
}

# Indicators used BEFORE certain chars
CAPITAL_INDICATOR: Set[int] = {6}            # next letter is uppercase
NUMBER_INDICATOR: Set[int] = {3, 4, 5, 6}    # following chars are digits 0-9

# After NUMBER_INDICATOR, digits 1-0 map to letters a-j
DIGIT_TO_LETTER = {
    "1": "a", "2": "b", "3": "c", "4": "d", "5": "e",
    "6": "f", "7": "g", "8": "h", "9": "i", "0": "j",
}

# ──────────────────────────────────────────────────────────────────────────────
# Hardware abstraction
# Minimal driver protocols; real Raspberry Pi drivers implement the same methods.


def pins_to_pattern(pins_high: Set[int]) -> int:
    """
    Encode a column's active dots {1,2,3} (top/mid/bottom) into a 3-bit pattern:

        top    -> bit 2 (4's place)
        middle -> bit 1 (2's place)
        bottom -> bit 0 (1's place)

    Example:
      {1,2}   -> 110b -> 6
      {2}     -> 010b -> 2
      {1,3}   -> 101b -> 5
      {}      -> 000b -> 0
    """
    pattern = 0
    if 1 in pins_high:
        pattern |= 0b100
    if 2 in pins_high:
        pattern |= 0b010
    if 3 in pins_high:
        pattern |= 0b001
    return pattern


class ColumnDriver(Protocol):
    """
    Represents ONE Braille column, abstracted as 3 possible dots (top/mid/bottom = 1/2/3).

    High-level logic passes a set of active pins {1,2,3}. The driver should:

      - set_pins(pins_high):
            * interpret pins_high as a 3-bit pattern (top/mid/bottom)
            * move hardware (e.g., a servo) to the corresponding discrete position
              where pattern 0..7 encodes which dots will be embossed.

      - emboss(dwell_ms):
            * perform the strike at the current position for dwell_ms milliseconds

      - reset():
            * optional: return to a safe, idle state (e.g., servo home or pattern 0)
              when the system is idle or at shutdown. Not called between every cell
              by the core logic anymore.
    """
    def set_pins(self, pins_high: Set[int]) -> None: ...
    def emboss(self, dwell_ms: int) -> None: ...
    def reset(self) -> None: ...


class TapeDriver(Protocol):
    """
    Controls linear motion of the tape/paper:
      - advance_column_gap: small step between LEFT and RIGHT columns of the same cell
      - advance_intercell:  larger step to the next cell
      - newline:            carriage return / line advance
    """
    def advance_column_gap(self) -> None: ...
    def advance_intercell(self) -> None: ...
    def newline(self) -> None: ...


# Simple console simulators
class ConsoleColumn(ColumnDriver):
    """
    Console-only ColumnDriver that shows how the 3-dot pattern maps to a
    servo-like position integer (0-7).

    In the real driver, you would replace the print with a servo position call,
    e.g. servo.goto(pattern).
    """
    def __init__(self, name: str) -> None:
        self.name = name
        self.state = {1: False, 2: False, 3: False}  # track which pins are high
        self.pattern: int = 0  # integer 0-7

    def set_pins(self, pins_high: Set[int]) -> None:
        # Compute the pattern and update internal "pins" view for debugging.
        self.pattern = pins_to_pattern(pins_high)
        for p in (1, 2, 3):
            self.state[p] = (p in pins_high)

        # In real hardware, this is where you'd move the servo:
        #     self.servo.goto(self.pattern)
        # For now, just show the mapping.
        bits_str = f"{self.pattern:03b}"
        _emit(
            f"[{self.name}] SET dots={sorted(list(pins_high)) or '{}'} "
            f"-> pattern={bits_str} (pos={self.pattern})"
        )

    def emboss(self, dwell_ms: int) -> None:
        _emit(
            f"[{self.name}] EMBOSS dwell={dwell_ms}ms, "
            f"servo_pos={self.pattern}, state={self.state}"
        )

    def reset(self) -> None:
        # Optional homing, no longer called after every cell by core logic.
        self.pattern = 0
        self.state = {1: False, 2: False, 3: False}
        _emit(f"[{self.name}] reset to pattern=000 (pos=0)")


class ConsoleTape(TapeDriver):
    """Console-only TapeDriver that prints each tape move."""

    def advance_column_gap(self) -> None:
        _emit("[TAPE] gap between columns")

    def advance_intercell(self) -> None:
        _emit("[TAPE] advance to next cell")

    def newline(self) -> None:
        _emit("[TAPE] NEW LINE")

# ──────────────────────────────────────────────────────────────────────────────
# Config

@dataclass
class EmbossConfig:
    """Timing and layout settings for embossing."""

    dwell_ms_left: int = 30         # strike time for LEFT col (ms)
    dwell_ms_right: int = 30        # strike time for RIGHT col (ms)
    wrap_cols: int = 28             # soft wrap width in cells (0 disables wrapping)
    unknown_as_blank: bool = True   # unknown chars produce a blank cell

# ──────────────────────────────────────────────────────────────────────────────
# Core logic


def split_dots_to_columns(dots: Set[int]) -> Tuple[Set[int], Set[int]]:
    """
    Convert a cell's dot set into two pin sets (LEFT and RIGHT column).
      - LEFT uses dots {1,2,3} directly
      - RIGHT uses dots {4,5,6} but REMAPPED to {1,2,3} for the right actuator
        (i.e., 4->1, 5->2, 6->3)
    Example: dots {2,4,6} -> LEFT {2}, RIGHT {1,3}
    """
    left = {d for d in dots if d in (1, 2, 3)}
    right = {d - 3 for d in dots if d in (4, 5, 6)}
    return left, right


class BrailleEmbosser:
    """
    Orchestrates: for each Braille cell, strike LEFT column then RIGHT column, with tape moves.
    Call `emboss_text("Hello")` and the driver interfaces take care of the physical actions.

    For each column we:
      - Convert the active dots {1,2,3} into a 3-bit pattern (top/mid/bottom).
      - Treat that as a servo position (0-7).
      - Strike for cfg.dwell_ms_*, then step the tape.
    """
    def __init__(
        self,
        left: ColumnDriver,
        right: ColumnDriver,
        tape: TapeDriver,
        cfg: Optional[EmbossConfig] = None,
    ) -> None:
        self.left, self.right, self.tape = left, right, tape
        self.cfg = cfg or EmbossConfig()

    # Low level, emboss a single cell of dots
    def emboss_cell(self, dots: Set[int]) -> None:
        """
        Physical sequence for ONE cell:
          1) LEFT column: set pins for dots {1,2,3}, map to 3-bit servo position, emboss
          2) Tape: small gap to the RIGHT column
          3) RIGHT column: set pins for {4,5,6} (as 1..3), map to position, emboss
          4) Tape: advance to the next cell position

        The column is not reset to pattern 000 after each emboss, so the servo
        moves directly from the previous pattern to the next one.
        """
        left_pins, right_pins = split_dots_to_columns(dots)

        # Strike LEFT column (e.g., 'h' left column = {1,2} -> 110 -> pos 6)
        self.left.set_pins(left_pins)
        self.left.emboss(self.cfg.dwell_ms_left)

        # Move a tiny distance between the two columns of the same cell
        self.tape.advance_column_gap()

        # Strike RIGHT column (e.g., 'h' right column = {2} -> 010 -> pos 2)
        self.right.set_pins(right_pins)
        self.right.emboss(self.cfg.dwell_ms_right)

        # Move to next cell (bigger step than the column gap)
        self.tape.advance_intercell()

    # High-level, emboss whole strings with caps/numbers handling
    def emboss_text(self, text: str) -> None:
        """
        Convert a Unicode string into a sequence of braille cells and actuations.
        Behaviors:
          - Newline '\n' -> call tape.newline()
          - Soft wrap at cfg.wrap_cols cells per line
          - Uppercase -> emit CAPITAL_INDICATOR cell, then letter cell (lowercased)
          - Digit runs -> emit NUMBER_INDICATOR once, then map each digit 1..0 to a..j cells
          - Unknown chars -> blank cell
        """
        col_count = 0  # how many cells we've placed on the current line
        i = 0
        while i < len(text):
            ch = text[i]

            # handle explicit newlines quickly
            if ch == "\n":
                self.tape.newline()
                col_count = 0
                i += 1
                continue

            # soft wrap if line is "full"
            if self.cfg.wrap_cols and col_count >= self.cfg.wrap_cols:
                self.tape.newline()
                col_count = 0

            # handle digit RUNS with a single number indicator at the start
            if ch.isdigit():
                # emit a single NUMBER_INDICATOR before consecutive digits
                self.emboss_cell(NUMBER_INDICATOR)
                col_count += 1
                # consume all consecutive digits
                while i < len(text) and text[i].isdigit():
                    letter = DIGIT_TO_LETTER[text[i]]  # map 1-0 -> a-j
                    digit_dots = BRAILLE_MAP[letter]   # look up braille for the letter
                    self.emboss_cell(digit_dots)
                    col_count += 1
                    i += 1
                # i already points past the digit run, so don't increment it again
                continue

            # handle uppercase letters with a preceding capital indicator
            if ch.isalpha() and ch.isupper():
                self.emboss_cell(CAPITAL_INDICATOR)
                col_count += 1
                ch = ch.lower()  # now treat as normal lowercase letter

            # normal char path (letters, punctuation, space, etc.)
            dots = BRAILLE_MAP.get(ch)
            if dots is None:
                # char not in the map:
                if self.cfg.unknown_as_blank:
                    dots = set()  # blank cell is safer for unknowns
                else:
                    # placeholder for another policy (skip or an "unknown" pattern);
                    # currently also a blank cell
                    dots = set()
            self.emboss_cell(dots)
            col_count += 1
            i += 1

# ──────────────────────────────────────────────────────────────────────────────
# Utilities


def sanitize_text(s: str) -> str:
    """
    Normalize tabs/extra spaces into single spaces.
    Keep punctuation as-is (we handle it in BRAILLE_MAP).
    """
    return " ".join(s.replace("\t", " ").split())


def emboss_lines(embosser: BrailleEmbosser, lines: Iterable[str]) -> None:
    """
    Emboss a list/iterator of lines. Inserts a newline between lines.
    Useful when you've already wrapped or separated OCR blocks.
    """
    for idx, line in enumerate(lines):
        if idx:
            embosser.tape.newline()
        embosser.emboss_text(line)

# ──────────────────────────────────────────────────────────────────────────────
# Demo / CLI (safe to run on a laptop; replace Console* with Raspberry Pi drivers)

DEMO_TEXT = "water bottle\nhi there"


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line options. Defaults match the original demo settings."""
    parser = argparse.ArgumentParser(
        description="Braille embosser console demo. "
                    "If a text file is provided, emboss its contents."
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Optional path to a .txt file to emboss. "
             "If omitted, a built-in demo string is used."
    )
    parser.add_argument("--dwell-ms", type=int, default=35,
                        help="Strike time per column in ms (default: 35).")
    parser.add_argument("--wrap-cols", type=int, default=16,
                        help="Soft wrap width in cells, 0 disables wrapping (default: 16).")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    from pathlib import Path

    args = parse_args(argv)

    # Set up fake hardware (swap these out on the Pi)
    left = ConsoleColumn("LEFT")
    right = ConsoleColumn("RIGHT")
    tape = ConsoleTape()

    cfg = EmbossConfig(
        dwell_ms_left=args.dwell_ms,
        dwell_ms_right=args.dwell_ms,
        wrap_cols=args.wrap_cols,
        unknown_as_blank=True
    )

    emb = BrailleEmbosser(left, right, tape, cfg)

    if args.file:
        # ── Emboss from a text file ──────────────────────────────────────────
        path = Path(args.file)
        if not path.is_file():
            raise SystemExit(f"File not found: {path}")

        # Read whole file as UTF-8 text
        raw_text = path.read_text(encoding="utf-8")

        # Keep line breaks, lightly sanitize each line
        lines = [sanitize_text(line) for line in raw_text.splitlines()]
        emboss_lines(emb, lines)
    else:
        # ── Fallback demo if no file is given ───────────────────────────────
        # Note: sanitize_text collapses the "\n" into a space, so the demo
        # embosses as a single soft-wrapped line.
        emb.emboss_text(sanitize_text(DEMO_TEXT))


if __name__ == "__main__":
    main()

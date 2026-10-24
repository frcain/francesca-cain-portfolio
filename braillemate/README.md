# BrailleMate

BrailleMate is a handheld assistive device that converts printed text into tactile braille. It was built as a team capstone project in Carnegie Mellon's ECE Design Experience (18-500, Fall 2025). A Raspberry Pi camera captures text, OCR extracts it, and the device embosses it as 6-dot braille using a servo-driven mechanism.

## Project structure

- `braille_embosser.py`: Converts OCR text into actuator steps. Each character is looked up as a set of braille dots (1 to 6), split into left and right columns, encoded as servo positions, and embossed cell by cell while the tape advances. Hardware access goes through small driver interfaces (`ColumnDriver`, `TapeDriver`), so the same logic runs against console stand-ins for testing or real Raspberry Pi drivers.
- `ocr_batch.py`: Runs Tesseract OCR over a folder of test images (default `OCR data/`) and writes one `.txt` per image under `ocr_out/`, to evaluate text extraction quality.
- `fetch_open_food_facts.py` / `fetch_open_food_facts_vitamins.py`: Download sample product label images from the Open Food Facts API to build a realistic OCR test set (packaging and nutrition labels).

## Install

From the repository root: `pip install -e ".[dev]"` for the embosser and downloaders, plus `pip install -e ".[ocr]"` for `ocr_batch.py`, which also needs the Tesseract binary (for example `brew install tesseract` or `apt install tesseract-ocr`).

## Run

Embosser logic without hardware (prints each actuator step to the console):

```bash
python3 braille_embosser.py                  # built-in demo string
python3 braille_embosser.py notes.txt        # emboss a text file
python3 braille_embosser.py --wrap-cols 28 --dwell-ms 30
```

`set_output_handler()` swaps the console output for a different sink.

OCR and image downloads:

```bash
python3 ocr_batch.py --input-dir "OCR data" --output-dir ocr_out
python3 fetch_open_food_facts.py -n 100 --panel front
python3 fetch_open_food_facts_vitamins.py -n 100 --category "Vitamins"
```

## Tests

From the repository root: `python3 -m pytest -q tests/test_braille_embosser.py`. The tests check the dot lookup, pin encoding, column split, and the exact step sequence produced when embossing short strings with fake drivers.

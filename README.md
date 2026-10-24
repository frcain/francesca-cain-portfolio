# Francesca Cain: Selected Code

![tests](https://github.com/frcain/francesca-cain-portfolio/actions/workflows/tests.yml/badge.svg)

Code samples from my engineering and research work at Carnegie Mellon University, where I earned a B.S. in Electrical and Computer Engineering and Biomedical Engineering (2026) and am now pursuing an M.S. in Biomedical Engineering (Computational).

This repository is a portfolio. The projects were developed separately on my own machine and in course and team folders, then collected and uploaded here together, so the commit history here does not reflect how each project was built. The original code was written during my coursework and research. Refactoring, tests, and tooling were added with assistance from Claude Code.

| Project | What it is | Language |
|---|---|---|
| [BrailleMate](braillemate/) | Software for a handheld device that converts printed text into embossed braille (ECE capstone, team project) | Python |
| [Force-sensing tether](force-sensing-tether/) | ESP32 Bluetooth Low Energy firmware and a Python live-graphing app for a prototype scoliosis implant (BME capstone, team project) | C++ (Arduino), Python |
| [Engineering education text analysis](engineering-education-text-analysis/) | Research pipeline using TF-IDF and NMF topic modeling to analyze student design reflections across cohorts | Python |

## Install

Python 3.10 or newer. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

This installs the core dependencies (pandas, scikit-learn, matplotlib, requests, pillow), the shared `textanalysis` package in editable mode, and the dev tools (pytest, ruff, mypy). The hardware and OCR extras are separate: `pip install -e ".[tether]"` adds `bleak` for the Bluetooth apps, and `pip install -e ".[ocr]"` adds `pytesseract` (which also needs the Tesseract binary). `requirements.txt` lists the same packages for `pip install -r requirements.txt`.

## Run

Every script has a command-line interface; run it with `--help` to see the options. Defaults match the values the scripts were originally written with, so running a script with no arguments behaves as before. Scripts can be run directly, for example:

```bash
python3 engineering-education-text-analysis/driver.py --help
python3 braillemate/braille_embosser.py
```

The education scripts add the repository root to the import path themselves, so they find `textanalysis` even without `pip install -e .`.

## Test, lint, and type-check

```bash
python3 -m pytest -q      # tests
ruff check .              # lint
mypy textanalysis         # type-check the shared package
```

The tests cover pure logic only (braille encoding, the shared text helpers, cohort detection, combining tables, word counts, a small TF-IDF and NMF run, the education pipeline on temporary files, and the tether's signal smoothing and CSV logging). They use made-up text and fake hardware drivers, and need no Bluetooth device, camera, display, network, or real data. The ESP32 firmware has no automated tests and is not compiled in CI. The GitHub Actions workflow in `.github/workflows/tests.yml` runs the three commands above on Python 3.11.

## Project structure

- `textanalysis/`: shared package used by the education scripts (tokenizers and stopwords, cohort detection, CSV reading and combining, word counts, TF-IDF and NMF topic fitting, writing word counts and topic bins). Fully type-hinted and checked with mypy.
- `braillemate/`: braille embosser logic, batch OCR, and Open Food Facts image downloaders
- `engineering-education-text-analysis/`: research pipeline scripts (code only; data is confidential and not included)
- `force-sensing-tether/`: ESP32 firmware and desktop BLE apps
- `tests/`: pytest tests for the shared package and all three projects; `conftest.py` puts the repository root and each project folder on the import path
- `pyproject.toml`: package metadata, dependencies, and mypy settings
- `pytest.ini`, `ruff.toml`: pytest and ruff settings
- `requirements.txt`: the same dependencies as a plain list

Contact: fcain@andrew.cmu.edu

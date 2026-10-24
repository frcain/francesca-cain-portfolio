#!/usr/bin/env python3
"""
fetch_open_food_facts_vitamins.py
Download a sample of Open Food Facts *vitamin / supplement* product images
for OCR testing.

This is a specialization of fetch_open_food_facts.py that filters by
the Open Food Facts `categories_tags_en` field (default: "Vitamins").

Examples:
  # 100 cropped 400px FRONT images of products in the "Vitamins" category
  python3 fetch_open_food_facts_vitamins.py -n 100 --panel front

  # 50 RAW originals of the ingredients panel into ./off_vitamins_raw_50
  python3 fetch_open_food_facts_vitamins.py --raw --panel ingredients -n 50 -o off_vitamins_raw_50

  # Use a different category filter (e.g., "Dietary supplements")
  python3 fetch_open_food_facts_vitamins.py --category "Dietary supplements" -n 100

  # Smaller API pages + no delay (faster feedback)
  python3 fetch_open_food_facts_vitamins.py -n 25 -p 50 --delay 0.0
"""

from __future__ import annotations

import argparse
import os
import pathlib
import time
import urllib.parse
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API = "https://world.openfoodfacts.org/api/v2/search"

# Put a real contact here so the API has a way to reach you if needed
UA_DEFAULT = "CMU-BrailleMate/0.2 (contact: fcain@andrew.cmu.edu)"


# ──────────────────────────────────────────────────────────────────────────────
# HTTP session with retries + short timeouts (avoids long stalls)

def make_session(ua: str) -> requests.Session:
    """Create a requests session with a User-Agent and automatic retries on GET."""
    sess = requests.Session()
    sess.headers.update({"User-Agent": ua, "Connection": "close"})
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.5,  # 0.5s, 1.0s, 2.0s ...
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    return sess


# ──────────────────────────────────────────────────────────────────────────────
# API fetches

def fetch_page(
    session: requests.Session,
    page: int,
    page_size: int,
    cropped: bool,
    panel: str,
    categories_tags_en: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Get one page of products with just the fields we need, filtered by
    categories_tags_en (e.g., "Vitamins" or "Dietary supplements").

    - For CROPPED (400px): use selected_images (front/nutrition/ingredients)
    - For RAW: use image_*_url fallbacks
    """
    if cropped:
        fields = "code,selected_images"
    else:
        # RAW originals often live in these top-level fields; also include selected_images
        # as a fallback if raw URL is missing.
        fields = (
            "code,"
            "image_url,"
            "image_front_url,"
            "image_ingredients_url,"
            "image_nutrition_url,"
            "selected_images"
        )

    params: Dict[str, Any] = {
        "page": page,
        "page_size": page_size,
        "sort_by": "unique_scans_n",  # popular first → higher chance of images
        "fields": fields,
        "countries": (
            "en:united-states,en:united-kingdom,en:canada,"
            "en:australia,en:ireland,en:new-zealand"
        ),
    }

    # Restrict to vitamin/supplement-ish products
    if categories_tags_en:
        # Example: categories_tags_en=Vitamins
        params["categories_tags_en"] = categories_tags_en

    print(f"Fetching page {page} (category={categories_tags_en!r}) …", flush=True)
    r = session.get(API, params=params, timeout=(5, 60))
    r.raise_for_status()
    data = r.json()
    return data.get("products", []) or []


# ──────────────────────────────────────────────────────────────────────────────
# URL pickers

def pick_cropped_url(prod: Dict[str, Any], panel: str) -> Optional[str]:
    """
    From selected_images, pick a 400px cropped URL for the requested panel
    (front/nutrition/ingredients). We accept the first available language.
    """
    si = prod.get("selected_images") or {}
    p = si.get(panel) or {}
    display = p.get("display") or p.get("small") or p.get("thumb") or {}
    # prefer 400px (that's 'display' size in OFF parlance)
    for _, url in display.items():
        if isinstance(url, str) and url.startswith("http"):
            return url
    return None


def pick_raw_url(prod: Dict[str, Any], panel: str) -> Optional[str]:
    """
    Prefer panel-specific raw image URL fields; fall back to generic image_url
    or a cropped URL if raw missing.
    """
    key_map = {
        "front": "image_front_url",
        "ingredients": "image_ingredients_url",
        "nutrition": "image_nutrition_url",
    }
    # Try panel-specific raw first
    key = key_map.get(panel, "")
    if key:
        url = prod.get(key)
        if isinstance(url, str) and url.startswith("http"):
            return url

    # Fallback to generic raw
    url = prod.get("image_url")
    if isinstance(url, str) and url.startswith("http"):
        return url

    # Last resort: use cropped if available
    return pick_cropped_url(prod, panel)


# ──────────────────────────────────────────────────────────────────────────────
# Downloader

def safe_filename_from_url(code: str, url: str) -> str:
    """
    Build a stable, readable filename: <code>__<basename>
    """
    base = pathlib.PurePosixPath(urllib.parse.urlparse(url).path).name
    if not base:
        base = "image.jpg"
    return f"{code}__{base}"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def download_images(
    session: requests.Session,
    outdir: str,
    num: int,
    panel: str,
    cropped: bool,
    page_size: int,
    delay: float,
    categories_tags_en: Optional[str],
) -> None:
    """Page through the API and save up to `num` images into `outdir`."""
    ensure_dir(outdir)
    downloaded = 0
    page = 1
    t0 = time.time()

    while downloaded < num:
        products = fetch_page(
            session=session,
            page=page,
            page_size=page_size,
            cropped=cropped,
            panel=panel,
            categories_tags_en=categories_tags_en,
        )
        if not products:
            print("No more products returned. Stopping.")
            break

        for prod in products:
            if downloaded >= num:
                break

            code = str(prod.get("code") or "").strip() or "unknown"
            url = pick_cropped_url(prod, panel) if cropped else pick_raw_url(prod, panel)
            if not url:
                continue

            fn = safe_filename_from_url(code, url)
            dst = os.path.join(outdir, fn)
            if os.path.exists(dst):
                # already there, skip
                continue

            try:
                resp = session.get(url, timeout=(5, 20))
                if resp.status_code == 200 and resp.content:
                    with open(dst, "wb") as f:
                        f.write(resp.content)
                    downloaded += 1
                    elapsed = max(1e-6, time.time() - t0)
                    rate = downloaded / elapsed
                    print(f"[{downloaded}/{num}] saved {fn}  —  {rate:.2f} img/s", flush=True)
                else:
                    # skip non-200 or empty responses
                    continue
            except requests.RequestException as e:
                # network hiccup, skip and continue
                print(f"skip ({type(e).__name__}): {url}", flush=True)
                continue

            if delay > 0:
                time.sleep(delay)

        page += 1

    print(f"Done. Downloaded {downloaded} files into: {outdir}")


# ──────────────────────────────────────────────────────────────────────────────
# CLI

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Download Open Food Facts images for OCR testing, "
            "filtered to vitamin / supplement categories via categories_tags_en."
        )
    )
    p.add_argument(
        "-n",
        "--num",
        type=int,
        default=1000,
        help="Number of images to download (default: 1000).",
    )
    p.add_argument(
        "-o",
        "--outdir",
        default="off_vitamins",
        help="Output folder (default: off_vitamins).",
    )
    p.add_argument(
        "-p",
        "--page-size",
        type=int,
        default=100,
        help="API page size (default: 100).",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="Sleep seconds between downloads (default: 0.1). Use 0.0 to disable.",
    )
    p.add_argument(
        "--panel",
        choices=["front", "ingredients", "nutrition"],
        default="front",
        help="Which panel to fetch (default: front).",
    )
    p.add_argument(
        "--raw",
        action="store_true",
        help="Download raw originals instead of cropped 400px.",
    )
    p.add_argument(
        "--ua",
        default=UA_DEFAULT,
        help="User-Agent string to use (please include a contact).",
    )
    p.add_argument(
        "--category",
        default="Vitamins",
        help=(
            "Value for the Open Food Facts `categories_tags_en` filter "
            '(default: "Vitamins"). Examples: "Vitamins", "Dietary supplements".'
        ),
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    session = make_session(args.ua)

    mode = "RAW" if args.raw else "CROPPED-400"
    print(f"Mode: {mode}  | Panel: {args.panel}  | Target: {args.num}  | Out: {args.outdir}")
    print(f"Page size: {args.page_size}  | Delay: {args.delay}s  | UA: {args.ua}")
    print(f"Category filter (categories_tags_en): {args.category!r}")

    download_images(
        session=session,
        outdir=args.outdir,
        num=args.num,
        panel=args.panel,
        cropped=(not args.raw),
        page_size=args.page_size,
        delay=args.delay,
        categories_tags_en=args.category,
    )


if __name__ == "__main__":
    main()

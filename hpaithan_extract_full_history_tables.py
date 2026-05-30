#!/usr/bin/env python3
"""
Full PDF Table Extraction -> one CSV per PDF (Responses API + schema)

# PYTHON VERSION:
# python --version
# Python 3.13.2

REQUIRED: this script expects the API key file at:
./course_api_key.txt

This script:
- scans each PDF page to find likely "field tables" (Key/Item/Data Type/Format/Length/Start/End/Comments)
- sends only those candidate pages to the Responses API (vision)
- enforces structured outputs using structure.json
- validates responses using structure.py (Pydantic)
- writes one final CSV per PDF

Logging behavior:
- Prints PDF + Pages immediately (so you see output right away)
- Does NOT print per-page extraction lines
- Optionally prints a short progress line every N candidate pages
- Prints final summary in the requested format
"""

import argparse
import base64
import csv
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF
from openai import OpenAI

from structure import DataExtractionResponse


USERNAME = "hpaithan"
MODEL = "gpt-5-nano"

COURSE_API_KEY_PATH = "./course_api_key.txt"
STRUCTURE_JSON_PATH = "./structure.json"
STRUCTURE_PY_PATH = "./structure.py"

PDF_JOBS = [
    {
        "pdf_path": "./ibes_detail_history_docs_extended.pdf",
        "out_csv": "./ibes_detail_history_docs_extended.csv",
    },
    {
        "pdf_path": "./ibes_summary_history_docs_extended.pdf",
        "out_csv": "./ibes_summary_history_docs_extended.csv",
    },
]

CSV_HEADER = ["file_name", "key", "item", "data_type", "format", "length", "start", "end", "comments"]
CANDIDATE_KEYWORDS = ["Key", "Item", "Data Type", "Format", "Length", "Start", "End", "Comments"]

# Set to 0 to disable progress printing entirely
PROGRESS_EVERY = 25


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def read_api_key(path: str) -> str:
    if not os.path.exists(path):
        die(
            f"API key file not found at: {path}\n"
            "Create course_api_key.txt in the same folder and put your course key inside (single line)."
        )
    key = open(path, "r", encoding="utf-8").read().strip()
    if not key or " " in key or not key.startswith("sk-"):
        die("API key file exists but does not look valid. It must be a single line starting with sk-.")
    return key


def load_schema_format(structure_json_path: str) -> Dict[str, Any]:
    if not os.path.exists(structure_json_path):
        die(f"Missing schema file: {structure_json_path}")
    data = json.load(open(structure_json_path, "r", encoding="utf-8"))
    if "format" not in data:
        die("structure.json must contain a top-level key named 'format'")
    return data["format"]


def normalize_whitespace(s: str) -> str:
    return " ".join(s.split())


def keyword_hit_count(page_text: str) -> int:
    if not page_text:
        return 0
    t = normalize_whitespace(page_text).lower()
    hits = 0
    for kw in CANDIDATE_KEYWORDS:
        if kw.lower() in t:
            hits += 1
    return hits


def is_candidate_page(page_text: str, min_hits: int) -> bool:
    return keyword_hit_count(page_text) >= min_hits


def render_page_to_data_url(doc: fitz.Document, page_index: int, zoom: float) -> str:
    page = doc.load_page(page_index)
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    png_bytes = pix.tobytes("png")
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def flatten_records(validated: DataExtractionResponse, pdf_base_name: str) -> List[Dict[str, Any]]:
    """
    Convert Pydantic records to dict rows matching CSV_HEADER order.
    Also removes exact duplicates within the same page (common model duplication issue).
    """
    out: List[Dict[str, Any]] = []
    seen = set()

    for r in validated.data_records:
        row = {
            "file_name": pdf_base_name,  # enforce exact file_name value
            "key": r.key,
            "item": r.item,
            "data_type": r.data_type,
            "format": r.format,
            "length": r.length,
            "start": r.start,
            "end": r.end,
            "comments": r.comments,
        }

        sig = tuple(row[c] for c in CSV_HEADER)
        if sig not in seen:
            seen.add(sig)
            out.append(row)

    return out


def call_responses_extract_page(
    client: OpenAI,
    schema_format: Dict[str, Any],
    image_data_url: str,
    pdf_base_name: str,
    page_index_0based: int,
    max_retries: int = 3,
) -> DataExtractionResponse:
    """
    Extract rows from the target table(s) on a single page.
    If the page has no such table, the model should return {"data_records": []}.
    We validate the JSON against structure.py (Pydantic).
    """
    page_1based = page_index_0based + 1

    instructions = f"""
You are extracting tabular data from a PDF page screenshot.

Return JSON that matches the provided schema EXACTLY:
- Top-level key: data_records (array)
- Each record must include:
  file_name (string), key (string), item (string), data_type (string), format (string),
  length (integer), start (integer), end (integer), comments (string)

Rules:
1) Only extract rows from tables whose columns correspond to:
   Key, Item, Data Type, Format, Length, Start, End, Comments.
2) Do not invent rows. Do not guess values.
3) Do not output header rows (like "Key Item Data Type ...").
4) Preserve text exactly as shown (case, punctuation).
5) length/start/end MUST be integers. If any numeric cell is blank/unknown, use -1.
6) comments must be a string; if blank, use "na".
7) file_name must be exactly: "{pdf_base_name}"
8) If this page has no such table, return: {{"data_records": []}}

Context: this is PDF page {page_1based}. Ignore any printed page number discrepancies.
""".strip()

    last_error: Optional[str] = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = client.responses.create(
                model=MODEL,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": instructions}]},
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": "Extract the matching table rows from this page."},
                            {"type": "input_image", "image_url": image_data_url, "detail": "high"},
                        ],
                    },
                ],
                text={"format": schema_format},
            )

            parsed = json.loads(resp.output_text)
            validated = DataExtractionResponse.model_validate(parsed)

            # enforce correct file_name again
            for rec in validated.data_records:
                rec.file_name = pdf_base_name

            return validated

        except Exception as e:
            last_error = str(e)
            time.sleep(1.5 * attempt)

    die(f"Failed to extract page {page_1based} after {max_retries} attempts. Last error: {last_error}")
    raise RuntimeError("unreachable")


def get_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--start-page", type=int, default=0, help="0-based start page index (default 0)")
    p.add_argument("--end-page", type=int, default=None, help="0-based end page index (inclusive). Default: last page")
    p.add_argument("--all-pages", action="store_true", help="Process every page (more API calls; use only if needed)")
    p.add_argument("--zoom", type=float, default=3.5, help="Render zoom for page images (default 3.5)")
    p.add_argument("--min-hits", type=int, default=6, help="Keyword hit threshold for candidate detection (default 6)")
    return p.parse_args()


def write_csv_streaming(out_path: str, rows_iter: List[Dict[str, Any]]) -> None:
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        w.writeheader()
        for r in rows_iter:
            w.writerow(r)


def sanity_bad_count(rows: List[Dict[str, Any]]) -> int:
    """
    Simple sanity check on the rows we already extracted:
    - required columns exist
    - numeric fields are integers
    """
    bad = 0
    for r in rows:
        # required columns
        for col in CSV_HEADER:
            if col not in r or r[col] is None:
                bad += 1
                break
        else:
            # numeric checks
            if not isinstance(r["length"], int) or not isinstance(r["start"], int) or not isinstance(r["end"], int):
                bad += 1
    return bad


def main() -> None:
    args = get_args()

    # quick sanity checks
    for need in [STRUCTURE_JSON_PATH, STRUCTURE_PY_PATH]:
        if not os.path.exists(need):
            die(f"Missing required schema file: {need}")

    api_key = read_api_key(COURSE_API_KEY_PATH)
    schema_format = load_schema_format(STRUCTURE_JSON_PATH)
    client = OpenAI(api_key=api_key)

    for job in PDF_JOBS:
        pdf_path = job["pdf_path"]
        out_csv = job["out_csv"]

        if not os.path.exists(pdf_path):
            die(f"Missing PDF: {pdf_path}")

        doc = fitz.open(pdf_path)
        pdf_base = os.path.basename(pdf_path)
        total_pages = doc.page_count

        start = args.start_page
        end = args.end_page if args.end_page is not None else total_pages - 1

        if start < 0 or start >= total_pages:
            die(f"Invalid --start-page {start} for total pages {total_pages}")
        if end < start or end >= total_pages:
            die(f"Invalid --end-page {end} for total pages {total_pages}")

        # Print immediately so you see output right away
        print(f"PDF: {pdf_path}", flush=True)
        print(f"Pages: {total_pages}", flush=True)

        # Candidate detection
        if args.all_pages:
            candidate_pages = list(range(start, end + 1))
        else:
            candidate_pages = []
            for pidx in range(start, end + 1):
                txt = doc.load_page(pidx).get_text("text")
                if is_candidate_page(txt, min_hits=args.min_hits):
                    candidate_pages.append(pidx)

            if len(candidate_pages) == 0:
                doc.close()
                die("No candidate pages found. Try --min-hits 5 or --all-pages.")

        # Extraction (no per-page print)
        extracted_rows: List[Dict[str, Any]] = []

        for i, pidx in enumerate(candidate_pages, start=1):
            if PROGRESS_EVERY > 0 and (i % PROGRESS_EVERY == 0):
                print(f"  Progress: {i}/{len(candidate_pages)} candidate pages processed...", flush=True)

            img_url = render_page_to_data_url(doc, pidx, zoom=args.zoom)
            validated = call_responses_extract_page(
                client=client,
                schema_format=schema_format,
                image_data_url=img_url,
                pdf_base_name=pdf_base,
                page_index_0based=pidx,
            )
            rows = flatten_records(validated, pdf_base_name=pdf_base)
            if rows:
                extracted_rows.extend(rows)

        doc.close()

        # Write CSV
        write_csv_streaming(out_csv, extracted_rows)

        # Summary output (matches your desired format)
        total = len(extracted_rows)
        bad = sanity_bad_count(extracted_rows)

        print(f"Rows kept: {total}", flush=True)
        print(f"Sanity: total={total}, bad={bad}", flush=True)
        print(f"Wrote: {os.path.basename(out_csv)}  (rows: {total})", flush=True)
        print("", flush=True)  # blank line between PDFs


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync review articles from bd_text Google Sheet.
Writes content/<lang>/reviews/<category>/<brand_slug>/<model_slug>/<capacity_slug>/_index.md
"""

import csv
import io
import re
from pathlib import Path
from typing import Dict, List
from urllib.request import urlopen

# bd_text spreadsheet (review sheet)
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSLFEW2jV1SY7MJg4OS74MYzoyksW7AETNOc8wo1z2qHFM9nNA2Ta42hP7mvuccpjZs27MoI7TzoQxW/pub?gid=0&single=true&output=csv"

OUT_ROOT = Path(__file__).resolve().parent.parent / "content"


def norm_header(h: str) -> str:
    h = (h or "").strip()
    h = h.replace(" ", "_")
    h = re.sub(r"[^a-zA-Z0-9_]", "", h)
    return h.lower()


def read_csv(url: str) -> List[Dict[str, str]]:
    sep = "&" if "?" in url else "?"
    raw = urlopen(f"{url}{sep}ts={__import__('time').time_ns()}").read().decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(raw))
    rows = list(reader)
    if not rows:
        return []

    headers = [norm_header(h) for h in rows[0]]
    out: List[Dict[str, str]] = []
    for line in rows[1:]:
        d: Dict[str, str] = {}
        for i, h in enumerate(headers):
            d[h] = (line[i] if i < len(line) else "").strip()
        out.append(d)
    return out


def truthy(v: str) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def yaml_quote(s: str) -> str:
    if s is None:
        return '""'
    s = (s or "").strip().replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{s}"'


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding=encoding, newline="\n")
    tmp.replace(path)


def build_review_md(row: Dict[str, str]) -> str:
    title = (row.get("title") or "").strip()
    if not title:
        brand = (row.get("brand") or "").strip()
        model = (row.get("model") or "").strip()
        cap = (row.get("capacity_label") or "").strip()
        title = f"{brand} {model} {cap} — Review".strip() or "Review"

    breadcrumb = (row.get("breadcrumb_title") or row.get("capacity_label") or "").strip()
    description = (row.get("description") or "").strip()
    text = (row.get("text") or "").strip()

    lines = [
        "---",
        f"title: {yaml_quote(title)}",
        f"breadcrumbTitle: {yaml_quote(breadcrumb)}",
        f"description: {yaml_quote(description)}",
        "---",
        "",
        text if text else "",
    ]
    return "\n".join(lines)


def main() -> int:
    rows = read_csv(CSV_URL)
    count = 0

    for r in rows:
        if not truthy(r.get("published", "")):
            continue

        category = (r.get("category") or "").strip()
        brand_slug = (r.get("brand_slug") or "").strip()
        model_slug = (r.get("model_slug") or "").strip()
        cap_slug = (r.get("capacity_slug") or "").strip()
        lang = (r.get("lang") or "en").strip().lower() or "en"

        if not (category and brand_slug and model_slug and cap_slug):
            continue

        out_dir = OUT_ROOT / lang / "reviews" / category / brand_slug / model_slug / cap_slug
        out_file = out_dir / "_index.md"
        atomic_write_text(out_file, build_review_md(r))
        print(f"Review: {out_file}")
        count += 1

    print(f"Done. {count} review(s) written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.request import urlopen
from datetime import datetime, timezone


CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSNY87-WIChWcLHd8Ilyx4Smy8hxRC690C4wjhb_yLgfi3uooSD91Pw6TZiK83n269O8AC_3koMsI1-/pub?gid=0&single=true&output=csv"

OUT_ROOT = Path("content")


def norm_header(h: str) -> str:
    h = (h or "").strip()
    h = h.replace(" ", "_")
    h = re.sub(r"[^a-zA-Z0-9_]", "", h)
    return h.lower()


def read_csv(url: str) -> List[Dict[str, str]]:
    sep = "&" if "?" in url else "?"
    raw = urlopen(f"{url}{sep}ts={__import__('time').time_ns()}").read().decode("utf-8", errors="replace")
    reader = csv.reader(raw.splitlines())
    rows = list(reader)
    if not rows:
        return []

    headers = [norm_header(h) for h in rows[0]]
    data: List[Dict[str, str]] = []

    for r in rows[1:]:
        if len(r) < len(headers):
            r = r + [""] * (len(headers) - len(r))
        item = {headers[i]: (r[i].strip() if i < len(r) else "") for i in range(len(headers))}
        if all(v == "" for v in item.values()):
            continue
        data.append(item)

    return data


def truthy(v: str) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def esc_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def parse_number(s: str):
    """
    Parse first float/int from string.
    Examples:
      "511" -> 511.0
      "511 (516)" -> 511.0
      "" -> None
    """
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", t.replace(",", "."))
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


# ==========================
# CALCULATOR JSON GENERATION
# ==========================

def build_calculator_json(rows: List[Dict[str, str]]) -> List[Dict]:
    """
    Builds calculator models from SAME table.

    We map by:
      section_key:
        - fresh_seq_write_250gib => slc_speed, sus_speed, slc_gib
        - seq_read_250gib        => seq_speed

      metrics (robust):
        - by metric_key (preferred when stable)
        - and by metric_label (fallback)
    Values:
      - use avg (requested)
      - fallback: parse first number from avg_median (e.g. "511 (516)" -> 511)
    """
    models: Dict[str, Dict] = {}

    for r in rows:
        section = (r.get("section_key") or "").strip()
        metric_key = (r.get("metric_key") or "").strip().lower()
        metric_label = (r.get("metric_label") or "").strip().lower()

        key = (
            (r.get("brand_slug") or "").strip(),
            (r.get("model_slug") or "").strip(),
            (r.get("capacity_slug") or "").strip(),
            (r.get("lang") or "").strip(),
        )
        if not all(key):
            continue

        model_id = "_".join(key)

        # capacity (GiB) comes from the source table (same for all rows of a model)
        cap_gib = parse_number(r.get("capacity_gib"))
        if isinstance(cap_gib, float) and cap_gib.is_integer():
            cap_gib = int(cap_gib)

        if model_id not in models:
            models[model_id] = {
                "model_id": model_id,
                "name": f'{(r.get("brand") or "").strip()} {(r.get("model") or "").strip()} {(r.get("capacity_label") or "").strip()}',
                "capacity_gib": cap_gib,
                "slc_speed": None,
                "slc_gib": None,
                "sus_speed": None,
                "seq_speed": None,
            }
        else:
            # Fill capacity if it was missing on the first encountered row
            if models[model_id].get("capacity_gib") is None and cap_gib is not None:
                models[model_id]["capacity_gib"] = cap_gib

        # value: avg preferred, fallback avg_median
        value = parse_number(r.get("avg"))
        if value is None:
            value = parse_number(r.get("avg_median"))
        if value is None:
            continue

        # helpers for matching
        is_avg_speed = ("avg_speed" in metric_key) or ("avg speed" in metric_label)
        is_slc_speed = ("slc_speed" in metric_key) or ("slc speed" in metric_label)
        is_sustained = ("sustained" in metric_key) or ("sustained" in metric_label)
        is_slc_gib = (("slc" in metric_key and "gib" in metric_key) or ("gib" in metric_label and "slc" in metric_label))

        # WRITE
        if section == "fresh_seq_write_250gib":
            if is_slc_speed:
                models[model_id]["slc_speed"] = value
            elif is_sustained:
                models[model_id]["sus_speed"] = value
            elif is_slc_gib:
                models[model_id]["slc_gib"] = value

        # READ
        if section == "seq_read_250gib":
            if is_avg_speed:
                models[model_id]["seq_speed"] = value

    # keep only complete models
    result = [
        m for m in models.values()
        if (
            m.get("capacity_gib") is not None and
            m["slc_speed"] is not None and
            m["slc_gib"] is not None and
            m["sus_speed"] is not None and
            m["seq_speed"] is not None
        )
    ]
    return result


def write_calculator_json(models: List[Dict]) -> None:
    out_file = Path("static/data/calculator.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)

    tmp_file = out_file.with_suffix(out_file.suffix + ".tmp")

    tmp_file.write_text(
        json.dumps(models, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    # atomic replace (Hugo/браузер не увидит "полуфайл")
    tmp_file.replace(out_file)

    print(f"Calculator JSON generated: {out_file}")


# ==========================
# CALCULATOR PAGE GENERATION
# ==========================

def now_rfc3339() -> str:
    # local timezone if available, otherwise UTC
    try:
        dt = datetime.now().astimezone()
    except Exception:
        dt = datetime.now(timezone.utc)
    # Hugo likes RFC3339
    return dt.replace(microsecond=0).isoformat()


def collect_calculators(rows: List[Dict[str, str]]) -> Dict[Tuple[str, str], str]:
    """
    Returns {(lang, calc_slug): calc_name} deduped from the same published table.
    Your sheet repeats calc_* for every metric row -> we dedupe by (lang, slug).
    """
    out: Dict[Tuple[str, str], str] = {}
    for r in rows:
        lang = (r.get("lang") or "").strip()
        slug = (r.get("calc_slug") or "").strip()
        name = (r.get("calc_name") or "").strip()
        if not (lang and slug and name):
            continue
        out[(lang, slug)] = name  # last one wins (they should be identical anyway)
    return out


def build_calc_md(title: str) -> str:
    """
    Minimal MD page. We intentionally keep body empty (no manual edits expected).
    Hugo will render this page using your calculators section template.
    """
    t = (title or "").replace('"', r"\"")
    dt = now_rfc3339()
    front = [
        "---",
        f'title: "{t}"',
        f'date: "{dt}"',
        f'lastmod: "{dt}"',
        "---",
        "",
        # body can stay empty
        "",
    ]
    return "\n".join(front)


def write_calculator_pages(calcs: Dict[Tuple[str, str], str]) -> None:
    """
    Writes content/<lang>/calculators/<calc_slug>.md for each calculator.
    Overwrites on every run.
    Also removes old calculator md files not present in current set (per lang),
    excluding _index.md.
    """
    # group by lang for cleanup
    by_lang: Dict[str, Dict[str, str]] = {}
    for (lang, slug), name in calcs.items():
        by_lang.setdefault(lang, {})[slug] = name

    for lang, items in by_lang.items():
        out_dir = OUT_ROOT / lang / "calculators"
        out_dir.mkdir(parents=True, exist_ok=True)

        # write/update
        for slug, name in sorted(items.items()):
            out_file = out_dir / f"{slug}.md"
            out_file.write_text(build_calc_md(name), encoding="utf-8")
            print(f"Calculator page: {out_file}")

        # cleanup (remove files not in sheet)
        keep = {f"{slug}.md" for slug in items.keys()}
        for p in out_dir.glob("*.md"):
            if p.name == "_index.md":
                continue
            if p.name not in keep:
                try:
                    p.unlink()
                    print(f"Removed old calculator page: {p}")
                except Exception as e:
                    print(f"WARNING: failed to remove {p}: {e}")


# ==========================
# ORIGINAL PAGE GENERATION
# ==========================

def build_md(page_rows: List[Dict[str, str]]) -> str:
    r0 = page_rows[0]

    brand = r0.get("brand", "").strip()
    model = r0.get("model", "").strip()
    cap_label = r0.get("capacity_label", "").strip()

    brand_slug = r0.get("brand_slug", "").strip()
    model_slug = r0.get("model_slug", "").strip()
    capacity_slug = r0.get("capacity_slug", "").strip()

    title = f"{brand} {model} {cap_label} - Raw Test Data"

    description = (
        f"Independent technical performance measurements of the "
        f"{brand} {model} {cap_label} conducted in a controlled test "
        f"environment in accordance with the standardized Eugen Standard methodology."
    )

    capacity_gib = r0.get("capacity_gib", "")
    serial_number = r0.get("serial_number", "")
    firmware = r0.get("firmware", "")
    operating_system = r0.get("operating_system", "")
    fio_version = r0.get("fio_version", "")

    sections: Dict[str, List[Dict[str, str]]] = {}
    for rr in page_rows:
        sk = rr.get("section_key", "")
        if not sk:
            continue
        sections.setdefault(sk, []).append(rr)

    html: List[str] = []
    html.append("{{< rawhtml >}}")
    html.append("")
    html.append("<h2>Test unit &amp; environment</h2>")
    html.append('<table class="meta-table"><tbody>')
    html.append(f"<tr><th>SSD model</th><td>{esc_html(brand + ' ' + model)}</td></tr>")
    html.append(f"<tr><th>Capacity (GiB)</th><td>{esc_html(capacity_gib)}</td></tr>")
    html.append(f"<tr><th>Serial number</th><td>{esc_html(serial_number)}</td></tr>")
    html.append(f"<tr><th>Firmware</th><td>{esc_html(firmware)}</td></tr>")
    html.append(f"<tr><th>Operating system</th><td>{esc_html(operating_system)}</td></tr>")
    html.append(f"<tr><th>Fio version</th><td>{esc_html(fio_version)}</td></tr>")
    html.append("</tbody></table>")

    for sk, rows in sections.items():
        section_title = rows[0].get("section_title", sk)
        html.append(f"<h2>{esc_html(section_title)}</h2>")
        html.append('<table class="data-table">')
        html.append("<thead><tr>")
        html.append("<th>Metric</th>")
        html.append("<th>Average (Median)</th>")
        html.append("<th>Attempt 1</th><th>Attempt 2</th><th>Attempt 3</th>")
        html.append("</tr></thead><tbody>")

        for rr in rows:
            html.append(
                f"<tr><td>{esc_html(rr.get('metric_label',''))}</td>"
                f"<td class='kpi'>{esc_html(rr.get('avg_median',''))}</td>"
                f"<td>{esc_html(rr.get('attempt1_value',''))}</td>"
                f"<td>{esc_html(rr.get('attempt2_value',''))}</td>"
                f"<td>{esc_html(rr.get('attempt3_value',''))}</td></tr>"
            )

        html.append("</tbody></table>")

    html.append("{{< /rawhtml >}}")

    # Front matter with structured params for breadcrumbs/lists
    front = [
        "---",
        f'title: "{title}"',
        f'description: "{description}"',
        f'brand: "{brand}"',
        f'model: "{model}"',
        f'brand_slug: "{brand_slug}"',
        f'model_slug: "{model_slug}"',
        f'capacity_label: "{cap_label}"',
        f'capacity_slug: "{capacity_slug}"',
        "---",
        "",
    ]

    return "\n".join(front + html)


def write_index_md(path: Path, title: str) -> None:
    """
    Creates a Hugo section index file. We do NOT overwrite if it already exists,
    so you can later add descriptions manually without losing them.
    """
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_title = (title or "").replace('"', r"\"")
    fm = f'---\ntitle: "{safe_title}"\n---\n'
    path.write_text(fm, encoding="utf-8")


def main() -> int:
    rows = read_csv(CSV_URL)
    rows = [r for r in rows if truthy(r.get("published", ""))]

    # ===== calculator json (from the SAME published rows) =====
    calc_models = build_calculator_json(rows)
    write_calculator_json(calc_models)

    # ===== calculator pages (from calc_name/calc_slug in SAME published rows) =====
    calcs = collect_calculators(rows)
    write_calculator_pages(calcs)

    pages: Dict[tuple, List[Dict[str, str]]] = {}
    brand_indexes: Dict[tuple, str] = {}
    model_indexes: Dict[tuple, str] = {}

    for r in rows:
        lang = (r.get("lang") or "").strip()
        category = (r.get("category") or "").strip()

        brand_slug = (r.get("brand_slug") or "").strip()
        model_slug = (r.get("model_slug") or "").strip()
        capacity_slug = (r.get("capacity_slug") or "").strip()

        if not (lang and category and brand_slug and model_slug and capacity_slug):
            continue

        brand = (r.get("brand") or "").strip()
        model = (r.get("model") or "").strip()

        # Collect section titles
        brand_key = (lang, category, brand_slug)
        if brand_key not in brand_indexes:
            brand_indexes[brand_key] = brand or brand_slug

        model_key = (lang, category, brand_slug, model_slug)
        if model_key not in model_indexes:
            # IMPORTANT: model title should NOT include brand (avoid breadcrumb duplicates)
            model_indexes[model_key] = model or model_slug

        key = (lang, category, brand_slug, model_slug, capacity_slug)
        pages.setdefault(key, []).append(r)

    # 1) Write leaf pages (capacity)
    for (lang, category, brand_slug, model_slug, capacity_slug), page_rows in sorted(pages.items()):
        out_dir = OUT_ROOT / lang / "data" / category / brand_slug / model_slug / capacity_slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "index.md"
        out_file.write_text(build_md(page_rows), encoding="utf-8")
        print(f"Wrote: {out_file}")

    # 2) Write section indexes (brand/model)
    for (lang, category, brand_slug), title in sorted(brand_indexes.items()):
        p = OUT_ROOT / lang / "data" / category / brand_slug / "_index.md"
        write_index_md(p, title)
        print(f"Index: {p}")

    for (lang, category, brand_slug, model_slug), title in sorted(model_indexes.items()):
        p = OUT_ROOT / lang / "data" / category / brand_slug / model_slug / "_index.md"
        write_index_md(p, title)
        print(f"Index: {p}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
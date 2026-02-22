#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from urllib.request import urlopen

CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSNY87-WIChWcLHd8Ilyx4Smy8hxRC690C4wjhb_yLgfi3uooSD91Pw6TZiK83n269O8AC_3koMsI1-/pub?gid=0&single=true&output=csv"

OUT_ROOT = Path("content")
TARGET_LANGS = ("en", "de")
FALLBACK_TO_EN_IF_MISSING = True

CALC_SECTION_DIR = Path("calculators")
CALC_SLUG = "external-ssd-read-write-time-calculator"
CALC_REL_DIR = CALC_SECTION_DIR / CALC_SLUG

# For Hugo translation linking (language switch, relref stability, etc.)
CALC_TRANSLATION_KEY = "calc-external-ssd-read-write-time"


# -------------------------
# CSV helpers
# -------------------------

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
    out: List[Dict[str, str]] = []
    for line in rows[1:]:
        d: Dict[str, str] = {}
        for i, h in enumerate(headers):
            d[h] = (line[i] if i < len(line) else "").strip()
        out.append(d)
    return out


def truthy(v: str) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def humanize_slug(s: str) -> str:
    """
    external-ssd -> External SSD
    usb-cable -> Usb Cable (ok as fallback)
    """
    s = (s or "").strip()
    if not s:
        return s
    parts = re.split(r"[-_]+", s)
    out: List[str] = []
    for p in parts:
        if not p:
            continue
        u = p.upper()
        if u in {"SSD", "HDD", "USB", "NVME", "TB", "GB", "MB", "KIO", "GIB"}:
            out.append(u)
        else:
            out.append(p[:1].upper() + p[1:].lower())
    return " ".join(out)


def split_rows_by_lang(rows: List[Dict[str, str]], default_lang: str = "en") -> Dict[str, List[Dict[str, str]]]:
    by: Dict[str, List[Dict[str, str]]] = {}
    for r in rows:
        lang = (r.get("lang") or "").strip().lower() or default_lang
        r["lang"] = lang
        by.setdefault(lang, []).append(r)
    return by


def html_escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fnum(x: str) -> Optional[float]:
    x = (x or "").strip()
    if not x:
        return None
    try:
        return float(x)
    except Exception:
        try:
            return float(x.replace(",", "."))
        except Exception:
            return None


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding=encoding, newline="\n")
    tmp.replace(path)


# -------------------------
# Calculator JSON
# -------------------------

def build_calculator_json(rows: List[Dict[str, str]]) -> List[Dict]:
    """
    Build a single JSON used by calculator UI.
    Reads from EN rows (recommended) to avoid duplicates if DE appears later.

    Uses:
      section_key: fresh_seq_write_250gib, seq_read_250gib
      metric_key : slc_speed_mb_s, sustained_speed_mb_s, slc_data_gib, avg_speed_mb_s
      avg_median : numeric
    """

    def pick(model_rows: List[Dict[str, str]], section_key: str, metric_key: str) -> Optional[float]:
        for rr in model_rows:
            if (rr.get("section_key") or "").strip() == section_key and (rr.get("metric_key") or "").strip() == metric_key:
                return fnum(rr.get("avg_median") or "")
        return None

    grouped: Dict[str, List[Dict[str, str]]] = {}
    meta: Dict[str, Dict[str, str]] = {}

    for r in rows:
        category = (r.get("category") or "").strip()
        brand_slug = (r.get("brand_slug") or "").strip()
        model_slug = (r.get("model_slug") or "").strip()
        cap_slug = (r.get("capacity_slug") or "").strip()

        if not (category and brand_slug and model_slug and cap_slug):
            continue

        key = f"{category}/{brand_slug}/{model_slug}/{cap_slug}"
        grouped.setdefault(key, []).append(r)

        if key not in meta:
            meta[key] = {
                "category": category,
                "brand": (r.get("brand") or "").strip(),
                "model": (r.get("model") or "").strip(),
                "capacity_label": (r.get("capacity_label") or "").strip(),
                "brand_slug": brand_slug,
                "model_slug": model_slug,
                "capacity_slug": cap_slug,
            }

    out: List[Dict] = []
    for key in sorted(grouped.keys()):
        rs = grouped[key]
        m = meta[key]

        slc_speed = pick(rs, "fresh_seq_write_250gib", "slc_speed_mb_s")
        sustained_speed = pick(rs, "fresh_seq_write_250gib", "sustained_speed_mb_s")
        slc_size_gib = pick(rs, "fresh_seq_write_250gib", "slc_data_gib")
        read_speed = pick(rs, "seq_read_250gib", "avg_speed_mb_s")

        item = {
            "id": f"{m['brand_slug']}_{m['model_slug']}_{m['capacity_slug']}",
            "name": f"{m['brand']} {m['model']} {m['capacity_label']}".strip(),

            **m,

            "slc_speed": slc_speed,
            "slc_size_gib": slc_size_gib,
            "sustained_speed": sustained_speed,
            "read_speed": read_speed,

            "slcSpeed": slc_speed,
            "slcGiB": slc_size_gib,
            "sustainedSpeed": sustained_speed,
            "readSpeed": read_speed,
        }
        out.append(item)

    return out


def write_calculator_json(models: List[Dict]) -> None:
    out_file = Path("static/data/calculator.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = out_file.with_suffix(out_file.suffix + ".tmp")
    tmp_file.write_text(json.dumps(models, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    tmp_file.replace(out_file)
    print(f"Calculator JSON generated: {out_file}")


# -------------------------
# Calculator pages Markdown (EN+DE) + calculators/_index.md
# -------------------------

def build_calculators_section_index_md(lang: str) -> str:
    if lang == "de":
        title = "Rechner"
        description = "Tools zur Berechnung von Zeiten und Geschwindigkeiten basierend auf echten Messdaten."
    else:
        title = "Calculators"
        description = "Tools to estimate times and speeds based on real measurements."

    return "\n".join([
        "---",
        f'title: "{title}"',
        f'description: "{description}"',
        "---",
        "",
    ])


def write_calculators_section_index_pages() -> None:
    for lang in TARGET_LANGS:
        out_file = OUT_ROOT / lang / CALC_SECTION_DIR / "_index.md"
        atomic_write_text(out_file, build_calculators_section_index_md(lang))
        print(f"Calculators section index: {out_file}")


def build_calculator_md(lang: str) -> str:
    if lang == "de":
        title = "External SSD Lese- & Schreibzeit-Rechner"
        description = "Berechne reale Lese- und Schreibzeiten basierend auf SLC-Cache und Sustained Speed."
    else:
        title = "External SSD Read & Write Time Calculator"
        description = "Calculate real read/write times based on SLC cache and sustained speed."

    lines: List[str] = []
    lines.append("---")
    lines.append(f'title: "{title}"')
    lines.append(f'description: "{description}"')
    lines.append(f'translationKey: "{CALC_TRANSLATION_KEY}"')
    lines.append('layout: "calculator"')
    lines.append(f'slug: "{CALC_SLUG}"')
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def write_calculator_pages() -> None:
    for lang in TARGET_LANGS:
        out_dir = OUT_ROOT / lang / CALC_REL_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "index.md"
        atomic_write_text(out_file, build_calculator_md(lang))
        print(f"Calculator page: {out_file}")


# -------------------------
# Data pages Markdown generation (i18n-safe keys in data-attrs)
# -------------------------

def build_md(page_rows: List[Dict[str, str]]) -> str:
    r0 = page_rows[0]

    brand = (r0.get("brand") or "").strip()
    model = (r0.get("model") or "").strip()
    cap_label = (r0.get("capacity_label") or "").strip()

    brand_slug = (r0.get("brand_slug") or "").strip()
    model_slug = (r0.get("model_slug") or "").strip()
    cap_slug = (r0.get("capacity_slug") or "").strip()

    title = f"{brand} {model} {cap_label} - Raw Test Data"
    description = (
        f"Independent technical performance measurements of the {brand} {model} {cap_label} "
        f"conducted in a controlled test environment in accordance with the standardized Eugen Standard methodology."
    )

    capacity_gib = (r0.get("capacity_gib") or "").strip()
    serial_number = (r0.get("serial_number") or "").strip()
    firmware = (r0.get("firmware") or "").strip()
    operating_system = (r0.get("operating_system") or "").strip()
    fio_version = (r0.get("fio_version") or "").strip()

    sections: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
    for r in page_rows:
        sk = (r.get("section_key") or "").strip()
        st = (r.get("section_title") or "").strip()
        if not sk:
            continue
        sections.setdefault((sk, st), []).append(r)

    section_items = sorted(sections.items(), key=lambda kv: (kv[0][0], kv[0][1]))

    lines: List[str] = []
    lines.append("---")
    lines.append(f'title: "{title}"')
    lines.append(f'description: "{description}"')
    lines.append(
        f'lead: "Independent technical performance measurements of the {brand} {model} {cap_label} conducted in a controlled test environment in accordance with the standardized Eugen Standard [methodology](/en/methodology/)."'
    )
    lines.append(f'brand: "{brand}"')
    lines.append(f'model: "{model}"')
    lines.append(f'brand_slug: "{brand_slug}"')
    lines.append(f'model_slug: "{model_slug}"')
    lines.append(f'capacity_label: "{cap_label}"')
    lines.append(f'capacity_slug: "{cap_slug}"')
    lines.append("---")
    lines.append("")
    lines.append("{{< rawhtml >}}")
    lines.append("")

    lines.append('<table class="meta-table"><tbody>')
    lines.append(f'<tr><th data-meta="ssd_model"></th><td>{html_escape(brand)} {html_escape(model)}</td></tr>')
    if capacity_gib:
        lines.append(f'<tr><th data-meta="capacity_gib"></th><td>{html_escape(capacity_gib)}</td></tr>')
    if serial_number:
        lines.append(f'<tr><th data-meta="serial_number"></th><td>{html_escape(serial_number)}</td></tr>')
    if firmware:
        lines.append(f'<tr><th data-meta="firmware"></th><td>{html_escape(firmware)}</td></tr>')
    if operating_system:
        lines.append(f'<tr><th data-meta="operating_system"></th><td>{html_escape(operating_system)}</td></tr>')
    if fio_version:
        lines.append(f'<tr><th data-meta="fio_version"></th><td>{html_escape(fio_version)}</td></tr>')
    lines.append("</tbody></table>")
    lines.append("")

    for (section_key, _section_title), rows in section_items:
        lines.append(f'<table class="data-table" data-test="{html_escape(section_key)}">')
        lines.append("<thead><tr>")
        lines.append('<th data-col="metric"></th>')
        lines.append('<th data-col="avg_median"></th>')
        lines.append('<th data-col="attempt1"></th><th data-col="attempt2"></th><th data-col="attempt3"></th>')
        lines.append("</tr></thead><tbody>")

        for r in rows:
            metric_key = (r.get("metric_key") or "").strip()
            metric_label = (r.get("metric_label") or "").strip()
            mk = metric_key or slugify(metric_label) or "metric"

            avg = (r.get("avg_median") or "").strip()
            a1 = (r.get("attempt1_value") or "").strip()
            a2 = (r.get("attempt2_value") or "").strip()
            a3 = (r.get("attempt3_value") or "").strip()

            lines.append(
                "<tr>"
                f'<td data-metric="{html_escape(mk)}"></td>'
                f"<td class='kpi'>{html_escape(avg)}</td>"
                f"<td>{html_escape(a1)}</td>"
                f"<td>{html_escape(a2)}</td>"
                f"<td>{html_escape(a3)}</td>"
                "</tr>"
            )

        lines.append("</tbody></table>")
        lines.append("")

    lines.append("{{< /rawhtml >}}")
    lines.append("")
    return "\n".join(lines)


def write_index_md(path: Path, title: str) -> None:
    atomic_write_text(path, f'---\ntitle: "{title}"\n---\n')


def write_category_index_md(path: Path, title: str, title_key: str) -> None:
    atomic_write_text(
        path,
        "\n".join([
            "---",
            f'title: "{title}"',
            f'titleKey: "{title_key}"',
            "---",
            "",
        ])
    )


def write_model_index_md(path: Path, title: str, breadcrumb_title: str) -> None:
    atomic_write_text(
        path,
        "\n".join([
            "---",
            f'title: "{title}"',
            f'breadcrumbTitle: "{breadcrumb_title}"',
            "---",
            "",
        ])
    )


def generate_data_pages(rows: List[Dict[str, str]], lang: str) -> None:
    pages: Dict[Tuple[str, str, str, str, str], List[Dict[str, str]]] = {}

    categories_seen: Dict[str, str] = {}  # category_slug -> fallback_title

    brand_indexes: Dict[Tuple[str, str, str], str] = {}
    # model_indexes теперь хранит (title, breadcrumbTitle)
    model_indexes: Dict[Tuple[str, str, str, str], Tuple[str, str]] = {}

    for r in rows:
        category = (r.get("category") or "").strip()
        brand_slug = (r.get("brand_slug") or "").strip()
        model_slug = (r.get("model_slug") or "").strip()
        capacity_slug = (r.get("capacity_slug") or "").strip()

        if not (category and brand_slug and model_slug and capacity_slug):
            continue

        categories_seen.setdefault(category, humanize_slug(category))

        brand = (r.get("brand") or "").strip()
        model = (r.get("model") or "").strip()

        brand_key = (lang, category, brand_slug)
        brand_indexes.setdefault(brand_key, brand or brand_slug)

        model_key = (lang, category, brand_slug, model_slug)
        # title для листинга = "Samsung T7", breadcrumbTitle = "T7"
        if model_key not in model_indexes:
            model_indexes[model_key] = (f"{brand} {model}".strip(), model)

        key = (lang, category, brand_slug, model_slug, capacity_slug)
        pages.setdefault(key, []).append(r)

    # leaf pages
    for (_, category, brand_slug, model_slug, capacity_slug), page_rows in sorted(pages.items()):
        out_dir = OUT_ROOT / lang / "data" / category / brand_slug / model_slug / capacity_slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "index.md"
        atomic_write_text(out_file, build_md(page_rows))
        print(f"Wrote: {out_file}")

    # category index (_index.md) with titleKey (i18n)
    for category, fallback_title in sorted(categories_seen.items()):
        p = OUT_ROOT / lang / "data" / category / "_index.md"
        title_key = f"category.{category}"
        write_category_index_md(p, fallback_title, title_key)
        print(f"Index: {p}")

    # brand index (без breadcrumbTitle / titleKey)
    for (_, category, brand_slug), title in sorted(brand_indexes.items()):
        p = OUT_ROOT / lang / "data" / category / brand_slug / "_index.md"
        write_index_md(p, title)
        print(f"Index: {p}")

    # model index (с breadcrumbTitle)
    for (_, category, brand_slug, model_slug), (title, bc) in sorted(model_indexes.items()):
        p = OUT_ROOT / lang / "data" / category / brand_slug / model_slug / "_index.md"
        write_model_index_md(p, title, bc)
        print(f"Index: {p}")


def main() -> int:
    rows_all = read_csv(CSV_URL)
    rows_all = [r for r in rows_all if truthy(r.get("published", ""))]

    by_lang = split_rows_by_lang(rows_all, default_lang="en")
    rows_en = by_lang.get("en", [])

    calc_source = rows_en if rows_en else rows_all
    write_calculator_json(build_calculator_json(calc_source))

    write_calculators_section_index_pages()
    write_calculator_pages()

    for lang in TARGET_LANGS:
        rows_lang = by_lang.get(lang, [])
        if not rows_lang and lang != "en" and FALLBACK_TO_EN_IF_MISSING and rows_en:
            print(f"[i] No '{lang}' rows in sheet → generating '{lang}' from EN rows (fallback).")
            rows_lang = rows_en

        if not rows_lang:
            print(f"[i] No rows for language '{lang}' — skipping.")
            continue

        generate_data_pages(rows_lang, lang=lang)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
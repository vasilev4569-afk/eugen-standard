#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import re
from pathlib import Path
from typing import Dict, List
from urllib.request import urlopen

CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSNY87-WIChWcLHd8Ilyx4Smy8hxRC690C4wjhb_yLgfi3uooSD91Pw6TZiK83n269O8AC_3koMsI1-/pub?gid=0&single=true&output=csv"

OUT_ROOT = Path("content")


def norm_header(h: str) -> str:
    h = (h or "").strip()
    h = h.replace(" ", "_")
    h = re.sub(r"[^a-zA-Z0-9_]", "", h)
    return h.lower()


def read_csv(url: str) -> List[Dict[str, str]]:
    raw = urlopen(url).read().decode("utf-8", errors="replace")
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

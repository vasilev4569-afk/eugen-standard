# photo_sync.py
# Eugen Standard — Layer 1 photo pipeline (v1)
# Google Drive (RAW) -> local -> convert to WebP -> Google Drive (Processed) -> Cloudflare R2 (production)
#
# Drive structure (inside "eugen-standard" folder):
# 01_RAW_Photos/external-ssd/<brand>/<model>/<capacity>/unit.jpg
# 02_Processed_WebP/external-ssd/<brand>/<model>/<capacity>/unit.webp
#
# R2 structure:
# external-ssd/<brand>/<model>/<capacity>/unit.webp
# external-ssd/<brand>/<model>/<capacity>/<any_subfolder>/<name>.webp
#
# Drive RAW:
# 01_RAW_Photos/external-ssd/<brand>/<model>/<capacity>/unit.jpg
# 01_RAW_Photos/external-ssd/<brand>/<model>/<capacity>/<any_subfolder>/*.{jpg,jpeg,avif,webp,png}
# All subfolders are mirrored automatically into 02_Processed_WebP and R2.

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ====== CONFIG ======
GDRIVE_ROOT = "gdrive:eugen-standard"

RAW_ROOT = f"{GDRIVE_ROOT}/01_RAW_Photos"
PROC_ROOT = f"{GDRIVE_ROOT}/02_Processed_WebP"

R2_BUCKET = "eugen-assets"
R2_ROOT = f"r2:{R2_BUCKET}"

LOCAL_RAW = Path(".tmp/raw")
LOCAL_PROC = Path(".tmp/processed")

MAX_WIDTH = 1100        # px
WEBP_Q = 85            # 1..100

RAW_NAME = "unit.jpg"   # what you upload to Drive RAW
OUT_NAME = "unit.webp"  # what we generate and publish
KIT_SUBDIR = "01_kit"   # subfolder for review "external appearance" photos
IMAGE_EXTS = {".jpg", ".jpeg", ".avif", ".webp", ".png"}
WATERMARK = "eugen-standard.com"
# Gray semi-transparent (matches site --muted #6b7280)
WATERMARK_COLOR = (107, 114, 128, 140)  # rgba
# ====================


def run(cmd: list[str]) -> None:
    """Run a command and fail fast with a readable output."""
    print("> " + " ".join(cmd))
    subprocess.check_call(cmd)


def ensure_dirs() -> None:
    LOCAL_RAW.mkdir(parents=True, exist_ok=True)
    LOCAL_PROC.mkdir(parents=True, exist_ok=True)


def rel_dir_lower(rel: Path) -> Path:
    """Normalize path to lowercase for consistent output (R2, Drive are case-sensitive)."""
    return Path(*[p.lower() for p in rel.parts])


def _get_watermark_font(size: int = 24) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load font matching site logo (system-ui, Segoe UI, Roboto, Arial)."""
    paths: list[str] = []
    if sys.platform == "win32":
        # Segoe UI (logo font on Windows), Arial fallback
        paths = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arial.ttf"]
    elif sys.platform == "darwin":
        # SF Pro / Helvetica (logo font on macOS)
        paths = ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/SFNSDisplay-Regular.otf", "/System/Library/Fonts/Supplemental/Arial.ttf"]
    else:
        # Roboto, Liberation Sans (Arial-like), DejaVu
        paths = [
            "/usr/share/fonts/truetype/roboto/Roboto-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def add_watermark(img: Image.Image) -> Image.Image:
    """Draw gray semi-transparent watermark in bottom-right corner (matches site logo font)."""
    img_rgba = img.convert("RGBA")
    overlay = Image.new("RGBA", img_rgba.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _get_watermark_font(max(14, min(28, img_rgba.width // 40)))
    bbox = draw.textbbox((0, 0), WATERMARK, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = max(8, img_rgba.width // 80)
    x = max(0, img_rgba.width - tw - pad)
    y = max(0, img_rgba.height - th - pad)
    draw.text((x, y), WATERMARK, fill=WATERMARK_COLOR, font=font)
    img_rgba = Image.alpha_composite(img_rgba, overlay)
    return img_rgba.convert("RGB")


def convert_one(src: Path, dst: Path) -> None:
    """Convert src (jpg/avif/webp/png) -> dst (webp), resize down to MAX_WIDTH if needed."""
    dst.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src) as img:
        # Normalize to RGB
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        elif img.mode == "RGBA":
            # Flatten alpha onto white background (safe for product photos)
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")

        w, h = img.size
        if w > MAX_WIDTH:
            new_h = int(h * (MAX_WIDTH / w))
            img = img.resize((MAX_WIDTH, new_h), Image.LANCZOS)

        img = add_watermark(img)
        img.save(dst, "WEBP", quality=WEBP_Q, method=6)


def main() -> None:
    force = "--force" in sys.argv
    if force:
        print("Force mode: re-converting all images (watermark will be applied)")
    ensure_dirs()

    # 1) Pull RAW from Drive -> local
    # NOTE: --checksum avoids relying on timestamps from cloud providers.
    run(["rclone", "sync", RAW_ROOT, str(LOCAL_RAW), "--checksum"])

    # 2) Convert all RAW images while mirroring folders (auto-includes all model subfolders)
    converted = 0
    scanned = 0
    expected_webp: set[Path] = set()

    for src in LOCAL_RAW.rglob("*"):
        if not src.is_file() or src.suffix.lower() not in IMAGE_EXTS:
            continue
        scanned += 1

        rel_dir = src.parent.relative_to(LOCAL_RAW)
        dst_dir = LOCAL_PROC / rel_dir_lower(rel_dir)
        if src.name.lower() == RAW_NAME:
            dst = dst_dir / OUT_NAME
        else:
            dst = dst_dir / (src.stem + ".webp")

        expected_webp.add(dst.resolve())

        # Convert if output missing OR input newer than output OR --force
        if force or (not dst.exists()) or (src.stat().st_mtime > dst.stat().st_mtime):
            convert_one(src, dst)
            converted += 1

    # 2b) Remove orphaned processed files to keep output mirrored to RAW
    for proc_webp in LOCAL_PROC.rglob("*.webp"):
        if proc_webp.resolve() not in expected_webp:
            proc_webp.unlink()

    # 2c) Build kit manifest from processed 01_kit/*.webp (for Hugo to auto-display all photos)
    kit_manifest: dict[str, list[str]] = {}  # product_path -> sorted list of .webp filenames
    for kit_dir in LOCAL_PROC.rglob(KIT_SUBDIR):
        if not kit_dir.is_dir():
            continue
        rel_dir = kit_dir.parent.relative_to(LOCAL_PROC)
        product_path = str(rel_dir).replace("\\", "/")
        files = sorted(f.name for f in kit_dir.glob("*.webp"))
        if files:
            kit_manifest[product_path] = files

    if kit_manifest:
        manifest_path = Path("data/kit_images.json")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(kit_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Kit manifest: {manifest_path} ({len(kit_manifest)} products)")

    print(f"RAW files found: {scanned}")
    print(f"Converted: {converted}")

    # 3) Push Processed back to Drive
    run(["rclone", "sync", str(LOCAL_PROC), PROC_ROOT, "--checksum"])

    # 4) Upload Processed to R2 bucket root (keeps same paths)
    run(["rclone", "sync", str(LOCAL_PROC), R2_ROOT, "--checksum"])

    print("DONE")


if __name__ == "__main__":
    main()
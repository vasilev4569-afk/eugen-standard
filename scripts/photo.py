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

import subprocess
from pathlib import Path

from PIL import Image

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
# ====================


def run(cmd: list[str]) -> None:
    """Run a command and fail fast with a readable output."""
    print("> " + " ".join(cmd))
    subprocess.check_call(cmd)


def ensure_dirs() -> None:
    LOCAL_RAW.mkdir(parents=True, exist_ok=True)
    LOCAL_PROC.mkdir(parents=True, exist_ok=True)


def convert_one(src: Path, dst: Path) -> None:
    """Convert src (jpg) -> dst (webp), resize down to MAX_WIDTH if needed."""
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

        img.save(dst, "WEBP", quality=WEBP_Q, method=6)


def main() -> None:
    ensure_dirs()

    # 1) Pull RAW from Drive -> local
    # NOTE: --checksum avoids relying on timestamps from cloud providers.
    run(["rclone", "sync", RAW_ROOT, str(LOCAL_RAW), "--checksum"])

    # 2) Convert unit.jpg -> unit.webp while mirroring folders
    converted = 0
    scanned = 0

    for src in LOCAL_RAW.rglob(RAW_NAME):
        scanned += 1

        # Mirror directory structure under LOCAL_PROC
        # e.g. external-ssd/samsung/t7/1tb/unit.jpg
        rel_dir = src.parent.relative_to(LOCAL_RAW)
        dst = LOCAL_PROC / rel_dir / OUT_NAME

        # Convert if output missing OR input newer than output
        if (not dst.exists()) or (src.stat().st_mtime > dst.stat().st_mtime):
            convert_one(src, dst)
            converted += 1

    print(f"RAW files found: {scanned}")
    print(f"Converted: {converted}")

    # 3) Push Processed back to Drive
    run(["rclone", "sync", str(LOCAL_PROC), PROC_ROOT, "--checksum"])

    # 4) Upload Processed to R2 bucket root (keeps same paths)
    run(["rclone", "sync", str(LOCAL_PROC), R2_ROOT, "--checksum"])

    print("DONE")


if __name__ == "__main__":
    main()
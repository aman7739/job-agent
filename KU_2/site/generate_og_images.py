"""Generate a crisp 1200x630 OpenGraph / Twitter Card image using Pillow."""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "site" / "static" / "images" / "og-image.png"

def create_og_image() -> Path:
    width = 1200
    height = 630

    # Create base canvas with dark slate background
    img = Image.new("RGB", (width, height), color=(15, 23, 42))  # #0f172a
    draw = ImageDraw.Draw(img)

    # Draw decorative border
    draw.rectangle([20, 20, width - 20, height - 20], outline=(51, 65, 85), width=2)
    # Accent top border
    draw.rectangle([20, 20, width - 20, 28], fill=(37, 99, 235))

    # Inner container card
    draw.rounded_rectangle([60, 60, width - 60, height - 60], radius=16, fill=(30, 41, 59), outline=(51, 65, 85), width=2)

    # Try to load standard fonts or fall back to default
    try:
        font_badge = ImageFont.truetype("arialbd.ttf", 18)
        font_title = ImageFont.truetype("arialbd.ttf", 52)
        font_subtitle = ImageFont.truetype("arial.ttf", 26)
        font_chips = ImageFont.truetype("arialbd.ttf", 18)
        font_meta = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        font_badge = ImageFont.load_default()
        font_title = ImageFont.load_default()
        font_subtitle = ImageFont.load_default()
        font_chips = ImageFont.load_default()
        font_meta = ImageFont.load_default()

    # Draw badge
    badge_text = "MILESTONE 2 VERIFIED  •  AUTONOMOUS PRODUCTION AGENT"
    badge_box = [90, 100, 640, 136]
    draw.rounded_rectangle(badge_box, radius=6, fill=(16, 185, 129, 40), outline=(16, 185, 129), width=1)
    draw.text((105, 107), badge_text, fill=(52, 211, 153), font=font_badge)

    # Main Headline
    draw.text((90, 160), "Job Digest Agent", fill=(248, 250, 252), font=font_title)

    # Subtitle
    subtitle = "Autonomous Fresher & Internship Discovery for Batch 2027"
    draw.text((90, 235), subtitle, fill=(148, 163, 184), font=font_subtitle)

    # Secondary text
    desc = "Daily ingestion across 8 ATS APIs with 10-point scoring, twice-daily delivery (8 AM & 7 PM),\nand immediate alerts for urgent opportunities closing in <= 4 hours."
    draw.text((90, 285), desc, fill=(203, 213, 225), font=font_meta, spacing=8)

    # Feature Chips
    chips = [
        "8 Permitted ATS Sources",
        "10-Point Scoring Matrix",
        "Twice-Daily Cadence (8 AM & 7 PM IST)",
        "Urgent <= 4h Alerts",
        "Zero Scraping Compliance",
        "Private Mobile Dashboard",
    ]

    start_x = 90
    start_y = 380
    chip_x = start_x
    chip_y = start_y

    for i, chip in enumerate(chips):
        chip_w = len(chip) * 11 + 24
        if chip_x + chip_w > width - 100:
            chip_x = start_x
            chip_y += 50

        draw.rounded_rectangle([chip_x, chip_y, chip_x + chip_w, chip_y + 36], radius=6, fill=(15, 23, 42), outline=(59, 130, 246), width=1)
        draw.text((chip_x + 12, chip_y + 8), chip, fill=(96, 165, 250), font=font_chips)
        chip_x += chip_w + 16

    # Footer note
    draw.line([90, height - 120, width - 90, height - 120], fill=(51, 65, 85), width=1)
    footer_text = "Single-User Private Architecture  •  Telegram Bot & SMTP Delivery  •  Strict Anti-Scraping Charter"
    draw.text((90, height - 100), footer_text, fill=(100, 116, 139), font=font_meta)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUTPUT_PATH, "PNG")
    print(f"[OK] Generated OpenGraph card: {OUTPUT_PATH} ({width}x{height})")
    return OUTPUT_PATH

if __name__ == "__main__":
    create_og_image()

#!/usr/bin/env python3
"""
One-time script to populate the public corpus with common chips.

Downloads datasheets, runs ingestion, and stores pre-canonicalized data
for instant results on subsequent uploads.

Usage:
    python scripts/populate_corpus.py                  # All 20 chips
    python scripts/populate_corpus.py --chip ATmega328P  # Single chip
    python scripts/populate_corpus.py --dry-run        # Preview only
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.akili.corpus import COMMON_CHIPS
from src.akili.corpus.loader import compute_pdf_hash, serialize_canonical_for_corpus
from src.akili.ingest.pipeline import ingest_document
from src.akili.store import create_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Datasheet URLs for common chips
# Note: Some may require manual download due to registration requirements
DATASHEET_URLS = {
    "ATmega328P": "https://ww1.microchip.com/downloads/en/DeviceDoc/ATmega328P-Complete-Datasheet-40002061B.pdf",
    "ATmega2560": "https://ww1.microchip.com/downloads/en/devicedoc/atmel-2549-8-bit-avr-microcontroller-atmega640-1280-1281-2560-2561_datasheet.pdf",
    "ESP32": "https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf",
    "ESP32-S3": "https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf",
    "ESP8266": "https://www.espressif.com/sites/default/files/documentation/0a-esp8266ex_datasheet_en.pdf",
    "STM32F103": "https://www.st.com/resource/en/datasheet/stm32f103c8.pdf",
    "STM32F411": "https://www.st.com/resource/en/datasheet/stm32f411ce.pdf",
    "RP2040": "https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf",
    "NE555": "https://www.ti.com/lit/ds/symlink/ne555.pdf",
    "LM7805": "https://www.ti.com/lit/ds/symlink/lm7805.pdf",
    "LM7812": "https://www.ti.com/lit/ds/symlink/lm7812.pdf",
    "LM317": "https://www.ti.com/lit/ds/symlink/lm317.pdf",
    "LM358": "https://www.ti.com/lit/ds/symlink/lm358.pdf",
    "LM386": "https://www.ti.com/lit/ds/symlink/lm386.pdf",
    "L293D": "https://www.ti.com/lit/ds/symlink/l293d.pdf",
    "ULN2003": "https://www.ti.com/lit/ds/symlink/uln2003a.pdf",
    "74HC595": "https://www.ti.com/lit/ds/symlink/sn74hc595.pdf",
    "MAX7219": "https://datasheets.maximintegrated.com/en/ds/MAX7219-MAX7221.pdf",
    "ADS1115": "https://www.ti.com/lit/ds/symlink/ads1115.pdf",
    "BME280": "https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme280-ds002.pdf",
}


async def download_datasheet(chip: str, temp_dir: Path) -> Path | None:
    """Download datasheet PDF for a chip."""
    url = DATASHEET_URLS.get(chip)
    if not url:
        logger.warning(f"No datasheet URL for {chip}")
        return None

    import aiohttp

    pdf_path = temp_dir / f"{chip}.pdf"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to download {chip}: HTTP {resp.status}")
                    return None
                content = await resp.read()
                pdf_path.write_bytes(content)
                logger.info(f"Downloaded {chip}: {len(content)} bytes")
                return pdf_path
    except Exception as e:
        logger.error(f"Download error for {chip}: {e}")
        return None


async def process_chip(chip: str, store: object, dry_run: bool = False) -> bool:
    """Process a single chip: download, ingest, store in corpus."""
    logger.info(f"Processing {chip}...")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Download datasheet
        pdf_path = await download_datasheet(chip, temp_path)
        if not pdf_path:
            return False

        # Compute hash
        content_hash = compute_pdf_hash(pdf_path)
        logger.info(f"  Hash: {content_hash[:16]}...")

        if dry_run:
            logger.info(f"  [DRY RUN] Would ingest and store {chip}")
            return True

        # Check if already in corpus
        existing = store.get_corpus_entry(content_hash)
        if existing:
            logger.info(f"  Already in corpus, skipping")
            return True

        # Run ingestion
        try:
            doc_id, canonical_objects, pages_ok, pages_failed = ingest_document(
                pdf_path=pdf_path,
                doc_id=f"corpus_{chip.lower().replace('-', '_')}",
                store=None,  # Don't store in main tables
            )

            # Separate canonical objects by type
            from akili.canonical import Bijection, ConditionalUnit, Grid, Range, Unit

            units = [o for o in canonical_objects if isinstance(o, Unit)]
            bijections = [o for o in canonical_objects if isinstance(o, Bijection)]
            grids = [o for o in canonical_objects if isinstance(o, Grid)]
            ranges = [o for o in canonical_objects if isinstance(o, Range)]
            conditional_units = [o for o in canonical_objects if isinstance(o, ConditionalUnit)]

            logger.info(
                f"  Extracted: {len(units)} units, {len(bijections)} bijections, "
                f"{len(grids)} grids, {len(ranges)} ranges"
            )

            # Serialize for corpus
            canonical_data = serialize_canonical_for_corpus(
                units, bijections, grids, ranges, conditional_units
            )

            # Store in corpus
            store.store_corpus_entry(
                content_hash=content_hash,
                mpn=chip,
                chip_name=chip,
                canonical_data=canonical_data,
                datasheet_url=DATASHEET_URLS.get(chip),
            )

            logger.info(f"  Stored in corpus successfully")
            return True

        except Exception as e:
            logger.error(f"  Ingestion error: {e}")
            return False


async def main():
    parser = argparse.ArgumentParser(description="Populate public corpus with common chips")
    parser.add_argument("--chip", type=str, help="Process single chip only")
    parser.add_argument("--dry-run", action="store_true", help="Preview without storing")
    parser.add_argument("--db-url", type=str, help="Database URL (default: from DATABASE_URL env)")
    args = parser.parse_args()

    # Initialize store
    db_url = args.db_url or os.environ.get("DATABASE_URL")
    if not db_url and not args.dry_run:
        logger.error("DATABASE_URL not set. Use --db-url or set environment variable.")
        sys.exit(1)

    store = create_store(db_url=db_url) if not args.dry_run else None

    # Determine chips to process
    chips = [args.chip] if args.chip else COMMON_CHIPS
    if args.chip and args.chip not in COMMON_CHIPS:
        logger.warning(f"{args.chip} not in COMMON_CHIPS list, proceeding anyway")

    logger.info(f"Processing {len(chips)} chips...")
    logger.info("=" * 60)

    success_count = 0
    for chip in chips:
        if await process_chip(chip, store, args.dry_run):
            success_count += 1
        # Rate limiting between chips
        await asyncio.sleep(2)

    logger.info("=" * 60)
    logger.info(f"Complete: {success_count}/{len(chips)} chips processed successfully")

    if success_count < len(chips):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

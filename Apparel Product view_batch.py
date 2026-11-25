#!/usr/bin/env python3
"""
ghost_mannequin_batch.py

A generalised batch pipeline for turning raw garment images into clean,
catalogue-ready "ghost mannequin" product images using a generative model,
with a quality-control pass before anything is approved.

This is a reusable template. The two integration points you must fill in
for your own setup are marked clearly:

    1. generate_image()  -> wire to your model (ComfyUI / Replicate / Gemini / etc.)
    2. passes_quality_check() -> wire to your fidelity / drift check

Design goals
------------
- No credentials in the file. All secrets come from environment variables.
- One bad image never kills the batch. Failures are caught, logged, and
  moved aside so the run continues.
- Clear separation between orchestration (stable) and the model call (swappable).

Usage
-----
    export MODEL_API_KEY="your-key-here"        # never hardcode this
    python ghost_mannequin_batch.py --input ./input --output ./output

"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Image file types the pipeline will pick up from the input folder.
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

# Secrets and environment-specific settings are read from the environment,
# never written into the file. Set these before running (see Usage above).
MODEL_API_KEY = os.environ.get("MODEL_API_KEY")          # required at run time
MODEL_ENDPOINT = os.environ.get("MODEL_ENDPOINT", "")     # optional, if you use one
MODEL_NAME = os.environ.get("MODEL_NAME", "")             # optional, your model id

# How many times to retry a single image before giving up on it.
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "2"))

# Seconds to wait between retries (simple backoff).
RETRY_BACKOFF_SECONDS = float(os.environ.get("RETRY_BACKOFF_SECONDS", "3"))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ghost_mannequin")


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

@dataclass
class BatchResult:
    """Simple tally of what happened across the run."""
    approved: int = 0
    rejected: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        return self.approved + self.rejected + self.failed


# ---------------------------------------------------------------------------
# Integration point 1 — the model call
# ---------------------------------------------------------------------------

def generate_image(source_path: Path, dest_path: Path) -> None:
    """
    Generate a ghost-mannequin image from `source_path` and write it to
    `dest_path`.

    >>> WIRE THIS TO YOUR OWN MODEL. <<<

    Depending on your setup this would:
      - submit the source image to a ComfyUI workflow via its local API, or
      - call a hosted model through its official Python client, or
      - hit your own inference endpoint.

    Use MODEL_API_KEY / MODEL_ENDPOINT / MODEL_NAME from the environment above
    rather than hardcoding anything. Raise an exception on failure so the
    retry/skip logic below can handle it.

    This template intentionally does not ship a specific provider's call,
    so it stays model-agnostic and safe to publish.
    """
    raise NotImplementedError(
        "generate_image() is a stub. Connect it to your ComfyUI workflow "
        "or model client. It should read the source image, run generation, "
        "and save the result to dest_path."
    )


# ---------------------------------------------------------------------------
# Integration point 2 — the quality / fidelity check
# ---------------------------------------------------------------------------

def passes_quality_check(source_path: Path, generated_path: Path) -> bool:
    """
    Decide whether a generated image is good enough to approve.

    >>> WIRE THIS TO YOUR OWN CHECK. <<<

    A generative model occasionally gets product detail wrong — a collar, a
    print, a colour. Because a catalogue image is a promise to the customer,
    nothing should be approved until it has passed a fidelity check.

    This could be:
      - an automated comparison between source and output,
      - a model-based evaluation against a set of rules, or
      - a flag that routes borderline images to a human review queue.

    Return True to approve, False to reject. The default below approves
    everything so the template runs end to end; replace it with your logic.
    """
    log.debug("Quality check stub approving %s", generated_path.name)
    return True


# ---------------------------------------------------------------------------
# Orchestration (the stable part — usually no need to change this)
# ---------------------------------------------------------------------------

def collect_inputs(input_dir: Path) -> list[Path]:
    """Return a sorted list of supported image files in the input folder."""
    files = [
        p for p in sorted(input_dir.iterdir())
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return files


def process_one(source: Path, output_dir: Path, rejected_dir: Path) -> str:
    """
    Run a single image through generation + quality check.

    Returns one of: "approved", "rejected", "failed".
    """
    dest = output_dir / f"{source.stem}_ghost{source.suffix}"

    # Try generation with a few retries, since model calls can be flaky.
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            generate_image(source, dest)
            break
        except NotImplementedError:
            # Stub not yet wired — re-raise so the user sees a clear message.
            raise
        except Exception as exc:  # noqa: BLE001 - we want to catch anything here
            log.warning(
                "Generation failed for %s (attempt %d/%d): %s",
                source.name, attempt, MAX_RETRIES, exc,
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS)
            else:
                log.error("Giving up on %s after %d attempts.", source.name, MAX_RETRIES)
                return "failed"

    # Quality / fidelity gate.
    try:
        if passes_quality_check(source, dest):
            log.info("Approved: %s", dest.name)
            return "approved"
        else:
            # Move the rejected output aside for review rather than deleting it.
            rejected_path = rejected_dir / dest.name
            if dest.exists():
                dest.replace(rejected_path)
            log.info("Rejected (failed quality check): %s", source.name)
            return "rejected"
    except Exception as exc:  # noqa: BLE001
        log.error("Quality check errored for %s: %s", source.name, exc)
        return "failed"


def run_batch(input_dir: Path, output_dir: Path) -> BatchResult:
    """Process every supported image in the input folder."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rejected_dir = output_dir / "_rejected"
    rejected_dir.mkdir(parents=True, exist_ok=True)

    inputs = collect_inputs(input_dir)
    if not inputs:
        log.warning("No supported images found in %s", input_dir)
        return BatchResult()

    log.info("Found %d image(s) to process.", len(inputs))
    result = BatchResult()

    for i, source in enumerate(inputs, start=1):
        log.info("[%d/%d] Processing %s", i, len(inputs), source.name)
        outcome = process_one(source, output_dir, rejected_dir)
        if outcome == "approved":
            result.approved += 1
        elif outcome == "rejected":
            result.rejected += 1
        else:
            result.failed += 1

    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch-generate ghost-mannequin product images with a QC pass."
    )
    parser.add_argument("--input", required=True, type=Path, help="Folder of source images.")
    parser.add_argument("--output", required=True, type=Path, help="Folder for approved output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.input.is_dir():
        log.error("Input folder does not exist: %s", args.input)
        return 1

    if MODEL_API_KEY is None:
        # Not fatal for a dry run with the stub, but warn clearly.
        log.warning(
            "MODEL_API_KEY is not set. Set it as an environment variable before "
            "wiring up generate_image() to a real model."
        )

    start = time.time()
    result = run_batch(args.input, args.output)
    elapsed = time.time() - start

    log.info("-" * 48)
    log.info("Done in %.1fs  |  %d total", elapsed, result.total)
    log.info("Approved: %d   Rejected: %d   Failed: %d",
             result.approved, result.rejected, result.failed)

    # Non-zero exit if nothing succeeded, so this plays nicely in automation.
    return 0 if result.approved > 0 or result.total == 0 else 2


if __name__ == "__main__":
    sys.exit(main())

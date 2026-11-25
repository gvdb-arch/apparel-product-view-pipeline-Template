# Apparel Product View Pipeline

A terminal-based Python pipeline that calls cloud-hosted AI models on
Replicate to generate apparel product-view images in batches — with a
quality-check layer that catches fidelity errors before an image is approved.

> One line: *I built a terminal-run Python pipeline that sends garment images
> to cloud-hosted models on Replicate — primarily Nano Banana Pro (Google's
> Gemini 3 Pro image model) — and returns clean, catalogue-ready product views
> at volume, plus the check that catches AI errors before they go live.*

---

## The problem

Producing apparel product-view imagery the traditional way — physical shoots,
styling, and manual post-production — is slow and expensive. At catalogue
scale, thousands of garments a month, it becomes a real bottleneck on both
cost and turnaround.

## The approach

A headless script runs from the terminal, takes a folder of garment images,
and processes them in batches through cloud-hosted models, returning a clean
product view for each.

- **Generation:** cloud-hosted models on **Replicate** (multi-model), primarily
  **Nano Banana Pro** — Google's Gemini 3 Pro image model (`google/nano-banana-pro`)
- **Orchestration:** a terminal-run Python script that batches the inputs and
  handles retries, logging, and output routing — no GUI, nothing to click
- **Config & secrets:** API token and settings read from environment variables
  (a local `.env`), never hardcoded
- **Output:** approved images written to an output folder; anything that fails
  the quality check is set aside for review, not deleted

Running in the cloud rather than on a local GUI was a deliberate choice — it
scales with the batch instead of being capped by one machine.

## Architecture

```
[input folder of garment images]
          |
          v
[terminal Python script]  -->  [Replicate API]  -->  [Nano Banana Pro / other models]
          |                                               |
          v                                               v
[quality / fidelity check]  <---------------------  [generated product view]
          |
   +------+-------+
   v              v
[approved]    [_rejected -- held for review]
```

## Quality control

Generative models occasionally get product detail wrong — a collar, a print,
a colour. Because a catalogue image is a promise to the customer, nothing is
approved until it has passed a fidelity check. The pipeline routes anything
that fails into a review folder rather than letting it through, so weak output
never reaches the live catalogue.

*(This check is the part I'm proudest of — it's what makes the speed usable
rather than risky.)*

## How it grew

This started as a solo test — a single terminal script to see whether
cloud-hosted models could produce usable apparel product views at volume.
It worked, and it grew from there into team tooling I led:

- **Terminal batch pipeline** — the core: a headless, cloud-backed script that
  processes garments in bulk with a quality gate.
- **UXP Photoshop plugin** — brought the pipeline into Photoshop so the team
  could run it inside the software they already work in, rather than at the
  command line.
- **Capture One integration** — connected the pipeline into the capture and
  post workflow, so generation and checks sit where the images already live.

The point of the plugin and integration was adoption: moving from a prototype
one person ran, to tooling the team uses in their day-to-day software.

## Results

> Fill these in with your own real figures. Leave a line out rather than
> estimate it — one true number is worth more than five guessed ones.

- **Throughput:** `[e.g. X images per batch / per run]`
- **Turnaround:** `[traditional process vs pipeline]`
- **Runs on:** `[your environment]`
- **Before / after:**

| Input | Generated product view |
|-------|------------------------|
| ![input](examples/input_01.jpg) | ![output](examples/output_01.jpg) |

*(Use non-proprietary sample garments for the public examples.)*

## Running it

```bash
# Set your Replicate token as an environment variable -- never hardcode it
export MODEL_API_KEY="your-replicate-token"

python apparel_product_view.py --input ./input --output ./output
```

*(Match the filename to your script — rename the script to
`apparel_product_view.py`, or adjust the command to your actual filename.)*

## Requirements

See `requirements.txt`. In short: the Replicate client plus a couple of
libraries to download and handle the returned images. Secrets load from a
local `.env` that is never committed (see `.gitignore`).

## Notes

Built as a reusable technique for automating high-volume apparel imagery.
Sample assets here are non-commercial and for demonstration only.

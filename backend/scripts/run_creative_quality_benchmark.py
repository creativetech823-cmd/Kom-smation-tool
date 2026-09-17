"""CLI entry point for the Creative Quality Benchmark's live runner.

Runs a fixed, small controlled sample of real, full pipeline generations
(Herbal Masala/Immune Care/Beard Oil, matching Phase 3C's Part 19 sample)
through the UNMODIFIED production pipeline (script_service.generate_script),
scheduled with bounded concurrency via creative_benchmark_runner.

Usage:
    python scripts/run_creative_quality_benchmark.py
    python scripts/run_creative_quality_benchmark.py --concurrency 4

Concurrency defaults to settings.creative_benchmark_concurrency (env
CREATIVE_BENCHMARK_CONCURRENCY, default 3) and can be overridden with
--concurrency for one run without changing the env/default.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

from app.models.product import StructuredProduct  # noqa: E402
from app.services import creative_benchmark_runner as runner  # noqa: E402

PRODUCTS = {
    "Herbal Masala": StructuredProduct(
        product_name="Aayush Herbal Masala",
        target_audience="adult gutka and pan masala chewers, 20s-40s, trying to switch away from tobacco",
        ingredients=["Mulethi", "Amla"], usp="a 0% tobacco, 0% supari herbal chew",
        key_benefits=["same chewing ritual and taste"],
    ),
    "Immune Care": StructuredProduct(
        product_name="AayushWellness Immune Care Tablets",
        target_audience="mothers of school-age children who feel overwhelmed juggling elaborate immunity routines",
        ingredients=["Amla", "Giloy", "Tulsi", "Zinc"], usp="a simple daily chewable immunity tablet",
        key_benefits=["simple daily routine", "kids take it without a fight"],
    ),
    "Beard Oil": StructuredProduct(
        product_name="AayushWellness Beard Grow Oil",
        target_audience="college-going young men, 18-22, self-conscious about patchy beard growth",
        ingredients=["Castor Oil", "Rosemary Oil", "Biotin"], usp="a daily beard oil for patchy growth",
        key_benefits=["fills in patchy areas with regular use"],
    ),
}
CATEGORY = {"Herbal Masala": "herbal_health", "Immune Care": "nutraceuticals", "Beard Oil": "personal_care"}

CASES = [
    ("Herbal Masala", "Doctor ki Advice, Healthy Life",
     "A regular gutka/pan-masala chewer visits a doctor for an unrelated checkup and gets unexpected advice about switching away from tobacco.",
     "surprised, reflective", "unexpected authority endorsement"),
    ("Herbal Masala", "Meri Choice, Meri Health",
     "A person quietly decides on their own, without anyone pushing them, to switch their daily chew.",
     "quiet resolve", "self-directed change"),
    ("Herbal Masala", "Dost Boli: Try Toh Kar!",
     "A friend notices the habit and casually offers an alternative during a normal hangout.",
     "casual, warm", "peer influence"),
    ("Herbal Masala", "Party Mein Nayi Baat",
     "At a celebration where pan masala is passed around, someone has already switched and it becomes a talking point.",
     "social, proud", "social contrast"),
    ("Immune Care", "Nani Maa Ka Nuskha",
     "A grandmother's simple daily habit inspires a busy mother trying to keep her kids healthy.",
     "warm, reassured", "generational wisdom"),
    ("Immune Care", "Morning Rush Hour",
     "A mother juggling the school-morning chaos finds one thing that doesn't add friction.",
     "relieved", "simplicity"),
    ("Beard Oil", "Job Interview Jitters",
     "A young man prepping for an interview notices his patchy beard and does something about it fast.",
     "anxious, then confident", "self-presentation"),
    ("Beard Oil", "Mirror, Mirror...",
     "A college student's daily mirror check becomes a quiet before/after over weeks.",
     "self-conscious, then proud", "visible transformation"),
]


def build_cases() -> list[runner.BenchmarkCase]:
    return [
        runner.BenchmarkCase(
            product_label=label, situation_title=title, situation_description=desc,
            situation_emotion=emotion, situation_marketing_angle=angle,
            structured_product=PRODUCTS[label], product_category=CATEGORY[label],
        )
        for label, title, desc, emotion, angle in CASES
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", type=int, default=None, help="Override settings.creative_benchmark_concurrency for this run")
    args = parser.parse_args()

    cases = build_cases()
    result = runner.run_benchmark_cases(cases, concurrency=args.concurrency)

    print(f"\n{'=' * 70}")
    print(f"[Benchmark] DONE — {len(result.succeeded)}/{result.total_cases} succeeded, "
          f"{len(result.failed)} failed | concurrency={result.concurrency} | "
          f"elapsed={result.elapsed_s / 60:.1f}m | total_cost=${result.total_cost_usd:.4f}")
    print(f"{'=' * 70}")
    for r in result.results:
        status_tag = r.status.upper()
        print(f"[{status_tag:7s}] {r.case.product_label:14s} | {r.case.situation_title:35s} | "
              f"{r.duration_s:6.1f}s | ${r.cost_usd:.4f} | retries={r.retry_count} rewrites={r.rewrite_count}")
        if r.error:
            print(f"          error: {r.error}")
        if r.script is not None:
            print(f"          hook: {r.script.hook.text}")


if __name__ == "__main__":
    main()

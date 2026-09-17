"""Creative Quality Benchmark runner — Phase 3C runtime optimization.

Runs independent benchmark CASES concurrently, bounded by
settings.creative_benchmark_concurrency (env CREATIVE_BENCHMARK_CONCURRENCY,
default 3). This module changes ONLY how benchmark cases are scheduled —
nothing about the production creative pipeline is touched. Each case is
still exactly one, unmodified script_service.generate_script() call,
executing its existing fixed sequence (insight -> territory -> architecture
-> premise -> hook -> beat outline -> final script -> quality gate ->
architecture/Creative Director gate -> bounded re-check) inside its own
worker thread. Concurrency here is ACROSS independent cases only — nothing
inside a single case's call chain is parallelized or reordered.

Usage/cost/retry/rewrite data is captured per case via a thread-scoped
logging handler rather than by touching script_service.py's own
contextvar-based tracking: those contextvars are already per-thread by
nature (safe for concurrent cases), but _generate_full_script's own
stop_usage_tracking() call (in its `finally` block) clears them before an
outer caller could read get_usage_summary() after generate_script() returns
— so reading the already-emitted "pipeline_cost_summary" log line (scoped to
this case's own worker thread only, via record.thread) is the only
non-invasive way to recover this data per case without changing any
production code.
"""

import ast
import concurrent.futures
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from app.config import settings
from app.models.product import ContentType, GeneratedScript, ScriptGenerationInput, ScriptLanguage, StorySituation, StructuredProduct
from app.services import script_service

logger = logging.getLogger("creative_benchmark_runner")

# Loggers that already emit everything this runner needs (cost summary,
# retry attempts, rewrite triggers) — see script_service.py and
# openrouter_utils.py. Reading these, scoped to one thread, avoids adding
# any new instrumentation to the production pipeline itself.
_CAPTURED_LOGGER_NAMES = ("script_service", "openrouter_utils", "architecture_validation_service")
_COST_SUMMARY_RE = re.compile(r"^pipeline_cost_summary (\{.*\})$")
_RETRY_RE = re.compile(r"attempt=\d+/\d+ failed transient=True")
_REWRITE_TRIGGER_RE = re.compile(r"attempting one (?:rewrite pass|targeted rewrite)")


class _ScopedLogCapture(logging.Handler):
    """Captures only the records emitted by ONE specific thread. Multiple
    cases running concurrently share the same underlying logger objects (a
    log record is delivered to every handler attached at emit time,
    regardless of which thread emitted it), so per-record thread filtering —
    not just per-handler attach/detach scoping — is what actually keeps
    concurrent cases' data from mixing."""

    def __init__(self, thread_id: int):
        super().__init__()
        self.thread_id = thread_id
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.thread == self.thread_id:
            self.records.append(record)


@dataclass
class BenchmarkCase:
    product_label: str
    situation_title: str
    situation_description: str
    situation_emotion: str
    situation_marketing_angle: str
    structured_product: StructuredProduct
    product_category: str
    script_language: ScriptLanguage = ScriptLanguage.hinglish
    platform: str = "instagram_reel"

    def to_payload(self) -> ScriptGenerationInput:
        situation = StorySituation(
            id="benchmark", title=self.situation_title, description=self.situation_description,
            emotion=self.situation_emotion, persona=self.structured_product.target_audience,
            marketing_angle=self.situation_marketing_angle, category="c", difficulty="medium",
            estimated_length="30s", virality_score=5.0, recommended_angles=[],
        )
        return ScriptGenerationInput(
            structured_product=self.structured_product, selected_situation=situation,
            product_category=self.product_category, platform=self.platform,
            script_language=self.script_language, content_type=ContentType.video,
        )


@dataclass
class CaseResult:
    case: BenchmarkCase
    status: str  # "success" | "failure" | "timeout"
    duration_s: float
    cost_usd: float
    usage_summary: dict = field(default_factory=dict)
    retry_count: int = 0
    rewrite_count: int = 0
    script: GeneratedScript | None = None
    error: str | None = None
    started_at: float = 0.0
    completed_at: float = 0.0


@dataclass
class BenchmarkRunResult:
    results: list[CaseResult]
    total_cases: int
    concurrency: int
    started_at: float
    completed_at: float
    elapsed_s: float

    @property
    def succeeded(self) -> list[CaseResult]:
        return [r for r in self.results if r.status == "success"]

    @property
    def failed(self) -> list[CaseResult]:
        return [r for r in self.results if r.status != "success"]

    @property
    def total_cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.results)


def _run_one_case(case: BenchmarkCase) -> CaseResult:
    """Runs exactly ONE unmodified generate_script() call end to end, on
    this one worker thread, in the pipeline's existing fixed order. Never
    lets an exception escape (a failed case must not sink the whole run) —
    always returns a CaseResult, status="failure" on any exception."""
    thread_id = threading.get_ident()
    handlers = [_ScopedLogCapture(thread_id) for _ in _CAPTURED_LOGGER_NAMES]
    loggers = [logging.getLogger(name) for name in _CAPTURED_LOGGER_NAMES]
    for lg, h in zip(loggers, handlers):
        lg.addHandler(h)

    started_at = time.time()
    status, error, script = "success", None, None
    try:
        script = script_service.generate_script(case.to_payload())
    except Exception as e:  # noqa: BLE001 — deliberately broad: one bad case must not sink the run
        status, error = "failure", f"{type(e).__name__}: {e}"
        logger.warning("Benchmark case %r failed: %s", case.situation_title, error)
    finally:
        for lg, h in zip(loggers, handlers):
            lg.removeHandler(h)
    completed_at = time.time()

    all_records = [r for h in handlers for r in h.records]
    usage_summary: dict = {}
    for r in all_records:
        m = _COST_SUMMARY_RE.match(r.getMessage())
        if m:
            try:
                usage_summary = ast.literal_eval(m.group(1))
            except (ValueError, SyntaxError):
                usage_summary = {}
    retry_count = sum(1 for r in all_records if _RETRY_RE.search(r.getMessage()))
    rewrite_count = sum(1 for r in all_records if _REWRITE_TRIGGER_RE.search(r.getMessage()))
    cost_usd = float(usage_summary.get("estimated_total_cost_usd") or 0.0)

    return CaseResult(
        case=case, status=status, duration_s=completed_at - started_at, cost_usd=cost_usd,
        usage_summary=usage_summary, retry_count=retry_count, rewrite_count=rewrite_count,
        script=script, error=error, started_at=started_at, completed_at=completed_at,
    )


def run_benchmark_cases(
    cases: list[BenchmarkCase],
    concurrency: int | None = None,
    timeout_s: float | None = None,
    on_progress: Callable[[BenchmarkRunResult, CaseResult], None] | None = None,
) -> BenchmarkRunResult:
    """Runs `cases` with bounded concurrency (default
    settings.creative_benchmark_concurrency). Independent cases run in
    parallel worker threads; the pipeline INSIDE each case is untouched and
    fully sequential — see _run_one_case. One case's failure never cancels
    the others (each future is independent and _run_one_case itself never
    raises).

    timeout_s, if given, is a best-effort REPORTING timeout, not a real
    cancellation: Python cannot forcibly kill a running thread mid-call, so
    a case that exceeds it is reported as status="timeout" and stops being
    waited on, but its underlying thread keeps running detached until the
    real generate_script() call itself returns — a known limitation of
    thread-based (not process-based) concurrency, documented here rather
    than silently pretended away."""
    n = concurrency or settings.creative_benchmark_concurrency
    started_at = time.time()
    results: list[CaseResult] = []
    total = len(cases)

    logger.info("[Benchmark] %d cases | concurrency=%d | started", total, n)
    # The cost-summary/retry/rewrite lines this runner reads are logged at
    # INFO. If the process's logging config hasn't already lowered these
    # loggers' effective level to INFO (e.g. no logging.basicConfig call),
    # logger.info(...) becomes a silent no-op at the SOURCE — the handler
    # never even sees a record to filter by thread. Set once for the whole
    # batch (not per case) and restore after every case has finished, so
    # concurrent cases sharing these loggers never race on the level.
    captured_loggers = [logging.getLogger(name) for name in _CAPTURED_LOGGER_NAMES]
    original_levels = [lg.level for lg in captured_loggers]
    for lg in captured_loggers:
        if not lg.isEnabledFor(logging.INFO):
            lg.setLevel(logging.INFO)

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=n)
    try:
        future_to_case = {executor.submit(_run_one_case, c): c for c in cases}
        pending = set(future_to_case)
        while pending:
            done, pending = concurrent.futures.wait(
                pending, timeout=timeout_s, return_when=concurrent.futures.FIRST_COMPLETED
            )
            if not done:
                # timeout_s elapsed with nothing newly finished — report the
                # rest as timed out and stop waiting on them (see docstring).
                for future in pending:
                    case = future_to_case[future]
                    result = CaseResult(
                        case=case, status="timeout", duration_s=timeout_s or 0.0, cost_usd=0.0,
                        error=f"Exceeded {timeout_s}s wait; the underlying call may still be running.",
                    )
                    results.append(result)
                    _log_progress(results, total, started_at, case, result)
                    if on_progress is not None:
                        on_progress(_partial_result(results, total, n, started_at), result)
                pending = set()
                break
            for future in done:
                case = future_to_case[future]
                try:
                    result = future.result()
                except Exception as e:  # noqa: BLE001 — executor-level failure, still just this one case
                    result = CaseResult(case=case, status="failure", duration_s=0.0, cost_usd=0.0, error=f"{type(e).__name__}: {e}")
                results.append(result)
                _log_progress(results, total, started_at, case, result)
                if on_progress is not None:
                    on_progress(_partial_result(results, total, n, started_at), result)
    finally:
        executor.shutdown(wait=False)
        for lg, original in zip(captured_loggers, original_levels):
            lg.setLevel(original)

    completed_at = time.time()
    return BenchmarkRunResult(
        results=results, total_cases=total, concurrency=n,
        started_at=started_at, completed_at=completed_at, elapsed_s=completed_at - started_at,
    )


def _partial_result(results: list[CaseResult], total: int, concurrency: int, started_at: float) -> BenchmarkRunResult:
    now = time.time()
    return BenchmarkRunResult(results=list(results), total_cases=total, concurrency=concurrency, started_at=started_at, completed_at=now, elapsed_s=now - started_at)


def _log_progress(results: list[CaseResult], total: int, started_at: float, case: BenchmarkCase, result: CaseResult) -> None:
    completed = len(results)
    elapsed = time.time() - started_at
    avg = elapsed / completed if completed else 0.0
    remaining_est = avg * (total - completed)
    failed = sum(1 for r in results if r.status != "success")
    logger.info(
        "[Benchmark] %d/%d completed | failed=%d | %s | %s -> %s (%.1fs, $%.4f) | "
        "elapsed=%.1fm | est. remaining=%.1fm",
        completed, total, failed, case.product_label, case.situation_title, result.status,
        result.duration_s, result.cost_usd, elapsed / 60, remaining_est / 60,
    )

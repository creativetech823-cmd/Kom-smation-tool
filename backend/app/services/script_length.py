import re

_SECTION_LABELS: dict[str, str] = {
    "hook": "Hook",
    "problem": "Problem",
    "science": "Science / Psychology / Logic",
    "story": "Story / Emotional Build-up",
    "product_intro": "Product Introduction",
    "ingredients": "Ingredients / Features",
    "benefits": "Benefits",
    "objection_handling": "Objection Handling",
    "cta": "CTA",
}
_SECTION_ORDER = list(_SECTION_LABELS)

# Realistic spoken-word target per duration bucket (~150-165 wpm ad-read pace).
_WORD_TARGETS: dict[str, tuple[int, int]] = {
    "15s": (35, 50),
    "20s": (45, 65),
    "30s": (65, 90),
    "45s": (100, 140),
    "60s": (140, 180),
    "90s": (220, 270),
    "120s": (300, 360),
}

# Exact block quota per section, per duration bucket. At short durations most of
# the 9-part structure is genuinely too much to fit — sections are dropped, not
# compressed into fragments. "hook" and "cta" are pinned to exactly 1 always:
# the JSON shape has a single hook/cta object (not an array like "body").
_SECTION_BLOCKS: dict[str, dict[str, int]] = {
    "15s": {"hook": 1, "problem": 1, "science": 0, "story": 0, "product_intro": 1, "ingredients": 0, "benefits": 0, "objection_handling": 0, "cta": 1},
    "20s": {"hook": 1, "problem": 1, "science": 0, "story": 0, "product_intro": 1, "ingredients": 0, "benefits": 1, "objection_handling": 0, "cta": 1},
    "30s": {"hook": 1, "problem": 1, "science": 1, "story": 0, "product_intro": 1, "ingredients": 0, "benefits": 1, "objection_handling": 0, "cta": 1},
    "45s": {"hook": 1, "problem": 1, "science": 1, "story": 1, "product_intro": 1, "ingredients": 1, "benefits": 1, "objection_handling": 0, "cta": 1},
    "60s": {"hook": 1, "problem": 1, "science": 1, "story": 1, "product_intro": 1, "ingredients": 1, "benefits": 1, "objection_handling": 1, "cta": 1},
    "90s": {"hook": 1, "problem": 2, "science": 1, "story": 2, "product_intro": 1, "ingredients": 1, "benefits": 2, "objection_handling": 1, "cta": 1},
    "120s": {"hook": 1, "problem": 2, "science": 2, "story": 2, "product_intro": 1, "ingredients": 2, "benefits": 2, "objection_handling": 2, "cta": 1},
}

_DEPTH_NOTE: dict[str, str] = {
    "15s": "a single fast beat — hook, the problem in one line, the product, and out",
    "20s": "a very tight cut — every word counts, no room for a detour",
    "30s": "a tight, fast-moving cut — every beat earns its place",
    "45s": "a medium-depth cut — hits the core beats without lingering",
    "60s": "a fuller cut with room to breathe on the science/story beats",
    "90s": "a detailed, fully-developed cut — give every beat real depth",
    "120s": "a cinematic long-form cut — expand story/science/objection handling substantially",
}

_BUCKET_SECONDS = {"15s": 15, "20s": 20, "30s": 30, "45s": 45, "60s": 60, "90s": 90, "120s": 120}
_BUCKET_ORDER = ["15s", "20s", "30s", "45s", "60s", "90s", "120s"]

WPM = 165.0


def bump_bucket(bucket: str) -> str:
    """One tier longer than the given bucket, capped at the longest tier."""
    if bucket in _BUCKET_ORDER and _BUCKET_ORDER.index(bucket) < len(_BUCKET_ORDER) - 1:
        return _BUCKET_ORDER[_BUCKET_ORDER.index(bucket) + 1]
    return bucket


def resolve_target_duration(estimated_length: str, override: str = "") -> str:
    """Pick the duration bucket to write for: an explicit override wins,
    otherwise derive it from the situation's estimated_length, snapping to
    the nearest known bucket. Defaults to "30s" if nothing parses."""
    for candidate in (override, estimated_length):
        if not candidate:
            continue
        match = re.search(r"\d+", candidate)
        if not match:
            continue
        seconds = int(match.group())
        return min(_BUCKET_SECONDS, key=lambda b: abs(_BUCKET_SECONDS[b] - seconds))
    return "30s"


def _quota(bucket: str) -> dict[str, int]:
    return _SECTION_BLOCKS.get(bucket, _SECTION_BLOCKS["30s"])


def included_sections(bucket: str) -> list[str]:
    """Ordered section keys that actually appear at this duration bucket."""
    quota = _quota(bucket)
    return [section for section in _SECTION_ORDER if quota.get(section, 0) > 0]


def _word_target(bucket: str) -> tuple[int, int]:
    return _WORD_TARGETS.get(bucket, _WORD_TARGETS["30s"])


def total_blocks(bucket: str) -> int:
    return sum(_quota(bucket).values())


def target_word_minimum(bucket: str) -> int:
    return _word_target(bucket)[0]


def target_word_maximum(bucket: str) -> int:
    return _word_target(bucket)[1]


def estimate_seconds(word_count: int) -> float:
    """Rough spoken-duration estimate for a given word count, at WPM pace."""
    return round((word_count / WPM) * 60, 1)


def length_directive(
    bucket: str,
    target_word_count: int | None = None,
    current_word_count: int | None = None,
) -> str:
    quota = _quota(bucket)
    blocks = total_blocks(bucket)
    depth = _DEPTH_NOTE.get(bucket, _DEPTH_NOTE["30s"])

    quota_lines = "\n".join(
        f'  - "{section}" ({_SECTION_LABELS[section]}): {count} block(s)'
        for section, count in quota.items()
        if count > 0
    )

    if target_word_count:
        # An explicit numeric target (shorten/extend/slider controls) — this is
        # a length ADJUSTMENT of an existing script, so the block count is a
        # flexible reference, not a hard requirement like during first generation.
        word_lo, word_hi = max(10, target_word_count - 8), target_word_count + 8
        wmin = max(4, word_lo // blocks)
        wmax = max(wmin + 4, -(-word_hi // blocks))  # ceil division
        current_note = ""
        if current_word_count:
            delta = target_word_count - current_word_count
            verb = "add" if delta > 0 else "cut"
            current_note = (
                f"The CURRENT script below is {current_word_count} words. You must {verb} roughly "
                f"{abs(delta)} words to reach the new target — a result close to {current_word_count} "
                f"words unchanged is a FAILED output, this must be a real, noticeable change in length, "
                f"achieved by genuinely expanding/trimming sentences and adding/removing/merging "
                f"blocks, not by tweaking a word or two.\n"
            )
        return (
            f"\nSCRIPT LENGTH TARGET (mandatory — treat as a hard ceiling, not a suggestion): the "
            f"ENTIRE script (hook + every body block + CTA combined) must land at approximately "
            f"{word_lo}-{word_hi} words TOTAL — not per block, not per section, the whole script. "
            f"{current_note}"
            f"This is a length ADJUSTMENT of the current script below — you may add, remove, split, "
            f"or merge body blocks as needed to actually hit this target; the section list below is "
            f"a reference for the beats a {bucket} video like this usually covers, not a fixed "
            f"count:\n{quota_lines}\n"
            f"As a guide, that's roughly {blocks} blocks at {wmin}-{wmax} words each, but adjust the "
            f"block count freely — what matters is landing the TOTAL in {word_lo}-{word_hi} words. "
            f"IMPORTANT: \"hook\" and \"cta\" are always exactly 1 block each — they are single JSON "
            f"objects, not arrays. All other sections' blocks belong in the \"body\" array.\n"
        )

    word_lo, word_hi = _word_target(bucket)
    wmin = max(4, word_lo // blocks)
    wmax = max(wmin + 4, -(-word_hi // blocks))  # ceil division
    return (
        f"\nSCRIPT LENGTH & STRUCTURE QUOTA (mandatory — this is a common failure mode: writing a "
        f"script that's several times too long to actually voice in {bucket}; treat the word count "
        f"as a hard ceiling, not a suggestion): this is a ~{bucket} video, {depth}. At normal spoken "
        f"ad-read pace that means the ENTIRE script (hook + every body block + CTA combined) must "
        f"land at approximately {word_lo}-{word_hi} words TOTAL — not per block, not per section, "
        f"the whole script. Write EXACTLY this many blocks tagged with each \"section\" value (a "
        f"block is one hook/body/cta array entry), and do NOT include any section not listed here:\n"
        f"{quota_lines}\n"
        f"That is {blocks} blocks total. Each block's \"text\" should be roughly {wmin}-{wmax} words "
        f"— short, punchy, spoken-pace phrases, not full paragraphs. Writing more blocks than listed, "
        f"adding sections not listed, or writing long blocks that blow past the total word budget is "
        f"a FAILED output — a {bucket} video cannot carry more than ~{word_hi} spoken words. "
        f"IMPORTANT: \"hook\" and \"cta\" are always exactly 1 block each — they are single JSON "
        f"objects, not arrays. All other sections' blocks belong in the \"body\" array.\n"
    )


def count_words(data: dict) -> int:
    def words(text: object) -> int:
        return len(str(text or "").split())

    total = words(data.get("hook", {}).get("text") if isinstance(data.get("hook"), dict) else "")
    for line in data.get("body", []) or []:
        if isinstance(line, dict):
            total += words(line.get("text"))
    cta = data.get("cta")
    if isinstance(cta, dict):
        total += words(cta.get("text"))
    return total

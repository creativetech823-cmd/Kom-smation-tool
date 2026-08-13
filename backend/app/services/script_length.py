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

# Exact block quota per section, per duration bucket — concrete per-beat counts
# are far more reliable to hit than an abstract total-word target. "hook" and
# "cta" are pinned to exactly 1: the JSON shape has a single hook/cta object
# (not an array like "body"), so any extra weight there goes to "story" instead.
_SECTION_BLOCKS: dict[str, dict[str, int]] = {
    "15s": {"hook": 1, "problem": 1, "science": 1, "story": 1, "product_intro": 1, "ingredients": 1, "benefits": 1, "objection_handling": 0, "cta": 1},
    "30s": {"hook": 1, "problem": 2, "science": 3, "story": 4, "product_intro": 2, "ingredients": 3, "benefits": 3, "objection_handling": 2, "cta": 1},
    "45s": {"hook": 1, "problem": 3, "science": 4, "story": 5, "product_intro": 3, "ingredients": 4, "benefits": 4, "objection_handling": 3, "cta": 1},
    "60s": {"hook": 1, "problem": 4, "science": 5, "story": 8, "product_intro": 4, "ingredients": 5, "benefits": 5, "objection_handling": 4, "cta": 1},
    "90s": {"hook": 1, "problem": 6, "science": 7, "story": 12, "product_intro": 5, "ingredients": 7, "benefits": 8, "objection_handling": 7, "cta": 1},
}

# (min, max) words per individual block's "text" field, per bucket.
_WORDS_PER_BLOCK: dict[str, tuple[int, int]] = {
    "15s": (10, 18),
    "30s": (14, 20),
    "45s": (15, 22),
    "60s": (16, 24),
    "90s": (16, 24),
}

_DEPTH_NOTE: dict[str, str] = {
    "15s": "a tight, fast-moving cut — every beat earns its place",
    "30s": "a medium-depth cut — hit every structural beat but keep it moving",
    "45s": "a fuller cut with room to breathe on the science/story beats",
    "60s": "a detailed, fully-developed cut — give every beat real depth",
    "90s": "a cinematic long-form cut — expand story/science/objection handling substantially",
}

_BUCKET_SECONDS = {"15s": 15, "30s": 30, "45s": 45, "60s": 60, "90s": 90}
_BUCKET_ORDER = ["15s", "30s", "45s", "60s", "90s"]


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


def total_blocks(bucket: str) -> int:
    return sum(_quota(bucket).values())


def target_word_minimum(bucket: str) -> int:
    wmin, _wmax = _WORDS_PER_BLOCK.get(bucket, _WORDS_PER_BLOCK["30s"])
    return total_blocks(bucket) * wmin


def length_directive(bucket: str) -> str:
    quota = _quota(bucket)
    wmin, wmax = _WORDS_PER_BLOCK.get(bucket, _WORDS_PER_BLOCK["30s"])
    depth = _DEPTH_NOTE.get(bucket, _DEPTH_NOTE["30s"])
    blocks = total_blocks(bucket)
    word_lo, word_hi = blocks * wmin, blocks * wmax

    quota_lines = "\n".join(
        f'  - "{section}" ({_SECTION_LABELS[section]}): {count} block(s)'
        for section, count in quota.items()
        if count > 0
    )

    return (
        f"\nSCRIPT LENGTH & STRUCTURE QUOTA (mandatory — a common failure mode is writing far too "
        f"few blocks; follow this exactly): this is a ~{bucket} video, {depth}. Write EXACTLY this "
        f"many blocks tagged with each \"section\" value (a block is one hook/body/cta array entry):\n"
        f"{quota_lines}\n"
        f"That is {blocks} blocks total. Each block's \"text\" should be roughly {wmin}-{wmax} words "
        f"(a full sentence or two, not a sentence fragment) — landing the whole script around "
        f"{word_lo}-{word_hi} words all together. Writing noticeably fewer blocks, or merging several "
        f"of these blocks into one, is a FAILED output — hit the exact per-section counts above. "
        f"IMPORTANT: \"hook\" and \"cta\" are always exactly 1 block each — they are single JSON "
        f"objects, not arrays. All the other sections' extra blocks belong in the \"body\" array.\n"
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

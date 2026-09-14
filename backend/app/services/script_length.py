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

# Creative-depth word bands per duration bucket (~150-165 wpm ad-read pace).
# These are targets to land naturally within, not a word count to hit
# mechanically — see _DEPTH_NOTE for what actually has to change between
# tiers (new story beats, not more words per beat).
_WORD_TARGETS: dict[str, tuple[int, int]] = {
    "15s": (20, 35),
    "20s": (40, 65),
    "30s": (70, 100),
    "45s": (105, 150),
    "60s": (150, 190),
    "90s": (160, 230),
    "120s": (240, 320),
}

# Exact block quota per section, per duration bucket — each tier up adds a
# genuinely new beat (a new section, or a second block of an existing one
# representing a distinct sub-beat), not just more room inside the same
# beats. "hook" and "cta" are pinned to exactly 1 always: the JSON shape has
# a single hook/cta object (not an array like "body").
_SECTION_BLOCKS: dict[str, dict[str, int]] = {
    "15s": {"hook": 1, "problem": 1, "science": 0, "story": 0, "product_intro": 1, "ingredients": 0, "benefits": 0, "objection_handling": 0, "cta": 1},
    "20s": {"hook": 1, "problem": 1, "science": 0, "story": 1, "product_intro": 1, "ingredients": 0, "benefits": 1, "objection_handling": 0, "cta": 1},
    "30s": {"hook": 1, "problem": 1, "science": 1, "story": 1, "product_intro": 1, "ingredients": 1, "benefits": 1, "objection_handling": 0, "cta": 1},
    "45s": {"hook": 1, "problem": 2, "science": 1, "story": 1, "product_intro": 1, "ingredients": 1, "benefits": 1, "objection_handling": 1, "cta": 1},
    "60s": {"hook": 1, "problem": 2, "science": 1, "story": 2, "product_intro": 1, "ingredients": 1, "benefits": 1, "objection_handling": 1, "cta": 1},
    "90s": {"hook": 1, "problem": 2, "science": 1, "story": 2, "product_intro": 1, "ingredients": 1, "benefits": 2, "objection_handling": 1, "cta": 1},
    "120s": {"hook": 1, "problem": 2, "science": 2, "story": 2, "product_intro": 1, "ingredients": 2, "benefits": 2, "objection_handling": 2, "cta": 1},
}

# What must genuinely be NEW at each tier — not "more words", specific beats
# that add information the shorter tier didn't have room for. Reused by both
# branches of length_directive() (fresh generation AND the Script Length
# control's length-adjustment regenerate) so a "+"/"-" click gets the same
# structural guidance as a first generation.
_DEPTH_NOTE: dict[str, str] = {
    "15s": (
        "a single fast beat: hook -> one sharp problem/idea -> the product/benefit -> out. No room "
        "for a detour — every word has to earn its place."
    ),
    "20s": (
        "a compact ad with a real beginning, one beat of tension, and a close: hook -> problem/"
        "situation -> one beat of genuine emotional or practical tension -> product intro -> the one "
        "benefit that matters most -> cta. Six distinct beats, each saying something the previous one "
        "didn't — not the same idea restated in a second sentence."
    ),
    "30s": (
        "a complete short-form ad: hook -> situation -> problem -> a beat of escalation or insight "
        "(why this actually happens, or why it matters more than it first seems) -> product "
        "introduction -> the relevant benefit(s) -> an emotional or product payoff -> cta. Every beat "
        "must add information the previous beat didn't have — no beat should just restate the one "
        "before it in different words."
    ),
    "45s": (
        "a developed story, not a longer version of the 30s ad: hook -> a strong opening situation -> "
        "a relatable problem -> a SPECIFIC consequence of that problem (a concrete moment, not the "
        "same problem restated) -> real emotional tension -> a turning point -> product introduction "
        "-> the product's mechanism/benefit -> the experience/payoff -> a closing thought that "
        "connects back to the hook -> cta. Two body beats now develop the problem (the problem itself, "
        "then its specific consequence) instead of one — that is where the extra length goes, not "
        "into padding the existing beats."
    ),
    "60s": (
        "a fuller cut with genuine room to breathe — expand the situation, the specific consequence, "
        "the turning point, and the product's benefits into real, distinct beats (two body beats "
        "develop the human situation, two develop the product experience) rather than compressing "
        "each into one generic line."
    ),
    "90s": (
        "a complete ad-film / UGC narrative in roughly 6-9 meaningful beats, each contributing "
        "something the others don't: (1) hook that creates curiosity, (2) situation — who this person "
        "is and what they want, (3) problem — the specific obstacle, (4) tension — why that obstacle "
        "actually matters emotionally, (5) turning point — the realization or change, (6) product "
        "introduced naturally at that turning point, (7) experience — the relevant benefit(s) shown "
        "through the person's actual experience, not a features list, (8) payoff that returns to the "
        "original goal/hook, (9) a cta that reads as the natural next sentence after the story. This "
        "must read as one continuous advertisement, not an expanded bullet list — if any two beats "
        "could be merged without losing information, the script is not developed enough yet."
    ),
    "120s": (
        "a cinematic long-form cut — every beat from the 90s structure gets real depth: expand the "
        "situation, escalate the problem with a specific consequence, give the turning point an "
        "actual moment (not a summary of one), and let the product's benefits emerge through the "
        "story rather than being listed."
    ),
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
        # An explicit numeric target (the Script Length control's +/-,
        # Shorten/Extend, etc.) — a length ADJUSTMENT of an existing script,
        # so the block count is a flexible reference, not a hard requirement
        # like during first generation. This is the exact path a "+"/"-"
        # click uses, so it carries the same depth-note structural guidance
        # as a fresh generation (see _DEPTH_NOTE) — the level control must
        # change the STORY, not just the number attached to it.
        word_lo, word_hi = max(10, target_word_count - 8), target_word_count + 8
        wmin = max(4, word_lo // blocks)
        wmax = max(wmin + 4, -(-word_hi // blocks))  # ceil division
        current_note = ""
        if current_word_count:
            delta = target_word_count - current_word_count
            verb = "add" if delta > 0 else "cut"
            growth_note = (
                f" Grow it by adding NEW story beats — {depth} — real story development, context, "
                f"tension, a concrete example, a beat of dialogue, deeper product relevance, or a "
                f"fuller emotional payoff. Do NOT grow it by: repeating the same point in different "
                f"words, adding a generic motivational sentence, repeating the product name, adding "
                f"filler adjectives, restating a benefit you already stated, or reaching for a "
                f"generic AI advertising phrase. If a sentence could be deleted without losing any "
                f"information, it should not have been added."
                if delta > 0
                else " Cut it by removing or merging whole beats/ideas — drop the least essential "
                "beat entirely rather than trimming every beat by a few words, which just makes "
                "every beat feel thin instead of making the story shorter."
            )
            current_note = (
                f"The CURRENT script below is {current_word_count} words. You must {verb} roughly "
                f"{abs(delta)} words to reach the new target — a result close to {current_word_count} "
                f"words unchanged is a FAILED output, this must be a real, noticeable change in length, "
                f"achieved by genuinely expanding/trimming sentences and adding/removing/merging "
                f"blocks, not by tweaking a word or two.{growth_note}\n"
            )
        return (
            f"\nSCRIPT LENGTH TARGET (mandatory — treat as a hard ceiling, not a suggestion): the "
            f"ENTIRE script (hook + every body block + CTA combined) must land at approximately "
            f"{word_lo}-{word_hi} words TOTAL — not per block, not per section, the whole script. "
            f"This is a ~{bucket}-scale ad: {depth}\n"
            f"{current_note}"
            f"This is a length ADJUSTMENT of the current script below — you may add, remove, split, "
            f"or merge body blocks as needed to actually hit this target; the section list below is "
            f"a reference for the beats a {bucket} video like this usually covers, not a fixed "
            f"count:\n{quota_lines}\n"
            f"As a guide, that's roughly {blocks} blocks at {wmin}-{wmax} words each, but adjust the "
            f"block count freely — what matters is landing the TOTAL in {word_lo}-{word_hi} words AND "
            f"actually following the beat structure above, not just hitting a number. The hook's "
            f"promise still needs a real payoff, and the CTA still needs to emerge from the story, not "
            f"be a generic tagline bolted onto the end — the longer the script, the more the ending "
            f"should explicitly connect back to what the hook opened. "
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
        f"a FAILED output — a {bucket} video cannot carry more than ~{word_hi} spoken words. A longer "
        f"bucket than a shorter one must mean genuinely new story beats — never the same beats "
        f"stretched out with filler, repeated ideas, restating a benefit already stated, or a generic "
        f"motivational sentence added just to fill space. The hook's promise needs a real payoff, and "
        f"the cta must emerge from the story, not read as a generic tagline bolted onto the end. "
        f"IMPORTANT: \"hook\" and \"cta\" are always exactly 1 block each — they are single JSON "
        f"objects, not arrays. All other sections' blocks belong in the \"body\" array.\n"
    )


# Static ad copy runs far shorter than a spoken video script at the same
# "size" — thresholds pick which structural guidance applies, given only
# the (already static-scaled) target_word_count, not a level name.
_STATIC_DEPTH_NOTE: list[tuple[int, str]] = [
    (14, "a very short creative — headline plus a short CTA, and nothing else; every word must earn its place"),
    (22, "a compact ad — headline, one supporting line, and a CTA"),
    (35, "a complete short static ad — headline, a stronger supporting message, the one benefit that matters most, and a CTA"),
    (55, "a developed static ad — headline, supporting copy that actually explains why the product fits, a concrete product-relevance detail, and a CTA"),
]
_STATIC_DEPTH_NOTE_LONGEST = (
    "a fully developed static ad — headline, multiple meaningful supporting lines that build a real "
    "message (not just restate the headline), a genuine product story or specific relevance detail, "
    "and a CTA. Still a static graphic, not a video script — every line must work as on-image copy, "
    "not a paragraph of body text."
)


def _static_depth_note(target_word_count: int) -> str:
    for ceiling, note in _STATIC_DEPTH_NOTE:
        if target_word_count <= ceiling:
            return note
    return _STATIC_DEPTH_NOTE_LONGEST


def static_length_directive(target_word_count: int | None, current_word_count: int | None = None) -> str:
    """Static creative's counterpart to length_directive() — only produces
    text when target_word_count is explicitly given (i.e. the Script Length
    control was used on a static creative). A fresh static generation with
    no explicit target keeps using content_formats.py's own tight,
    format-specific word ceilings (headline/body/cta), which this must NOT
    override — static ad copy runs far shorter than a spoken video script
    at the same "size", so callers pass a static-scaled word count, not the
    video one."""
    if not target_word_count:
        return ""
    word_lo, word_hi = max(4, target_word_count - 6), target_word_count + 6
    depth = _static_depth_note(target_word_count)
    current_note = ""
    if current_word_count:
        delta = target_word_count - current_word_count
        verb = "add" if delta > 0 else "cut"
        growth_note = (
            " Grow it with a genuinely new supporting line or a more specific product-relevance "
            "detail — never by padding with filler adjectives, repeating the headline's idea in "
            "different words, or repeating the product name."
            if delta > 0
            else " Cut it by removing a whole line, not by trimming every line down to a fragment."
        )
        current_note = (
            f"The CURRENT creative below is {current_word_count} words. You must {verb} roughly "
            f"{abs(delta)} words to reach the new target — a result close to {current_word_count} "
            f"words unchanged is a FAILED output.{growth_note}\n"
        )
    return (
        f"\nCOPY LENGTH TARGET (mandatory): the ENTIRE creative's copy (headline + every body/"
        f"supporting block + CTA combined) must land at approximately {word_lo}-{word_hi} words "
        f"TOTAL — this is {depth}. {current_note}"
        f"This is a length ADJUSTMENT — grow it with real substance (a genuine supporting line, a "
        f"more specific detail) or trim it by cutting a whole block, never by padding with filler "
        f"adjectives or awkwardly truncating a sentence. Never turn this into a paragraph of body "
        f"copy just because the target is larger — it is still a static graphic. Still respect the "
        f"format's own STRUCTURE below for which blocks exist — add/remove only where that structure "
        f"allows optional blocks.\n"
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

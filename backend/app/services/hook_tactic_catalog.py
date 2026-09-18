"""Hooks Menu — the HOOK TACTIC vocabulary (2026-09-18 task). Deliberately a
SEPARATE axis from creative_mechanism_catalog.py's CREATIVE MECHANISM: a hook
tactic is HOW attention is captured in the first 1-3 seconds (a technique);
a creative mechanism is WHAT the underlying idea is (object-driven-reveal,
ritual-replacement, ...). The two combine — e.g. a "Question" hook tactic
opening into a "Ritual Replacement" creative mechanism — but must never be
stored or reasoned about as the same field. Same catalog-with-description/
validator convention as creative_angles.py and creative_mechanism_catalog.py.

Execution guidance for the 8 tactics the task spelled out explicitly
(Question, Reaction in Action, Absurd Alternative, Teaser Hook, Make Me
Laugh, Skeptical Voice, Negative Hook, Evolution) is quoted close to the
task's own wording. The remaining 10 tactics were named but not given
explicit execution notes in the task — their descriptions below are a
reasonable, conventional reading of each named technique, not verbatim from
the task; flagged here so this is auditable rather than presented as if the
task specified all 18 in equal detail.
"""

HOOK_TACTICS: list[dict[str, str]] = [
    {
        "label": "Dramatize the Problem",
        "description": "Open by staging the problem itself as a visible moment (not narrating it) — the "
        "audience sees the problem happening, not being described.",
    },
    {
        "label": "Motion Tricks",
        "description": "A visually arresting physical motion/transition (a whip-pan, a snap-transform, an "
        "unexpected camera move) creates the stop-scroll instant, tied to the actual subject, not a "
        "generic effect.",
    },
    {
        "label": "Podcast",
        "description": "Opens mid-conversation, dropped into an ongoing podcast/interview-style exchange — "
        "the viewer is caught mid-sentence, creating the sense of overhearing something real.",
    },
    {
        "label": "Reminder",
        "description": "Opens by naming something the viewer already knows/does but hasn't consciously "
        "registered — a recognition beat, not new information.",
    },
    {
        "label": "The Absurd Alternative",
        "description": "Show the unexpected/absurd behavior FIRST, before revealing the product — the "
        "viewer sees someone doing something strange/extreme and wants to know why, before any "
        "explanation arrives.",
    },
    {
        "label": "In Real Life",
        "description": "A grounded, unstaged-feeling, documentary-style real moment — authenticity itself "
        "is the hook, not a polished setup.",
    },
    {
        "label": "Reaction in Action",
        "description": "Show the reaction happening immediately — open on the face/body reacting to "
        "something, before the audience knows what caused it.",
    },
    {
        "label": "Question",
        "description": "Do not merely write a question — open the actual scene WITH a question (asked by "
        "a character, or posed through a concrete situation) that creates real curiosity, not a "
        "rhetorical line stapled onto generic footage.",
    },
    {
        "label": "Evolution",
        "description": "Show an actual progression/change happening (a sequence, a visible shift over "
        "steps) rather than simply stating 'before and after' as a claim.",
    },
    {
        "label": "Shocking Effect",
        "description": "A genuinely surprising visual/statement in the first instant — specific and "
        "earned by what follows, not shock for its own sake.",
    },
    {
        "label": "On Trend / FOMO",
        "description": "Opens by referencing a visible, current social pattern the viewer recognizes "
        "others already doing — the hook is the fear of being behind, grounded in something specific.",
    },
    {
        "label": "Teaser Hook",
        "description": "Create an information gap and deliberately delay the reveal — the opening shows "
        "enough to create a specific question, withholding the answer on purpose.",
    },
    {
        "label": "Emphasize the Solution",
        "description": "Opens directly on the solution/outcome in action (not the problem) — used when "
        "the result itself is visually striking enough to be the hook.",
    },
    {
        "label": "Negative Hook",
        "description": "Start with a relevant negative statement or warning, then create the turn — the "
        "negative framing must connect directly to what follows, not be a generic scare line.",
    },
    {
        "label": "Make Me Laugh",
        "description": "Start with an actual comedic situation or action happening on screen — not a "
        "generic funny-sounding sentence with nothing being performed.",
    },
    {
        "label": "Satisfying Intro",
        "description": "Opens on a visually/sensorially satisfying moment (a clean action, a precise "
        "motion, an ASMR-adjacent detail) that rewards watching for its own sake.",
    },
    {
        "label": "Destroy / Toss & Burn",
        "description": "Opens with a decisive destructive/discarding action (throwing away, crushing, "
        "burning the old thing) as a visual statement of rejection before the alternative appears.",
    },
    {
        "label": "Skeptical Voice",
        "description": "Begin with doubt or resistance — a character (or the narrator) openly skeptical — "
        "and then earn the product reveal through what follows, not by asserting it away.",
    },
]

_NORMALIZED_LOOKUP: dict[str, str] = {t["label"].strip().lower(): t["label"] for t in HOOK_TACTICS}
_DEFAULT_FALLBACK = "Question"


def catalog_prompt_block() -> str:
    return "\n".join(f"- {t['label']}: {t['description']}" for t in HOOK_TACTICS)


def valid_hook_tactic_label(raw: str) -> str:
    """Canonicalizes a single reported hook tactic against the known
    catalog (case/whitespace-insensitive); falls back to a safe default
    rather than trusting an invented/misspelled label."""
    canonical = _NORMALIZED_LOOKUP.get((raw or "").strip().lower())
    return canonical or _DEFAULT_FALLBACK

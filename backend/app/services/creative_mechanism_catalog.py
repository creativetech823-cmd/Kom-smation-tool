"""Creative Mechanism catalog — the WHAT-MAKES-IT-WORK primitive vocabulary
extracted from real reference ad scripts (see creative_reference_dna.py's
mechanism-tagged records), distinct from both creative_angles.py's execution
STYLE (HOW it's filmed) and creative_architecture.py's beat STRUCTURE (the
scene scaffolding). A mechanism is the underlying creative engine a story
situation is built from — object-driven reveal, ritual replacement, value
math, etc. — same catalog-with-description-and-validator convention as
creative_angles.py, so story_situation_service.py can both INSTRUCT
generation with it and VALIDATE the model's own reported mechanism against
it, never trusting free-text the model could invent or misspell.

These are creative PRIMITIVES, not mandatory templates — a story situation
combines a mechanism with a specific human situation/behavior/tension/
product role; forcing every candidate through the same one or two mechanisms
is exactly the repetitive convergence this catalog exists to prevent (see
story_situation_service.py's mechanism-variety selection).
"""

CREATIVE_MECHANISMS: list[dict[str, str]] = [
    {
        "label": "Object-Driven Reveal",
        "description": "A physical object (a packet, a note, a pocket, a ritual gesture) carries the "
        "story — curiosity/expectation is built around the object, then a contrast or reveal changes "
        "what it turns out to be.",
    },
    {
        "label": "Ritual Replacement",
        "description": "The familiar ritual/taste/motion continues unchanged; only the choice inside it "
        "changes — old ritual -> familiarity preserved -> new choice -> different outcome/meaning.",
    },
    {
        "label": "Value Math",
        "description": "A specific number (a price, a count, a frequency) visually accumulates into a "
        "realization the viewer does the math on themselves — not just \"it's cheap\", but a concrete "
        "sum that reframes an everyday habit.",
    },
    {
        "label": "Character-as-Proof",
        "description": "A character's personality/competence is established through behavior BEFORE the "
        "product appears, so the product choice reads as a natural extension of who they already are, "
        "not a lecture handed to them.",
    },
    {
        "label": "Peer Realization",
        "description": "A friend, colleague, sibling, or the person's own observation — not an authority "
        "figure — introduces the alternative or triggers the realization.",
    },
    {
        "label": "Upgrade / Modernization",
        "description": "Everything else in the person's life has modernized/upgraded; one old habit "
        "hasn't caught up — the tension is inconsistency, not fear.",
    },
    {
        "label": "Behavioral Comedy / Satire",
        "description": "Humor or gentle satire built from a specific, recognizable behavior pattern, not "
        "generic jokes — the comedy IS the observation.",
    },
    {
        "label": "Social Contradiction",
        "description": "A visible gap between how someone presents themselves and a private habit — the "
        "story plays the contradiction, not a moral lecture about it.",
    },
    {
        "label": "Unexpected Reveal",
        "description": "The viewer expects one specific thing to happen (based on a familiar setup) and "
        "a specific, concrete detail turns out different — a genuine turn, not just a twist ending.",
    },
    {
        "label": "Familiar Ritual Interrupted",
        "description": "A precisely repeated daily routine (same chair, same time, same motion) is shown "
        "as routine, then one specific beat in it changes — the interruption IS the story.",
    },
    {
        "label": "Before/After Behavioral Contrast",
        "description": "Two moments of the SAME behavior, changed — not a narrated claim about change, "
        "an observable behavioral contrast the viewer can see for themselves.",
    },
    {
        "label": "Social Experiment",
        "description": "A real-feeling, semi-documentary setup (asking people, testing reactions, a "
        "cumulative group response) used as proof, not a single scripted testimonial.",
    },
    {
        "label": "Self-Realization",
        "description": "The person notices something about their own behavior themselves — tracked "
        "spending, a repeated action, a pattern — no one else has to tell them.",
    },
    {
        "label": "Curiosity Through an Object",
        "description": "An object is shown or mentioned with no explanation yet, creating a specific "
        "question the viewer wants answered — not a vague curiosity gap, a concrete unanswered detail.",
    },
    {
        "label": "Everyday Specific Situation",
        "description": "A precisely observed, ordinary Indian moment (a specific commute, a specific "
        "office break, a specific family meal) grounds the story in real specificity rather than a "
        "generic \"daily life\" montage.",
    },
    {
        "label": "Sensory Specificity",
        "description": "The story is told through concrete sensory/behavioral detail (reaching into a "
        "pocket, a specific sound, a specific taste reaction) rather than an abstract emotional "
        "statement.",
    },
]

_NORMALIZED_LOOKUP: dict[str, str] = {m["label"].strip().lower(): m["label"] for m in CREATIVE_MECHANISMS}
_DEFAULT_FALLBACK = "Everyday Specific Situation"


def catalog_prompt_block() -> str:
    """The vocabulary listing injected into the story-situations system
    prompt — label plus the mechanism's actual WORKING PRINCIPLE, not just a
    name, so the model understands what to build, not just what to label."""
    return "\n".join(f"- {m['label']}: {m['description']}" for m in CREATIVE_MECHANISMS)


def valid_mechanism_label(raw: str) -> str:
    """Canonicalizes a single reported mechanism against the known catalog
    (case/whitespace-insensitive); falls back to a safe default rather than
    trusting an invented or misspelled label, same convention as
    creative_angles.valid_angle_labels()."""
    canonical = _NORMALIZED_LOOKUP.get((raw or "").strip().lower())
    return canonical or _DEFAULT_FALLBACK

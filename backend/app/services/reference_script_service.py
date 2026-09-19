"""Real AayushWellness reference scripts — import + retrieval (2026-09-19).

Why this exists: `product_reference_scripts` was empty. The Product Library
has always supported reference scripts (create/list/approve endpoints,
`build_product_context()` -> `reference_script_excerpts` -> the writer
prompt), and `creative_reference_dna.py` holds hand-condensed DNA records for
five real Herbal Masala scripts from "Calender Video August.docx" — but
nothing ever imported the document's actual script TEXT into the table, and
the DB file is gitignored/per-environment, so no environment had them. The
writer therefore never saw a single real sentence of the brand's own winning
scripts, only abstract metadata — which cannot teach sentence construction,
Hinglish phrasing, or punchline rhythm.

This module is the missing importer plus a mechanism-aware retriever. It
reuses the existing table and the existing prompt path; it does not add a
new reference architecture. Structured creative DNA (hook_device,
human_insight, payoff...) stays in creative_reference_dna.REFERENCE_RECORDS,
joined by `reference_key` == that record's video_id — one source of truth.

The document is CREATIVE REFERENCE MATERIAL, never approved product fact:
several scripts contain health/ingredient/"no chemicals" claims. Every
imported row's notes say so, and the prompt header repeats it — Claim Safety
and the product's approved claims remain the only authority.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.db_models import AyushProduct, ProductReferenceScript
from app.services import creative_reference_dna

logger = logging.getLogger("reference_dna")

SOURCE_DOCUMENT = "Calender Video August.docx"
# backend/app/services/<this file> -> backend/
DEFAULT_DOCUMENT_PATH = Path(__file__).resolve().parents[2] / SOURCE_DOCUMENT

# Script number in the document -> (creative direction, creative_mechanism_
# catalog label). Mechanism labels match the CAL1/CAL3/CAL4/CAL5 records
# already in creative_reference_dna.py. Script 2 ("Problem to Solution") has
# no DNA record and no honest catalog mechanism, so it deliberately carries
# none rather than a forced one — it is retrievable by direction only.
_SCRIPT_METADATA: dict[int, tuple[str, str]] = {
    1: ("Premium / Upgrade", "Upgrade / Modernization"),
    2: ("Problem → Solution", ""),
    3: ("Money / Value", "Value Math"),
    4: ("Funny / Sarcastic", "Character-as-Proof"),
    5: ("Character / Persona", "Peer Realization"),
}

_SCRIPT_MARKER = re.compile(r"^\s*Script\s*(\d+)\s*:\s*-?\s*(.*?)\s*$", re.IGNORECASE)

_REFERENCE_NOTES = (
    "Imported from {source} (Script {n}). Creative reference material only — claims inside this "
    "script (ingredient/health/efficacy, 'no chemicals', 'healthy alternative', etc.) are NOT approved "
    "product facts. Claim Safety and the product's approved claims remain the only authority."
)

# The instruction that travels with every reference excerpt into the writer
# prompt (script_service._context_block and the no-product-context path).
REFERENCE_PROMPT_HEADER = (
    "REAL AAYUSHWELLNESS REFERENCE SCRIPTS — creative DNA + language DNA. Study the reference examples "
    "for patterns and writing DNA. Transfer the underlying style and principles. Never copy sentences, "
    "phrases, characters, or story wording. Learn from them: how sentences are built and how long they "
    "run, the conversational Hinglish rhythm, how a punchline lands, how the product enters, how the CTA "
    "is phrased — then write an ORIGINAL script for THIS story. These are creative reference material, "
    "NOT approved product facts: any health, ingredient, efficacy, or 'no chemicals/no tobacco' claim "
    "inside a reference must NOT be reused unless the approved claims/product info elsewhere in this "
    "prompt supports it — claim safety always wins over a reference:"
)


@dataclass(frozen=True)
class ParsedReference:
    number: int
    title: str
    script_text: str
    direction: str
    mechanism: str

    @property
    def reference_key(self) -> str:
        return f"CAL{self.number}"


@dataclass
class ImportResult:
    products_matched: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    references_in_document: int = 0
    product_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReferenceHit:
    reference_key: str
    title: str
    direction: str
    mechanism: str
    text: str


# --- parsing ----------------------------------------------------------------


def parse_calender_document(path: Path | str | None = None) -> list[ParsedReference]:
    """Splits the document at its "Script N:-" markers and keeps each
    script's ACTUAL wording untouched (only blank paragraphs/lines and edge
    whitespace are dropped — typos and phrasing are preserved on purpose,
    they're part of the language DNA). The leading "Sales Ad Script analyze
    Points" notes are analysis of a different ad, not an Aayush script, so
    they are not imported."""
    import docx  # local import: python-docx is only needed for import, not request serving

    document = docx.Document(str(path or DEFAULT_DOCUMENT_PATH))
    scripts: list[tuple[int, str, list[str]]] = []
    for paragraph in document.paragraphs:
        marker = _SCRIPT_MARKER.match(paragraph.text.splitlines()[0]) if paragraph.text.strip() else None
        if marker:
            scripts.append((int(marker.group(1)), marker.group(2).strip(), []))
            continue
        if not scripts:
            continue
        lines = [ln.strip() for ln in paragraph.text.splitlines() if ln.strip()]
        scripts[-1][2].extend(lines)

    parsed = []
    for number, title, lines in scripts:
        text = "\n".join(lines).strip()
        if not text:
            continue
        direction, mechanism = _SCRIPT_METADATA.get(number, (title or f"Script {number}", ""))
        parsed.append(ParsedReference(number=number, title=title or f"Script {number}", script_text=text,
                                      direction=direction, mechanism=mechanism))
    return parsed


# --- product matching -------------------------------------------------------

_BRAND_TOKENS = {"aayush", "ayush", "wellness"}


def _normalize_name(name: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", (name or "").lower())
    return " ".join(t for t in tokens if t not in _BRAND_TOKENS)


def is_herbal_masala_name(name: str) -> bool:
    return _normalize_name(name) == "herbal masala"


def _herbal_masala_products(db: Session) -> list[AyushProduct]:
    return [p for p in db.query(AyushProduct).all() if is_herbal_masala_name(p.name)]


# --- import -----------------------------------------------------------------


def _upsert_for_product(db: Session, product: AyushProduct, refs: list[ParsedReference], result: ImportResult) -> None:
    for ref in refs:
        existing = (
            db.query(ProductReferenceScript)
            .filter(ProductReferenceScript.product_id == product.id, ProductReferenceScript.reference_key == ref.reference_key)
            .first()
        )
        if existing is None:
            db.add(ProductReferenceScript(
                product_id=product.id, title=ref.title, script_text=ref.script_text, format="video",
                notes=_REFERENCE_NOTES.format(source=SOURCE_DOCUMENT, n=ref.number), is_approved=True,
                source_document=SOURCE_DOCUMENT, reference_key=ref.reference_key,
                creative_direction=ref.direction, creative_mechanism=ref.mechanism,
            ))
            result.created += 1
            continue
        # Source-owned fields are refreshed; is_approved and notes are left
        # alone so a curator who un-approves a reference isn't overridden.
        changed = False
        for attr, value in (
            ("title", ref.title), ("script_text", ref.script_text), ("source_document", SOURCE_DOCUMENT),
            ("creative_direction", ref.direction), ("creative_mechanism", ref.mechanism),
        ):
            if getattr(existing, attr) != value:
                setattr(existing, attr, value)
                changed = True
        if changed:
            result.updated += 1
        else:
            result.unchanged += 1


def import_calender_references(
    db: Session, document_path: Path | str | None = None, products: list[AyushProduct] | None = None
) -> ImportResult:
    """Idempotent: keyed by (product_id, reference_key). Running it twice
    creates nothing the second time. Attaches to every Herbal Masala product
    (the library can legitimately hold more than one row for it)."""
    refs = parse_calender_document(document_path)
    targets = products if products is not None else _herbal_masala_products(db)
    result = ImportResult(products_matched=len(targets), references_in_document=len(refs),
                          product_ids=[p.id for p in targets])
    for product in targets:
        _upsert_for_product(db, product, refs, result)
    db.commit()
    logger.info(
        "[REFERENCE_DNA] import complete document=%s references_in_document=%d products_matched=%d "
        "created=%d updated=%d unchanged=%d",
        SOURCE_DOCUMENT, result.references_in_document, result.products_matched,
        result.created, result.updated, result.unchanged,
    )
    return result


def seed_reference_scripts_safely(db: Session) -> None:
    """Startup hook — never raises (a missing/corrupt document must not take
    the API down; the failure is logged loudly instead)."""
    try:
        import_calender_references(db)
    except Exception as e:
        db.rollback()
        logger.warning("[REFERENCE_DNA] startup import skipped: %s", e)


# --- retrieval --------------------------------------------------------------


def _resolve_product_ids(db: Session, product_id: str, product_name: str) -> list[str]:
    ids: list[str] = []
    if product_id:
        ids.append(product_id)
    normalized = _normalize_name(product_name)
    if normalized:
        for p in db.query(AyushProduct).all():
            if _normalize_name(p.name) == normalized and p.id not in ids:
                ids.append(p.id)
    return ids


def _score(hit: ReferenceHit, mechanism: str, hint_text: str) -> int:
    score = 0
    if mechanism and hit.mechanism and hit.mechanism.lower() == mechanism.lower():
        score += 10
    hint = (hint_text or "").lower()
    if any(tok in hint for tok in re.findall(r"[a-z]{4,}", hit.direction.lower())):
        score += 3
    return score


def select_reference_scripts(
    db: Session, *, product_id: str = "", product_name: str = "", mechanism: str = "",
    hint_text: str = "", limit: int = 3,
) -> list[ReferenceHit]:
    """Approved reference scripts for the product, mechanism-matched first
    (the reference that actually uses the chosen mechanism is the most
    relevant language AND creative example), then direction-matched, then a
    stable fallback so a story with no matching reference still gets real
    writing examples rather than none."""
    ids = _resolve_product_ids(db, product_id, product_name)
    if not ids:
        return []
    rows = (
        db.query(ProductReferenceScript)
        .filter(ProductReferenceScript.product_id.in_(ids), ProductReferenceScript.is_approved.is_(True))
        .all()
    )
    seen: set[str] = set()
    hits: list[ReferenceHit] = []
    for r in sorted(rows, key=lambda r: (r.reference_key or "~", str(r.created_at))):
        key = r.reference_key or r.id
        if key in seen:  # duplicate product rows carry identical copies
            continue
        seen.add(key)
        hits.append(ReferenceHit(reference_key=key, title=r.title or "", direction=r.creative_direction or "",
                                 mechanism=r.creative_mechanism or "", text=r.script_text))
    hits.sort(key=lambda h: (-_score(h, mechanism, hint_text), not h.mechanism, h.reference_key))
    return hits[:limit]


def retrieve_for_generation(
    *, product_id: str = "", product_name: str = "", mechanism: str = "", hint_text: str = "", limit: int = 3,
) -> list[ReferenceHit]:
    """Pipeline-facing entry point (opens its own session, same convention
    as creative_memory_service). Never raises — retrieval trouble must
    degrade to "no references", never fail script generation. If the product
    is Herbal Masala but the table has nothing for it yet (e.g. the product
    was created after startup), it self-heals by importing first."""
    try:
        with SessionLocal() as db:
            hits = select_reference_scripts(db, product_id=product_id, product_name=product_name,
                                            mechanism=mechanism, hint_text=hint_text, limit=limit)
            if not hits:
                targets = [p for p in db.query(AyushProduct).filter(AyushProduct.id == product_id).all()] if product_id else []
                targets += [p for p in _herbal_masala_products(db) if is_herbal_masala_name(product_name) and p not in targets]
                targets = [p for p in targets if is_herbal_masala_name(p.name)]
                if targets:
                    import_calender_references(db, products=targets)
                    hits = select_reference_scripts(db, product_id=product_id, product_name=product_name,
                                                    mechanism=mechanism, hint_text=hint_text, limit=limit)
            return hits
    except Exception as e:
        logger.warning("[REFERENCE_DNA] retrieval failed, continuing without reference scripts: %s", e)
        return []


# --- language DNA + prompt formatting ---------------------------------------

_LABEL_LINE = re.compile(r"^\s*(visual|scene|hook|duration|text on screen|voiceover|vo)\b[^:]*:?\s*$", re.IGNORECASE)


def _spoken_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for line in text.splitlines():
        line = re.sub(r"^\s*(voiceover|vo|hook\s*\d*|visual[^:]*|dialogue)\s*:-?\s*", "", line, flags=re.IGNORECASE)
        if not line.strip() or _LABEL_LINE.match(line) or re.match(r"^\s*(scene|script|duration)\b", line, re.IGNORECASE):
            continue
        for piece in re.split(r"(?<=[.?!…])\s+|\n", line):
            if len(piece.split()) >= 2:
                sentences.append(piece.strip())
    return sentences


def language_dna_summary(text: str, dna_language_style: str = "") -> str:
    """Measured (not guessed) language DNA of one reference, plus the
    hand-recorded language_style from creative_reference_dna when present."""
    sentences = _spoken_sentences(text)
    parts: list[str] = []
    if sentences:
        lengths = [len(s.split()) for s in sentences]
        parts.append(f"about {sum(lengths) / len(lengths):.0f} words per spoken sentence (range {min(lengths)}-{max(lengths)})")
    questions = text.count("?")
    if questions:
        parts.append(f"{questions} direct question(s) to the viewer")
    ellipses = text.count("…") + text.count("...")
    if ellipses:
        parts.append(f"{ellipses} trailing-off pause(s) (…) used as spoken rhythm")
    parts.append("Devanagari Hindi" if re.search("[ऀ-ॿ]", text) else "Roman-script Hinglish")
    if re.search(r"₹\s?\d", text):
        parts.append("states concrete numbers plainly (₹ amounts)")
    line = "Language DNA (measured): " + "; ".join(parts)
    if dna_language_style:
        line += f". Recorded style: {dna_language_style}"
    return line + "."


def _dna_record(reference_key: str):
    return next((r for r in creative_reference_dna.REFERENCE_RECORDS if r.video_id == reference_key), None)


def format_reference_excerpt(hit: ReferenceHit) -> str:
    """One reference as a labeled excerpt: creative DNA, measured language
    DNA, then the FULL original text (never truncated — the writer needs
    real sentence construction to learn from)."""
    rec = _dna_record(hit.reference_key)
    head = f"[{hit.reference_key}] Direction: {hit.direction or 'n/a'}; mechanism: {hit.mechanism or 'n/a'}"
    lines = [head]
    if rec is not None:
        lines.append(f"Creative DNA — hook device: {rec.hook_device}; payoff: {rec.payoff}")
    lines.append(language_dna_summary(hit.text, rec.language_style if rec is not None else ""))
    lines.append("Reference text (study, do not copy):")
    lines.append(hit.text)
    return "\n".join(lines)


def format_reference_block(hits: list[ReferenceHit]) -> str:
    if not hits:
        return ""
    body = "\n".join(f'  """{format_reference_excerpt(h)}"""' for h in hits)
    return f"{REFERENCE_PROMPT_HEADER}\n{body}"

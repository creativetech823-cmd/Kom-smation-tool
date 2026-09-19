"""Repeatable/idempotent import of the real AayushWellness reference scripts
from "Calender Video August.docx" into product_reference_scripts.

Usage (from backend/):  python scripts/import_reference_scripts.py [path/to/doc.docx]
Safe to run any number of times — keyed by (product_id, reference_key)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base, SessionLocal, engine, run_lightweight_migrations  # noqa: E402
from app.services import reference_script_service  # noqa: E402


def main() -> None:
    Base.metadata.create_all(bind=engine)
    run_lightweight_migrations()
    path = sys.argv[1] if len(sys.argv) > 1 else None
    with SessionLocal() as db:
        result = reference_script_service.import_calender_references(db, path)
    print(
        f"references_in_document={result.references_in_document} products_matched={result.products_matched} "
        f"created={result.created} updated={result.updated} unchanged={result.unchanged}"
    )


if __name__ == "__main__":
    main()

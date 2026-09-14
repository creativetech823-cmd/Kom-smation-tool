from collections.abc import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = "sqlite:///./content_factory.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_lightweight_migrations() -> None:
    """`Base.metadata.create_all` only creates missing tables, never alters
    existing ones — so a column added to a model after the SQLite file
    already exists needs a manual, idempotent `ALTER TABLE`. No Alembic in
    this project, so this stays a small explicit list rather than a real
    migration framework."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if "projects" in table_names:
        existing_columns = {col["name"] for col in inspector.get_columns("projects")}
        statements = {
            "pipeline_state": "ALTER TABLE projects ADD COLUMN pipeline_state TEXT",
            "pipeline_stage": "ALTER TABLE projects ADD COLUMN pipeline_stage VARCHAR(40)",
        }
        with engine.begin() as conn:
            for column, statement in statements.items():
                if column not in existing_columns:
                    conn.execute(text(statement))

    # hooks.product_id was added after the AyushWellness Product Library
    # feature shipped — existing DBs (and fresh ones created before
    # ayush_products.create_all runs) may already have a "hooks" table
    # without it. Nullable, so pre-existing hook rows are unaffected.
    if "hooks" in table_names:
        existing_hook_columns = {col["name"] for col in inspector.get_columns("hooks")}
        if "product_id" not in existing_hook_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE hooks ADD COLUMN product_id VARCHAR(32)"))

    # ayush_products / product_assets gained a batch of new columns (basic
    # info extras, brand/creative-direction fields, and reference-material
    # metadata) after those tables already existed in dev DBs.
    if "ayush_products" in table_names:
        existing_product_columns = {col["name"] for col in inspector.get_columns("ayush_products")}
        product_statements = {
            "display_name": "ALTER TABLE ayush_products ADD COLUMN display_name VARCHAR(300)",
            "subcategory": "ALTER TABLE ayush_products ADD COLUMN subcategory VARCHAR(200)",
            "brand": "ALTER TABLE ayush_products ADD COLUMN brand VARCHAR(200)",
            "sku": "ALTER TABLE ayush_products ADD COLUMN sku VARCHAR(100)",
            "marketplace_urls": "ALTER TABLE ayush_products ADD COLUMN marketplace_urls TEXT",
            "landing_page_url": "ALTER TABLE ayush_products ADD COLUMN landing_page_url VARCHAR(500)",
            "never_say": "ALTER TABLE ayush_products ADD COLUMN never_say TEXT",
            "secondary_target_audience": "ALTER TABLE ayush_products ADD COLUMN secondary_target_audience TEXT",
            "customer_objections": "ALTER TABLE ayush_products ADD COLUMN customer_objections TEXT",
            "buying_triggers": "ALTER TABLE ayush_products ADD COLUMN buying_triggers TEXT",
            "awareness_level": "ALTER TABLE ayush_products ADD COLUMN awareness_level VARCHAR(200)",
            "brand_personality": "ALTER TABLE ayush_products ADD COLUMN brand_personality TEXT",
            "words_to_use": "ALTER TABLE ayush_products ADD COLUMN words_to_use TEXT",
            "words_to_avoid": "ALTER TABLE ayush_products ADD COLUMN words_to_avoid TEXT",
            "visual_style": "ALTER TABLE ayush_products ADD COLUMN visual_style TEXT",
            "visual_exclusions": "ALTER TABLE ayush_products ADD COLUMN visual_exclusions TEXT",
        }
        with engine.begin() as conn:
            for column, statement in product_statements.items():
                if column not in existing_product_columns:
                    conn.execute(text(statement))

    if "product_assets" in table_names:
        asset_columns = inspector.get_columns("product_assets")
        existing_asset_columns = {col["name"] for col in asset_columns}
        asset_statements = {
            "source_url": "ALTER TABLE product_assets ADD COLUMN source_url VARCHAR(1000)",
            "learning_notes": "ALTER TABLE product_assets ADD COLUMN learning_notes TEXT",
            "style_notes": "ALTER TABLE product_assets ADD COLUMN style_notes TEXT",
        }
        with engine.begin() as conn:
            for column, statement in asset_statements.items():
                if column not in existing_asset_columns:
                    conn.execute(text(statement))

        # file_path was originally NOT NULL — a URL-only reference asset
        # (advertisement/reference_video with no uploaded file) needs it
        # nullable. SQLite can't drop a NOT NULL constraint with a plain
        # ALTER TABLE, so rebuild the table the standard SQLite way: rename,
        # let create_all's schema define the new (already-nullable) table,
        # copy rows across, drop the old one. Only runs once — a no-op on a
        # fresh DB where the table was already created nullable.
        file_path_col = next((c for c in asset_columns if c["name"] == "file_path"), None)
        if file_path_col is not None and file_path_col.get("nullable") is False:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE product_assets RENAME TO product_assets_old"))
            Base.metadata.tables["product_assets"].create(bind=engine)
            shared_columns = ", ".join(
                col["name"] for col in asset_columns if col["name"] != "file_path"
            ) + ", file_path"
            with engine.begin() as conn:
                conn.execute(
                    text(
                        f"INSERT INTO product_assets ({shared_columns}) "
                        f"SELECT {shared_columns} FROM product_assets_old"
                    )
                )
                conn.execute(text("DROP TABLE product_assets_old"))

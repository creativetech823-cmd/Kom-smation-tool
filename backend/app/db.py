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
    if "projects" not in inspector.get_table_names():
        return
    existing_columns = {col["name"] for col in inspector.get_columns("projects")}
    statements = {
        "pipeline_state": "ALTER TABLE projects ADD COLUMN pipeline_state TEXT",
        "pipeline_stage": "ALTER TABLE projects ADD COLUMN pipeline_stage VARCHAR(40)",
    }
    with engine.begin() as conn:
        for column, statement in statements.items():
            if column not in existing_columns:
                conn.execute(text(statement))

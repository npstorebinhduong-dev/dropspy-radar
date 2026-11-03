"""Apply reviewed migrations. PostgreSQL lock serializes simultaneous API startup."""

from pathlib import Path
from alembic import command
from alembic.config import Config
from .db import engine


def upgrade_database(target="head", connection=None):
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    if connection is not None:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, target)
        return
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            from sqlalchemy import text

            conn.execute(text("SELECT pg_advisory_xact_lock(801204021)"))
        upgrade_database(target, conn)


if __name__ == "__main__":
    upgrade_database()

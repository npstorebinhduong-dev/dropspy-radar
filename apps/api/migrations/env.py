from alembic import context
from sqlalchemy import engine_from_config, pool
from app.db import Base, DATABASE_URL
import app.models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
connection = config.attributes.get("connection")


def migrate(conn):
    context.configure(connection=conn, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if connection is not None:
    migrate(connection)
else:
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as conn:
        migrate(conn)

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, engine_from_config, pool

# Import our database base metadata
from resultarai.adapters.persistence_postgres.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata to our SQLAlchemy models base metadata
target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from environment or configuration."""
    return os.environ.get(
        "DATABASE_URL",
        config.get_main_option(
            "sqlalchemy.url", "postgresql+psycopg://postgres:postgres@localhost:5432/resultarai_dev"
        ),
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    url = get_url()

    # Use create_engine if DATABASE_URL is set,
    # otherwise fall back to engine_from_config.
    if "DATABASE_URL" in os.environ:
        connectable = create_engine(url, poolclass=pool.NullPool)
    else:
        # Fall back to engine_from_config, but override the url in the config dict
        cfg_section = config.get_section(config.config_ini_section, {})
        cfg_section["sqlalchemy.url"] = url
        connectable = engine_from_config(
            cfg_section,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

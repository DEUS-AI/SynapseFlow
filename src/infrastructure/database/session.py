"""Database Session Management.

Provides async database session handling using SQLAlchemy.
"""

import logging
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)

from .config import DatabaseConfig, default_config
from .models import Base

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


async def init_database(
    config: Optional[DatabaseConfig] = None,
    create_tables: bool = False
) -> AsyncEngine:
    """Initialize the database connection.

    Args:
        config: Database configuration (uses default if not provided)
        create_tables: Whether to create tables if they don't exist

    Returns:
        Async SQLAlchemy engine
    """
    global _engine, _session_factory

    if _engine is not None:
        logger.warning("Database already initialized, returning existing engine")
        return _engine

    config = config or default_config

    logger.info(f"Initializing database connection to {config.host}:{config.port}/{config.database}")

    _engine = create_async_engine(
        config.get_url(async_driver=True),
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_timeout=config.pool_timeout,
        pool_recycle=config.pool_recycle,
        echo=config.echo,
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    if create_tables:
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created")

    logger.info("Database connection initialized successfully")
    return _engine


async def close_database() -> None:
    """Close the database connection."""
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connection closed")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session.

    Yields:
        Async database session

    Usage:
        async for session in get_db_session():
            result = await session.execute(...)
    """
    global _session_factory

    if _session_factory is None:
        await init_database()

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions.

    Usage:
        async with db_session() as session:
            result = await session.execute(...)
    """
    global _session_factory

    if _session_factory is None:
        await init_database()

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_engine() -> Optional[AsyncEngine]:
    """Get the current database engine."""
    return _engine


def is_initialized() -> bool:
    """Check if database is initialized."""
    return _engine is not None

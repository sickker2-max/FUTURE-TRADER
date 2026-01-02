"""
SQLAlchemy Database Connection and Session Management

This module provides database configuration, engine initialization, and session
management for the FUTURE-TRADER application.
"""

from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./future_trader.db"  # Default to SQLite for development
)

# SQLAlchemy engine configuration
engine = create_engine(
    DATABASE_URL,
    # SQLite-specific settings
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    poolclass=StaticPool if "sqlite" in DATABASE_URL else None,
    echo=os.getenv("SQL_ECHO", "False").lower() == "true",  # Log SQL statements
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# Database base for ORM models
from sqlalchemy.orm import declarative_base

Base = declarative_base()


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign keys for SQLite databases."""
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection function for database sessions.
    
    Yields:
        Session: SQLAlchemy database session
        
    Example:
        @app.get("/items/")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize the database by creating all tables defined in models.
    
    This should be called once at application startup.
    """
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """
    Drop all tables in the database.
    
    WARNING: This is destructive and should only be used in development.
    """
    Base.metadata.drop_all(bind=engine)


class DatabaseSession:
    """
    Context manager for database sessions.
    
    Usage:
        with DatabaseSession() as db:
            user = db.query(User).filter(User.id == 1).first()
    """
    
    def __init__(self):
        self.db = None
    
    def __enter__(self) -> Session:
        self.db = SessionLocal()
        return self.db
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()
        return False

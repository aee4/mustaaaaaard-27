from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    pool_timeout=10,
    pool_size=2,
    max_overflow=0,
    connect_args={
        "connect_timeout": 5,
        "options": "-c statement_timeout=15000 -c lock_timeout=5000 -c idle_in_transaction_session_timeout=15000",
    },
)
SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=Session)

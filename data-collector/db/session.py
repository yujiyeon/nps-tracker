"""SQLAlchemy 세션 팩토리"""
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # 끊어진 커넥션 자동 감지
    pool_size=5,
    max_overflow=10,
)

SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """트랜잭션 범위 세션 컨텍스트 매니저 - 예외 발생 시 자동 롤백"""
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

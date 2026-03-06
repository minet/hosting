"""SQLAlchemy model for per-user quota advisory locks."""

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class QuotaLock(Base):
    """ORM model representing a per-user quota lock row.

    Used to serialize concurrent quota-checking operations for a given user
    via ``SELECT ... FOR UPDATE``.

    :param user_id: The user identifier that serves as the primary key and lock target.
    """

    __tablename__ = "quota_locks"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)

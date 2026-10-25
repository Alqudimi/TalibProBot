from datetime import datetime, timezone
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA_NAME = "student_platform"
metadata_obj = MetaData(schema=SCHEMA_NAME)


class Base(DeclarativeBase):
    metadata = metadata_obj

    def to_dict(self) -> dict:
        """Helper to convert model attributes to a dictionary."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

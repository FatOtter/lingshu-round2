"""SQLAlchemy ORM models for Data module."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lingshu.setting.models import Base


class Connection(Base):
    __tablename__ = "connections"

    rid: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    credentials: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, server_default="disconnected")
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class EditLog(Base):
    """Edit log entries for the write-back pipeline.

    P2 stores these in PostgreSQL; P3 will migrate to FoundationDB.
    """

    __tablename__ = "edit_logs"

    entry_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    type_rid: Mapped[str] = mapped_column(String, nullable=False)
    primary_key_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    operation: Mapped[str] = mapped_column(String, nullable=False)  # create/update/delete
    field_values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    action_type_rid: Mapped[str | None] = mapped_column(String, nullable=True)
    branch: Mapped[str] = mapped_column(String, nullable=False, server_default="main")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_editlog_tenant_type_key", "tenant_id", "type_rid"),
        Index("ix_editlog_tenant_branch", "tenant_id", "branch"),
    )

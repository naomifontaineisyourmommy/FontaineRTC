"""ORM models.

Admin role (ported from OlcRTC-AdminVPS data.db):
    Group, Server
Node role:
    Instance  (the per-user olcrtc config; replaces users.json)

Fields below mirror the originals; expand during migration phases 2/3.
"""

import time

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


# ── admin role ────────────────────────────────────────────────────────────────
class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    servers: Mapped[list["Server"]] = relationship(back_populates="group")


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ip: Mapped[str] = mapped_column(String, nullable=False, unique=True)  # API URL
    api_key: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    added_at: Mapped[float] = mapped_column(Float, default=time.time)

    group: Mapped[Group] = relationship(back_populates="servers")


# ── node role ───────────────────────────────────────────────────────────────--
class Instance(Base):
    """One olcrtc instance (formerly an entry in users.json)."""

    __tablename__ = "instances"
    __table_args__ = (UniqueConstraint("uid"),)

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    key: Mapped[str] = mapped_column(String, nullable=False)
    carrier: Mapped[str] = mapped_column(String, default="jitsi")
    transport: Mapped[str] = mapped_column(String, default="datachannel")
    custom_room_id: Mapped[str] = mapped_column(String, default="")
    auto_restart: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    # Transport params + transient runtime state are added in migration phase 2.

from sqlalchemy import (Table,
                        Sequence,
                        Column,
                        Integer,
                        String,
                        DateTime,
                        Boolean,
                        ForeignKey,
                        Numeric,
                        UniqueConstraint,
                        Date,
                        CheckConstraint,
                        ForeignKeyConstraint,
                        Index)
from sqlalchemy.schema import Identity
from sqlalchemy.dialects.postgresql import JSONB

from ..models import metadata, users, sites, users_projects, projects



slides = Table("slides", metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("name", String, unique=True, nullable=False, info={"log": True}),
    Column("project_id", Integer, ForeignKey("projects.id"), nullable=False, info={"log": True}),
    Column("collection_id", Integer, ForeignKey("collections.id"), nullable=True),
    Column("directory_name", String, nullable=False),
    Column("user_directory_timestamp", String, unique=True, nullable=False), # Prevent the same upload being added more than once
    Column("created_datetime", DateTime(timezone=True), nullable=False),
    Column("attr", JSONB, default={}, nullable=False),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("site_id", Integer, ForeignKey("sites.id"), nullable=False, info={"log": True}),
    Column("status", String, nullable=False, info={"log": True}),
    Column("deleted", Boolean(name="bool"), nullable=False, default=False))

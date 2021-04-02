from datetime import (datetime,
                      timezone)

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

from sqlalchemy.dialects.postgresql import JSONB

from aireal.models import (metadata,
                             users,
                             groups,
                             users_groups,
                             sites,
                             users_sites,
                             users_projects,
                             configurations,
                             projects)



nanoporeruns = Table("nanoporeruns", metadata,
    Column("id", Integer, primary_key=True),
    Column("nanoporeid", String, unique=True, nullable=False),
    Column("num_samples", Integer, nullable=True),
    Column("num_uploaded", Integer, nullable=True),
    Column("attr", JSONB, default={}, nullable=False))



nanoporesamples = Table("nanoporesamples", metadata,
    Column("id", Integer, primary_key=True),
    Column("nanoporeid", String, nullable=False),
    Column("nanoporerun_id", Integer, ForeignKey("nanoporeruns.id"), nullable=False),
    Column("status", String, default="", nullable=False),# ?needed
    Column("project_id", Integer, ForeignKey("projects.id"), nullable=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=True),
    Column("upload_datetime", DateTime(timezone=True), nullable=True),
    Column("attr", JSONB, default={}, nullable=False),
    Column("name", String, nullable=True),
    Column("completed", Boolean(name="bool"), default=False, nullable=False),
    UniqueConstraint("nanoporeid", "nanoporerun_id"))



nanoporefiles = Table("nanoporefiles", metadata,
    Column("id", Integer, primary_key=True),
    Column("nanoporesample_id", Integer, ForeignKey("nanoporesamples.id"), nullable=True),
    Column("filename", String, nullable=False),
    Column("size", Integer, nullable=False),
    Column("identifier", String, nullable=True),
    Column("completed", Boolean(name="bool"), default=False, nullable=False,))



nanoporechunks = Table("nanoporechunks", metadata,
    Column("id", Integer, primary_key=True),
    Column("nanoporefile_id", Integer, ForeignKey("nanoporefiles.id"), nullable=False),
    Column("index", Integer, nullable=False),
    Column("etag", String, nullable=False),
    UniqueConstraint("nanoporefile_id", "index"))







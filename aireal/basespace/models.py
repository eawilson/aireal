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
                             users_projects,
                             configurations,
                             projects)



bsaccounts = Table("bsaccounts", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, unique=True, nullable=False),
    Column("token", String, nullable=False))



users_bsaccounts = Table("users_bsaccounts", metadata,
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("bsaccount_id", Integer, ForeignKey("bsaccounts.id"), nullable=False),
    UniqueConstraint("user_id", "bsaccount_id"))



bsruns = Table("bsruns", metadata,
    Column("id", Integer, primary_key=True),
    Column("bsid", Integer, unique=True, nullable=False),
    Column("attr", JSONB, default={}, nullable=False),
    
    Column("num_total", Integer, nullable=True),
    Column("num_uploaded", Integer, nullable=True))



# Yes this is messey but a single run may be shared between multiple accounts.
bsaccounts_bsruns = Table("bsaccounts_bsruns", metadata,
    Column("bsrun_id", Integer, ForeignKey("bsruns.id"), nullable=False),
    Column("bsaccount_id", Integer, ForeignKey("bsaccounts.id"), nullable=False),
    UniqueConstraint("bsrun_id", "bsaccount_id"))



bsappsessions = Table("bsappsessions", metadata,
    Column("id", Integer, primary_key=True),
    Column("bsid", String, unique=True, nullable=False),
    Column("bsrun_id", Integer, ForeignKey("bsruns.id"), nullable=False),
    Column("attr", JSONB, default={}, nullable=False))



bssamples = Table("bssamples", metadata,
    Column("id", Integer, primary_key=True),
    Column("bsappsession_id", Integer, ForeignKey("bsappsessions.id"), nullable=False),
    Column("name", String, nullable=False),
    Column("reads_pf", Integer, nullable=False),
    Column("status", String, default="", nullable=False),
    Column("project_id", Integer, ForeignKey("projects.id"), nullable=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=True),
    Column("upload_datetime", DateTime(timezone=True), nullable=True))



bsdatasets = Table("bsdatasets", metadata,
    Column("id", Integer, primary_key=True),
    Column("bsid", String, unique=True, nullable=False),
    Column("bssample_id", Integer, ForeignKey("bssamples.id"), nullable=False),
    Column("attr", JSONB, default={}, nullable=False))



bsprojects = Table("bsprojects", metadata,
    Column("id", Integer, primary_key=True),
    Column("bsid", Integer, unique=True, nullable=False),
    Column("attr", JSONB, default={}, nullable=False),
    
    Column("num_total", Integer, nullable=True),
    Column("num_uploaded", Integer, nullable=True))



# Yes this is messey but a single run may be shared between multiple accounts.
bsaccounts_bsprojects = Table("bsaccounts_bsprojects", metadata,
    Column("bsproject_id", Integer, ForeignKey("bsprojects.id"), nullable=False),
    Column("bsaccount_id", Integer, ForeignKey("bsaccounts.id"), nullable=False),
    UniqueConstraint("bsproject_id", "bsaccount_id"))

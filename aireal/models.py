from sqlalchemy import (create_engine,
                        MetaData,
                        Table,
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


conv = {"ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
        }
metadata = MetaData(naming_convention=conv)



users = Table("users", metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("email", String, unique=True, nullable=False, info={"log": True}),
    Column("name", String, nullable=False),
    Column("forename", String, nullable=False, info={"log": True}),
    Column("surname", String, nullable=False, info={"log": True}),
    Column("last_session", JSONB, default={}, nullable=False),
    Column("restricted", Boolean(name="Bool"), nullable=True),
    
    Column("totp_secret", String, nullable=True),
    Column("password", String, nullable=True),
    Column("reset_datetime", String, nullable=True),
    Column("deleted", Boolean(name="bool"), default=False, nullable=False))



groups = Table("groups", metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("name", String, unique=True, nullable=False),
    Column("order", Integer, default=99, nullable=False))



users_groups = Table("users_groups", metadata,
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("group_id", Integer, ForeignKey("groups.id"), nullable=False),
    UniqueConstraint("user_id", "group_id"))



sites = Table("sites", metadata,
    Column("id", Integer, Identity(), primary_key=True, nullable=False),
    Column("name", String, unique=True, nullable=False, info={"log": True}),
    Column("deleted", Boolean(name="bool"), default=False, index=True, nullable=False))



users_sites = Table("users_sites", metadata,
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("site_id", Integer, ForeignKey("sites.id"), nullable=False),
    UniqueConstraint("user_id", "site_id"))



projects = Table("projects", metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("name", String, unique=True, nullable=False),
    Column("deleted", Boolean(name="bool"), default=False, index=True, nullable=False))



users_projects = Table("users_projects", metadata,
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("project_id", Integer, ForeignKey("projects.id"), nullable=False),
    UniqueConstraint("user_id", "project_id"))



logs = Table("logs", metadata,
    Column("id", Integer, Identity(), primary_key=True, nullable=False),
    Column("tablename", String, nullable=False, index=True),
    Column("row_id", Integer, nullable=False, index=True),
    Column("action", String, nullable=False),
    Column("details", String, nullable=False),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=True),
    Column("ip_address", String, nullable=True),
    Column("datetime", DateTime(timezone=True), nullable=False))



projects = Table("projects", metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("name", String, unique=True, nullable=False, info={"log": True}),
    Column("subject_attr", JSONB, default={}, nullable=False),
    Column("collection_attr", JSONB, default={}, nullable=False),
    Column("pipeline_id", Integer, ForeignKey("pipelines.id"),
                                  nullable=True),
    Column("default_pipeline_options", JSONB, default={}, nullable=False),
    Column("deleted", Boolean(name="bool"), nullable=False, default=False),
    extend_existing=True)



subjects = Table("subjects", metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("name", String, nullable=False),
    Column("project_id", Integer, ForeignKey("projects.id"), nullable=False),
    Column("attr", JSONB, default={}, nullable=False),
    Column("deleted", Boolean(name="bool"), nullable=False, default=False),
    UniqueConstraint("project_id", "name"))



collections = Table("collections", metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("subject_id", Integer, ForeignKey("subjects.id"), nullable=True),
    Column("collection_datetime", DateTime(timezone=True), nullable=True),
    Column("received_datetime", DateTime(timezone=True), nullable=True),
    Column("attr", JSONB, default={}, nullable=False),
    Column("deleted", Boolean(name="bool"), nullable=False, default=False))



samples = Table("samples", metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("collection_id", Integer, ForeignKey("collections.id"), nullable=False),
    Column("parent_id", Integer, ForeignKey("subjects.id"), nullable=True),
    Column("project_id", Integer, ForeignKey("projects.id"), nullable=False),
    Column("material_id", Integer, ForeignKey("materials.id"), nullable=False),
    Column("creation_datetime", DateTime(timezone=True), nullable=False),
    Column("attr", JSONB, default={}, nullable=False),
    Column("deleted", Boolean(name="bool"), nullable=False, default=False))



samples = Table("materials", metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("name", String, nullable=False))



analyses = Table("analyses", metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("pipeline_id", Integer, ForeignKey("pipelines.id"),
                          nullable=True),
    Column("sequencing_id", Integer, ForeignKey("sequencings.id"),
                            nullable=True),
    Column("application", String, nullable=True),
    Column("version", String, nullable=True),
    Column("command_line", String, nullable=False),
    Column("log", String, nullable=False),######################################
    Column("status", String, nullable=False),########################### ??????
    Column("attr", JSONB, default={}, nullable=False),
    Column("deleted", Boolean(name="bool"), nullable=False, default=False))



files = Table("files", metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("name", String, unique=True, nullable=False),
    Column("collection_id", Integer, ForeignKey("collections.id"),
                            nullable=False),
    Column("analysis_id", Integer, ForeignKey("analyses.id"), nullable=True),
    Column("type", String, nullable=False),
    Column("extension", String, nullable=False),
    Column("creation_datetime", DateTime(timezone=True), nullable=False),
    Column("deleted", Boolean(name="bool"), nullable=False, default=False))



diskfiles = Table("diskfiles", metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("file_id", Integer, ForeignKey("files.id"), nullable=False),
    Column("size", Integer, nullable=False),
    Column("aws_bucket", String, nullable=False),
    Column("aws_key", String, nullable=False),
    Column("storage_class", String, nullable=False),
    Column("status", String, nullable=False),
    Column("deleted", Boolean(name="bool"), nullable=False, default=False))



files_analyses = Table("files_analyses", metadata,
    Column("file_id", Integer, ForeignKey("files.id"), nullable=False),
    Column("analysis_id", Integer, ForeignKey("analyses.id"),
                          nullable=False),
    UniqueConstraint("file_id", "analysis_id"))



pipelines = Table("pipelines", metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("name", String, unique=True, nullable=False),
    Column("version", String, nullable=False),
    Column("script", String, nullable=False),
    Column("deleted", Boolean(name="bool"), nullable=False, default=False))



sequencings = Table("sequencings", metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("name", String, unique=True, nullable=False),
    Column("platform", String, nullable=False),
    Column("status", String, nullable=False),
    Column("completion_datetime", String, nullable=False),
    Column("attr", JSONB, default={}, nullable=False))

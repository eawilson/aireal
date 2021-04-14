from aireal import create_app
from aireal.models import metadata
from sqlalchemy.sql.ddl import CreateTable
from sqlalchemy.dialects import postgresql


create_app("/home/ed/Data/aireal_instance")
for table in metadata.sorted_tables:
    print(CreateTable(table).compile(dialect=postgresql.dialect()))


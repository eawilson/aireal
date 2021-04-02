from logging import Handler
from datetime import datetime, now
from sqlalchemy import create_engine, event, MetaData, Table,Column, Integer, String, DateTime, select, and_
from flask import has_request_context, current_app, request, session

_engines = {}

def engine():
    db_url = current_app().config["LOG_URL"]
    try:
        return _engines[db_url]
    except KeyError:
        engine = create_engine(db_url)
        metadata.create_all()
        _engines[db_url] = engine
        return engine


convention = {"ix": "ix_%(column_0_label)s",
              "uq": "uq_%(table_name)s_%(column_0_name)s",
              "ck": "ck_%(table_name)s_%(constraint_name)s",
              "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
              "pk": "pk_%(table_name)s"
             }

metadata = MetaData(naming_convention=convention)


dblog = Table("dblog", metadata,
    Column("id", Integer, primary_key=True),
    Column("logger", String, nullable=False),
    Column("level", String, nullable=False),
    Column("level_numeric", Integer, nullable=False),
    Column("datetime", DateTime, default=now, nullable=False),
    Column("user_id", Integer),
    Column("user_agent", String),
    Column("remote_addr", String),
    Column("path", String),
    Column("method", String),
    Column("args", String),
    Column("form", String),
    Column("sql", String),
    Column("paramaters", String),
    Column("message", String))




class DatabaseHandler(Handler):
    
    def emit(record):
        values = {"logger": record.name,
                  "level": record.levelname,
                  "level_numeric": record.level,
                  "message": record.getMessage(),
                 }
        
        if has_request_context():
            values["user_id"] = session["user_id"]
            values["user_agent"] = request.user_agent
            values["remote_addr"] = request.remote_addr
            values["path"] = request.path
            values["method"] = request.method
            values["args"] = repr(request.args.to_dict())
            values["form"] = repr(request.form.to_dict())

        if 
        
        
        
        with engine().connect() as conn:
        
        
        
        
        try:
            msg = self.format(record)
            stream = self.stream
            # issue 35046: merged two stream.writes into one.
            stream.write(msg + self.terminator)
            self.flush()

        except Exception:
            self.handleError(record)



root_logger = logging.getLogger()
root_logger.addHandler(DatabaseHandler())





















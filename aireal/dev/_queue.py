import time
from datetime import datetime, timedelta, now
from ast import literal_eval

from sqlalchemy import create_engine, event, MetaData, Table,Column, Integer, String, DateTime, select, and_
from flask import current_app


convention = {"ix": "ix_%(column_0_label)s",
              "uq": "uq_%(table_name)s_%(column_0_name)s",
              "ck": "ck_%(table_name)s_%(constraint_name)s",
              "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
              "pk": "pk_%(table_name)s"
             }

metadata = MetaData(naming_convention=convention)

jobs = Table("jobs", metadata,
    Column("id", Integer, primary_key=True),
    Column("function", String, nullable=False),
    Column("args", String, nullable=False),
    Column("kwargs", String, nullable=False),
    Column("datetime_created", DateTime, default=now, nullable=False),
    Column("datetime_ready", DateTime, nullable=False))



outcomes = Table("outcomes", metadata,
    Column("id", Integer, primary_key=True),
    Column("job_id", Integer, ForeignKey("jobs.id"), nullable=False),
    Column("datetime_executed", DateTime, default=now, nullable=False),
    Column("message", String, default="", nullable=False),
    Column("complete", Boolean, default=True, nullable=False))



#config = Config()
#config.from_envvar("INTEGRATED_CONFIG")
#queue_url = config.get("QUEUE_URL", None)

if queue_url:
    engine = create_engine(queue_url)

    @event.listens_for(engine, "connect")
    def do_connect(dbapi_connection, connection_record):
        # disable pysqlite's emitting of the BEGIN statement entirely.
        # also stops it from emitting COMMIT before any DDL.
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def do_begin(conn):
        # emit our own BEGIN
        conn.execute("BEGIN")

    metadata.create_all(engine)

    functions = {}

    def asynchronous(minutes=0):
        def queue_decorator(function):
            name = function.__name__
            assert name not in functions
            functions[name] = function
            
            @wraps(function)
            def wrapper(*args, **kwargs):
                with engine.connect() as conn:
                    conn.execute(jobs.insert().values(function=name, args=repr(args), kwargs=repr(kwargs), datetime_ready=now()+timedelta(minutes=minutes)))
            return wrapper
        return queue_decorator



    def execute_next_job():
        with engine.connect() as conn:
            sql = select([jobs.c.id, jobs.c.function, jobs.c.args, jobs.c.kwargs]). \
                    select_from(join(jobs, outcomes, and_(jobs.c.id == outcomes.c.job_id, outcomes.c.complete == True), isouter=True)). \
                    where(and_(jobs.c.datetime_ready > now(), jobs.c.complete == None)). \
                    order_by(jobs.c.datetime_ready)
            row = list(conn.execute(sql).first() or ())
            
        if row:
            try:
                functions[row[jobs.c.function]](*literal_eval(row[jobs.c.args]), **literal_eval(row[jobs.c.kwargs]))
                with engine.connect() as conn:
                    conn.execute(outcomes.insert())
            except Exception as e:
                message = str(e)
                num_failures = len(conn.execute(select([outcomes.c.id]).where(outcomes.c.job_id == row[jobs.c.id])))
                if numfailures >= 6:
                    delay = timedelta(days=1)
                elif num_failures >= 3:
                    delay = timedelta(hours=1)
                else:
                    delay = timedelta(minutes=5)
                with engine.begin() as conn:
                    conn.execute(outcomes.insert().values(message=message, complete=False))
                    conn.execute(jobs.update().where(jobs.c.id == row[jobs.c.id]).values(datetime_ready=now()+delay))
            return True
        


    def pole(seconds=60):
        while True:
            while execute_next_job():
                pass
        
            time.sleep(seconds)
    

    
else:    
    def asynchronous(function):
        return function
    
    
    
    
    
    
    
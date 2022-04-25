import os, pdb

from flask import request
from psychopg2 import DatabaseError

from ..flask import Blueprint
from ...utils import Transaction



app = Blueprint("Automation", __name__)



@app.route("/automation/<string:token>", max_age=7*24*60*60, methods=["POST"])
def automation_callback(token):
    state = request.form["state"]

    if state == "ready":
        sql = """UPDATE task
                 SET status = 'Running',
                     identifier = %(identifier)s,
                     activity = %(activity)s,
                     datetime_started = current_timestamp,
                     datetime_heartbeat = current_timestamp
                 WHERE id = (
                     SELECT id
                     FROM task
                     WHERE status = 'Queued'
                     LIMIT 1
                     FOR UPDATE SKIP LOCKED)
                 RETURNING command;"""                
        activity = "Initialising..."
        
    elif state == "running":
        sql = """UPDATE task SET activity = %(activity)s WHERE identifier = %(identifier)s;"""
        activity = request.form["activity"]
    
    elif state == "terminated": # Spot termination
        sql = """UPDATE task
                 SET identifier = NULL,
                     status = 'Queued',
                     activity = %(activity)s,
                     datetime_started = NULL,
                     datetime_heartbeat = NULL
                 WHERE identifier = %(identifier)s;"""
        activity = ""
    
    elif state == "failed":
        sql = """UPDATE task
                 SET status = (CASE WHEN attempts < 3 THEN 'Queued' ELSE 'Failed' END),
                     identifier = NULL,
                     activity = %(activity)s,
                     datetime_started = (CASE WHEN attempts < 3 THEN NULL ELSE datetime_started END),
                     datetime_heartbeat = (CASE WHEN attempts < 3 THEN NULL ELSE datetime_heartbeat END),
                     datetime_completed = (CASE WHEN attempts < 3 THEN NULL ELSE current_timestamp END)
                 WHERE identifier = %(identifier)s;"""
        activity = ""
    
    elif state == "completed":
        sql = """UPDATE task
                 SET identifier = NULL,
                     status = 'Completed',
                     activity = %(activity)s,
                     datetime_complete = current_timestamp
                 WHERE identifier = %(identifier)s;"""
        activity = ""
    
    
    ret = {}
    with Transaction() as trans:
        with trans.cursor() as cur:
            try:
                cur.execute(sql, {"activity": activity, "identifier": request.form["identifier"]})
                if state == "ready":
                    ret["command"] = cur.fetchone()[0]
            except DatabaseError as e:
                print(e)
    return ret



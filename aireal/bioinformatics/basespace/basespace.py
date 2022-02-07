#!/usr/bin/env python3

import argparse
import os
import re
import glob
import sys
import pdb
from dateutil import parser

import pytz
import requests
from requests.exceptions import HTTPError
import psycopg2
from psycopg2.extensions import register_adapter, ISOLATION_LEVEL_READ_UNCOMMITTED, ISOLATION_LEVEL_READ_COMMITTED, ISOLATION_LEVEL_REPEATABLE_READ, ISOLATION_LEVEL_SERIALIZABLE
from psycopg2.extras import Json


register_adapter(dict, Json)
trim_lane_regex = re.compile("_L[0-9]{3}$")



def iso8601_to_utc(dt_string):
    """ Convert a string in iso8601 format to a datetime with the timezone set
        to UTC.
    """
    dt = parser.isoparse(dt_string)
    return dt.astimezone(pytz.utc)



def bsget(url, token, params={}):
    response = requests.get(url,
                            params=params, 
                            headers={"x-access-token": token},
                            stream=True)
    response.raise_for_status()
    return response.json()
    #except requests.exceptions.RequestException as e:
        #print(e)
        #pdb.set_trace() # need to add proper handling
    #except requests.exceptions.JSONDecodeError as e:
        #print(e)
        #pass



def bsget_runs(bsserver, token, offset=0, limit=10):
    return bsget(f"{bsserver}/v2/search", token, params={"scope": "runs",
                                                         "query": "(experimentname:*)",
                                                         "offset": offset,
                                                         "limit": limit,
                                                         "SortBy": "DateModified",
                                                         "SortDir": "Desc"})



def bsget_run(bsserver, token, bsid):
    return bsget(f"{bsserver}/v2/runs/{bsid}", token)



def bsget_appsessions(bsserver, token, run_bsid, offset=0, limit=10):
    return bsget(f"{bsserver}/v2/appsessions", token, params={"input.runs": run_bsid,
                                                              "offset": offset,
                                                              "limit": limit,
                                                              "SortBy": "DateModified",
                                                              "SortDir": "Desc"})



def bsget_appsession(bsserver, token, bsid):
    appsession_json = bsget(f"{bsserver}/v2/appsessions/{bsid}", token)
    
    datasets = []
    for prop in appsession_json["Properties"]["Items"]:
        if prop["Name"] == "Logs.Tail":
            # Illumina what the f**k are you doing! Nul bytes in a string!!! Really!!!!
            prop["Content"] = prop["Content"].replace("\x00", "").replace("\x01", "")
        
        elif prop["Name"] == "Output.Datasets":
            if prop["ItemsDisplayedCount"] == prop["ItemsTotalCount"]:
                items = prop["DatasetItems"]
            else:
                items = []
                total = prop["ItemsTotalCount"]
                while len(items) < total:
                    response = bsget(f"{bsserver}/v2/appsessions/{bsid}/properties/Output.Datasets/items",
                                      token, params={"offset": len(items), "SortBy": "DateCreated", "SortDir": "Desc"})
                    for item in response["Items"]:
                        items.append(item["Dataset"])
            
            for item in items:
                pdb.set_trace()
                try:
                    dataset = bsget(item["Href"], token)
                except HTTPError as e:
                    if e.response.status_code == 403: # Forbidden
                        continue
                    raise
                print(dataset["Id"])##################################################
                datasets.append(dataset)
            
    return (appsession_json, datasets)




def bsrefresh(db_uri):
    
    with psycopg2.connect(db_uri) as conn:
        sql = """SELECT DISTINCT ON (bsaccount.id) bsaccount.id, bsserver.id, bsserver.url, bsaccount.token, bsrun.datetime_modified, bsappsession.datetime_modified
                 FROM bsaccount
                 JOIN bsserver ON bsaccount.bsserver_id = bsserver.id
                 LEFT OUTER JOIN bsaccount_bsrun ON bsaccount_bsrun.bsaccount_id = bsaccount.id
                 LEFT OUTER JOIN bsrun ON bsrun.id = bsaccount_bsrun.bsrun_id
                 LEFT OUTER JOIN bsappsession ON bsappsession.bsrun_id = bsrun.id
                 ORDER BY bsaccount.id, bsrun.datetime_modified DESC, bsappsession.datetime_modified DESC;"""
        
        conn.set_session(isolation_level=ISOLATION_LEVEL_SERIALIZABLE, readonly=True)
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        conn.rollback()
        conn.set_session(isolation_level=ISOLATION_LEVEL_SERIALIZABLE, readonly=False)
        
        
        for account_id, server_id, server, token, run_lastmodified, appsession_lastmodified in rows:
            modified_runs = []
            offset = 0
            total_count = 1
            while offset < total_count:
                response = bsget_runs(server, token, offset=offset)
                paging = response["Paging"]
                total_count = paging["TotalCount"]
                offset = paging["Offset"] + paging["DisplayedCount"]
                for item in response["Items"]:
                    item = item["Run"]
                    datetime_modified = iso8601_to_utc(item["DateModified"])
                    if run_lastmodified is not None and datetime_modified <= run_lastmodified:
                        offset = total_count
                        break
                    modified_runs.append(item)
            
            modified_runs.reverse()
            for run_json in modified_runs:
                #try:
                    ## this actually returns less information than the experimentname elastic search!
                    #run_json = bsget_run(server, token, run_bsid)
                #except HTTPError as e:
                    #if e.response.status_code == 403: # Forbidden
                        #continue
                    #raise
                
                modified_appsessions = []
                offset = 0
                total_count = 1
                while offset < total_count:
                    response = bsget_appsessions(server, token, run_json["Id"], offset=offset)
                    paging = response["Paging"]
                    total_count = paging["TotalCount"]
                    offset = paging["Offset"] + paging["DisplayedCount"]
                    for item in response["Items"]:
                        datetime_modified = iso8601_to_utc(item["DateModified"])
                        if appsession_lastmodified is not None and datetime_modified <= appsession_lastmodified:
                            offset = total_count
                            break
                        modified_appsessions.append(item["Id"])
                
                modified_appsessions = [bsget_appsession(server, token, bsid) for bsid in modified_appsessions]
                if not modified_appsessions:
                    continue###############################
                
                with conn.cursor() as cur:
                    sql = """INSERT INTO bsrun (bsserver_id, bsid, attr, summary, datetime_modified)
                             VALUES (%(bsserver_id)s, %(bsid)s, %(attr)s, %(summary)s, %(datetime_modified)s)
                             ON CONFLICT ON CONSTRAINT uq_bsrun_bsid_bsserver_id
                             DO UPDATE SET attr = %(attr)s, summary = %(summary)s, datetime_modified = %(datetime_modified)s
                             WHERE bsrun.datetime_modified < %(datetime_modified)s
                             RETURNING id;"""
                    seqstats = run_json["SequencingStats"]
                    summary = {"ExperimentName": run_json["ExperimentName"],
                               "Status": run_json["Status"],
                               "InstrumentType": run_json["InstrumentType"],
                               "InstrumentName": run_json["InstrumentName"],
                               "PercentGtQ30": seqstats["PercentGtQ30"],
                               "PercentPf": seqstats["PercentPf"],
                               "ClusterDensity": seqstats["ClusterDensity"],
                               "DateCreated": run_json["DateCreated"]}
                    values = {"bsserver_id": server_id,
                              "bsid": run_json["Id"],
                              "attr": run_json,
                              "summary": summary,
                              "datetime_modified": iso8601_to_utc(item["DateModified"])}
                    cur.execute(sql, values)
                    result = cur.fetchone()
                    if result is None:
                        continue
                    run_id = result[0]
                    
                    sql = """INSERT INTO bsaccount_bsrun (bsaccount_id, bsrun_id)
                             VALUES (%(bsaccount_id)s, %(bsrun_id)s)
                             ON CONFLICT DO NOTHING;"""
                    values = {"bsaccount_id": account_id,
                              "bsrun_id": run_id}
                    cur.execute(sql, values)
                    
                    for appsession_json, datasets in modified_appsessions:
                        sql = """INSERT INTO bsappsession (bsserver_id, bsrun_id, bsid, attr, summary, datetime_modified)
                                 VALUES (%(bsserver_id)s, %(bsrun_id)s, %(bsid)s, %(attr)s, %(summary)s, %(datetime_modified)s)
                                 ON CONFLICT ON CONSTRAINT uq_bsappsession_bsid_bsserver_id
                                 DO UPDATE SET attr = %(attr)s, summary = %(summary)s, datetime_modified = %(datetime_modified)s
                                 WHERE bsappsession.datetime_modified < %(datetime_modified)s
                                 RETURNING id;"""
                        summary = {"ExecutionStatus": appsession_json["ExecutionStatus"],
                                   "Name": appsession_json["Application"]["Name"],
                                   "TotalSize": appsession_json["TotalSize"]}
                        values = {"bsserver_id": server_id,
                                  "bsrun_id": run_id,
                                  "bsid": appsession_json["Id"],
                                  "attr": appsession_json,
                                  "summary": summary,
                                  "datetime_modified": iso8601_to_utc(appsession_json["DateModified"])}
                        cur.execute(sql, values)
                        result = cur.fetchone()
                        if result is None:
                            continue
                        appsession_id = result[0]
                        
                        pdb.set_trace()
                        values = []
                        for dataset_json in datasets:
                            name = dataset_json["Name"]
                            if not trim_lane_regex.search(name):
                                # If name doe not have a lane suffix then assume it is a composite dataset containing the combined datasets
                                # for each of the individual dataset from each lane. WARNING - This assumption may not be future proof but
                                # I can see no other way of doing it other than for checking for unique names or etags within the files
                                # and this would significantly increase the number of api calls and reduce responsivness.
                                continue
                            
                            lane = int(name[-3:])
                            name = name[:-5]
                            summary = {}
                            values.append({"bsserver_id": server_id,
                                           "bsappsession_id": appsession_id,
                                           "bsid": str(dataset_json["Id"]),
                                           "name": name,
                                           "attr": dataset_json,
                                           "summary": summary,
                                           "lane": lane,
                                           "datetime_modified": iso8601_to_utc(dataset_json["DateModified"])})
                        
                        sql = """INSERT INTO bsdataset (bsserver_id, bsappsession_id, bsid, name, attr, summary, lane, datetime_modified)
                                VALUES (%(bsserver_id)s, %(bsappsession_id)s, %(bsid)s, %(name)s, %(attr)s, %(summary)s, %(lane)s, %(datetime_modified)s)
                                ON CONFLICT ON CONSTRAINT uq_bsdataset_bsid_bsserver_id
                                DO UPDATE SET attr = %(attr)%, summary = %(summary)s, datetime_modified = %(datetime_modified)s
                                WHERE datetime_modified < %(datetime_modified)s;"""
                        psycopg2.extras.execute_batch(cur, sql, values)
                conn.commit()
    conn.close()



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", help="path to instance folder containing the config file with database connection uri.", default=".")    
    args = parser.parse_args()
    
    config_files = glob.glob(os.path.join(args.path, "*.cfg"))
    if len(config_files) == 0:
        sys.exit(f"no configuration file found in {args.path}")
    elif len(config_files) > 1:
        sys.exit(f"multiple configuration files found in {args.path}")
    config_path = config_files[0]
    config_file = os.path.basename(config_path)
    
    config = {}
    with open(config_path, mode="rb") as f_in:
        exec(compile(f_in.read(), config_file, "exec"), config)
    
    if "DB_URI" not in config:
        sys.exit(f"no DB_URI found in {config_file}")
    
    bsrefresh(config["DB_URI"])
    
    
    
if __name__ == "__main__":
    main()

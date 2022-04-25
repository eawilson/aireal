#!/usr/bin/env python3

import sys
Z
from datetime import datetime, timedelta, timezone
from time import sleep
from contextlib import closing

import boto3
from botocore.exceptions import ClientError

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_READ_UNCOMMITTED, ISOLATION_LEVEL_READ_COMMITTED, ISOLATION_LEVEL_REPEATABLE_READ, ISOLATION_LEVEL_SERIALIZABLE

from aireal.flask import config_file, load_config
from aireal.aws import ec2_metadata

import pdb



def launch_instances(cur, client, config):
    max_instances = 5
    sql = """WITH relevant AS (
                 SELECT type, status, callback
                 FROM task
                 WHERE type = 'Pipeline' AND status IN ('Queued', 'Running')
                 ORDER BY status <> 'Running', datetime_created
                 LIMIT %(max_instances)s)
             SELECT callback
             FROM relevant
             WHERE status = 'Queued';"""
    cur.execute(sql, {"max_instances": max_instances})
    needed_instances = [row[0] for row in cur]
        
    if needed_instances and "AWS_REGION" in config:
        availability_zones = [config["AWS_REGION"] + letter for letter in ("a", "b", "c")]
        response = client.describe_spot_price_history(Filters=[{"Name": "availability-zone", "Values": availability_zones},
                                                               {"Name": "instance-type", "Values": ["c5d.4xlarge"]},
                                                               {"Name": "product-description", "Values": ["Linux/UNIX"]}])
        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            selected_zone = sorted(response["SpotPriceHistory"], key=lambda x: x["SpotPrice"])[0]["AvailabilityZone"]
        else:
            selected_zone = config["AWS_AVAILABILITY_ZONE"]
        
        for callback in needed_instances:
            userdata = f"""#!/usr/bin/env bash
                           sudo -u ubuntu runner --callback {callback} --progress 5 || true
                           sudo shutdown now"""
            response = client.request_spot_instances(InstanceCount=needed_instances,
                                                     LaunchSpecification={"IamInstanceProfile": {"Arn'": "arn:aws:iam::387676495311:instance-profile/Pipeline"},
                                                                          "ImageId": "ami-02e30cc33d1871084",
                                                                          "InstanceType": "c5d.4xlarge",
                                                                          "Placement": {"AvailabilityZone": selected_zone},
                                                                          "SecurityGroupIds": ["sg-03e5bf35ec90c8943"],
                                                                          "UserData": userdata}
                                                     ValidUntil=datetime.now(timezone.utc) + timedelta(minutes=5))



def terminate_instances(cur, client):
        sql = """SELECT identifier 
                 FROM task
                 WHERE status = 'Running' AND datetime_heartbeat < current_timestamp - INTERVAL '11 minutes';"""
        cur.execute(sql)
        hung_instances = [row[0] for row in cur]
        
        sql = """UPDATE task
                 SET status = (CASE WHEN attempts < 3 THEN 'Queued' ELSE 'Failed' END),
                     identifier = NULL,
                     activity = '',
                     datetime_started = (CASE WHEN attempts < 3 THEN NULL ELSE datetime_started END),
                     datetime_heartbeat = (CASE WHEN attempts < 3 THEN NULL ELSE datetime_heartbeat END),
                     datetime_completed = (CASE WHEN attempts < 3 THEN NULL ELSE current_timestamp END)
                 WHERE identifier = %(identifier)s;"""
        for instance_identifier in hung_instances:
            try:
                response = client.describe_instances(InstanceIds=[instance_identifier])
            except ClientError:
                continue
            if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                resevations = response['Reservations']
                if resevations and resevations[0]["Instances"][0]["State"]["Name"] == "running":
                    response = client.terminate_instances(InstanceIds=[instance_identifier])
                    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                        cur.execute(sql, {"identifier": instance_identifier})



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("instance_path", nargs="?", help="path to instance folder containing the config file with database connection uri.", default=".")    
    args = parser.parse_args()
    
    config = load_config(config_file(args.instance_path))
    if "DB_URI" not in config:
        # DB_URI is essential for access to queue
        sys.exit("DB_URI not found within configuration file")
    config.update(ec2_metadata())
    
    while True:
        client = boto3.client("ec2")
        with closing(psycopg2.connect(config["DB_URI"])) as conn:
            conn.set_session(isolation_level=ISOLATION_LEVEL_REPEATABLE_READ, autocommit=True)
            with conn.cursor() as cur:
                launch_instances(cur, client, config)
                terminate_instances(cur, client)
            
        sleep(15 * 60)



if __name__ == "__main__":
    main()

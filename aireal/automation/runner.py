#!/usr/bin/env python3

import os
import sys
import argparse
import pdb
import time
import subprocess
import shlex

import requests

from pipeline import mount_instance_storage, am_i_an_ec2_instance, boto3_client, spot_interuption
from aireal import ec2_metadata



class Cpu(object):
    def __init__(self):
        table = top_table()
        user_i = table[0].index(" USER")
        self.pre_existing_pids = set(row[:user_i].strip() for row in table[1:])
    
    @property
    def usage(self):
        names = set()
        table = top_table()
        pid_stop = table[0].index(" USER")
        cpu_start = table[0].index(" S ", pid_stop) + 3
        cpu_stop = table[0].index("%CPU", cpu_start) + 4
        command_start = table[0].index("COMMAND", cpu_stop)
        for row in table[1:]:
            if row[:pid_stop].strip() not in self.pre_existing_pids:
                name = row[command_start:]
                if name != "top":
                    cpu = float(row[cpu_start:cpu_stop])
                    if cpu > 0:
                        names.add(name)
        return ",".join(sorted(names))



def top_table():
    kwargs = {"shell": True, "stdout": subprocess.PIPE, "universal_newlines": True}
    return subprocess.run(f"top -bn1 -w 512 -u `whoami`", **kwargs).stdout.splitlines()[6:]



def main():
    """
    """
    print("Starting runner...", file=sys.stderr)
    
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--progress", help="Time in minutes between progress reports submitted via callback, 0 (default) means no reports.", type=int, default=0, required=False)
    parser.add_argument("-c", "--callback", help="URL of the callback to be made to get new jobs and report progress on current job.", required=True)
    args = parser.parse_args()
    args.progress = args.progress * 60
    
    i_am_an_ec2_instance = am_i_an_ec2_instance()
    if i_am_an_ec2_instance:
        os.chdir(mount_instance_storage())
    identifier = ec2_metadata().get("AWS_INSTANCE_ID", "<IDENTIFIER>")
    
    cpu = Cpu()
    interuption_base_time = int(time.time())
    while True:
        if any(os.path.isfile(fn) for fn in os.listdir()):
            sys.exit("runner: Working directory not empty")
        
        try:
            response = requests.post(args.callback, {"state": "ready", "identifier": identifier})
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            sys.exit(e)
        
        data = response.json()
        command = data["command"]
        if not command:
            break
        
        print(" ".join(shlex.quote(token) for token in command), file=sys.stderr)
        process_base_time = int(time.time())
        retcode = None
        process = subprocess.Popen(command)
        while retcode is None:
            time.sleep(5)
            retcode = process.poll()
            if retcode is None:
                current_time = time.time()
                
                # Should get a 2 minute warnuing so checking every 55 seconds should allow 2 checks
                if i_am_an_ec2_instance and current_time - interuption_base_time > 55:
                    interuption_base_time = current_time
                    if spot_interuption():
                        requests.post(args.callback, {"state": "terminated", "identifier": identifier})
                        sys.exit("Terminated.")
                
                if args.progress and current_time - process_base_time > args.progress:
                    process_base_time = current_time
                    requests.post(args.callback, {"state": "running", "identifier": identifier, "activity": cpu.usage})
                    
        response = requests.post(args.callback, {"state": "failed" if retcode else "completed", "identifier": identifier})

        for fn in os.listdir():
            if os.path.isfile(fn):
                 os.unlink(fn)

    print("Complete.", file=sys.stderr)



if __name__ == "__main__":
    main()

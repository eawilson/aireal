#!/usr/bin/env python3

import os
import argparse
import uuid
import subprocess
import requests



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--auth-file", help="Path to write authentication url to.", required=True)
    parser.add_argument("-a", "--api-server", help="URL of BaseSpace authentication server.", required=True)
    parser.add_argument("-c", "--callback", help="URL of callback to be made at completion to update database.", required=True)
    parser.add_argument("-s", "--scopes", help="List of scopes to authenticate with.", required=True)
    args = parser.parse_args()
    
    unique_config = str(uuid.uuid4())
    cmd = ["bs", "auth", "--config", unique_config, "--api-server", args.api_server, "--scopes", args.scopes]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
    stdout = process.stdout.readline()
    # Not certain this is ever required but better safe than sorry
    if not stdout.endswith("\n"):
        stdout += "\n"
    with open(args.auth_file, "wt") as f_out:
        f_out.write(stdout)
    
    # bs auth will timeout after 120 seconds so we should not need to set a timeout here
    if process.wait() == 0:
        access_token = ""
        config_path = os.path.join(os.path.expanduser("~"), ".basespace", f"{unique_config}.cfg")
        with open(config_path) as f_in:
            for row in f_in:
                if row.startswith("accessToken = "):
                    access_token = row[14:].strip()
                    break
        if access_token:
            process = subprocess.run(["bs", "whoami", "--config", unique_config, "-f", "csv"], stdout=subprocess.PIPE, universal_newlines=True)
            if process.returncode == 0:
                whoami = (process.stdout + "\n").split("\n")[1].split(",")
                if len(whoami) > 1:
                    response = requests.post(args.callback, data={"name": whoami[0], "bsid": whoami[1], "token": access_token})
                    print(response.request.url)
                    print(response.request.body)
                    print(response.request.headers)
        try:
            os.unlink(config_path)
        except FileNotFoundError:
            pass
    
    else:
        # bs auth may have failed quickly so allow enough time for error message in auth file to be read before deleting it
        sleep(2)
    
    try:
        os.unlink(args.auth_file)
    except FileNotFoundError:
        pass



if __name__ == "__main__":
    main()

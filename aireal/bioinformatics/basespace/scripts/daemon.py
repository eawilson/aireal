import os
import sys
from subprocess import Popen, PIPE, run
from socket import socket
import pdb
import requests
from threading import Thread, get_ident
from aireal.basespace import Session
from aireal import app



def auth(connection):
    config_file = "auth-{}.cfg".format(get_ident())
    config_path = os.path.join(os.path.expanduser("~"), ".basespace", config_file)
    
    process = Popen(["bs", "auth", "--force", "--config", config_file, "--scopes", "READ GLOBAL"], stdout=PIPE, universal_newlines=True)
    output = process.stdout.readline()
    if not output.startswith(b"Please go to this URL to authenticate:"):
        return
    
    
    try:
        self.wfile.write(output[38:])
    except BrokenPipeError:
        process.kill()
        return
    
    if process.wait() != 0:
        return
    
    with open(config_path, "rt") as f:
        for row in f:
            if row.startswith("accessToken = "):
                token = row[14:].strip()
                break
        else:
            return
    
    process = run(["bs", "whoami", "--config", config_file, "-f", "csv"], stdout=PIPE, universal_newlines=True)
    if process.return_code != 0:
        return
    
    user_name = process.stdout.split("\n")[1].split(",")[0]

    os.unlink(config_path)

    requests.post("http://127.0.0.1:5000/basespace/accounts/create",
                    data={"name": name, "token": token, "user_id": user_id})



def main():
    if len(sys.argv) > 1:
        os.chdir(sys.argv[1])
    
    try:
        os.unlink(server_address)
    except OSError:
        if os.path.exists(server_address):
            raise

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(server_address)
    sock.listen(1)
    
    while True:
        connection, client_address = sock.accept()
        connection.settimeout(120)
        thread = Thread(target=auth, args=(connection,))
        thread.start()
    
    
    
if __name__ == "__main__":
    main()
    
    
 

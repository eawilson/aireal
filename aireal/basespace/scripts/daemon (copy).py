import os
import sys
from subprocess import Popen, PIPE
from socketserver import (UnixStreamServer,
                          UnixDatagramServer,
                          StreamRequestHandler,
                          BaseRequestHandler)
import pdb
import requests
from threading import Thread
from aireal.basespace import Session



class AuthHandler(StreamRequestHandler):
    def handle(self):
        user_id = int(self.rfile.readline().strip().decode())
        config_file = "auth-{}.cfg".format(os.getpid())
        process = Popen(["bs", "auth", "--force", "--config", config_file, "--scopes", "READ GLOBAL"], stdout=PIPE)
        output = process.stdout.readline()
        if not output.startswith(b"Please go to this URL to authenticate:"):
            return
            
        try:
            self.wfile.write(output[38:])
        except BrokenPipeError:
            process.kill()
            return
        
        retcode = process.wait()
        if retcode != 0:
            return
        
        config_path = os.path.join(os.path.expanduser("~"),
                                   ".basespace",
                                   config_file)
        with open(config_path, "rt") as f:
            for row in f:
                if row.startswith("accessToken = "):
                    token = row[14:].strip()
                    break
            else:
                return
        os.unlink(config_path)
        
        current_user = Session(token).get_single("users/current")
        name = current_user["Name"]
        requests.post("http://127.0.0.1:5000/basespace/accounts/create",
                      data={"name": name, "token": token, "user_id": user_id})



class UploadHandler(BaseRequestHandler):
    def handle(self):
        pass



def auth_server():
    auth_sock = "auth_sock"
    if os.path.exists(auth_sock):
        os.unlink(auth_sock)

    server = UnixStreamServer(auth_sock, AuthHandler)
    server.serve_forever()


def upload_server():
    upload_sock = "upload_sock"
    if os.path.exists(upload_sock):
        os.unlink(upload_sock)

    server = UnixDatagramServer(upload_sock, UploadHandler)
    server.serve_forever()



def main():
    if len(sys.argv) > 1:
        os.chdir(sys.argv[1])
    if sum(fn.endswith(".cfg") for fn in os.listdir(".")) != 1:
        raise RuntimeError("Not a valid instance directory.")

    auth_thread = Thread(target=auth_server)
    upload_thread = Thread(target=upload_server)
    auth_thread.start()
    upload_thread.start()
    auth_thread.join()
    upload_thread.join()
    
    
    
if __name__ == "__main__":
    main()
    
    
 

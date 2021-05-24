import os
import sys
from subprocess import Popen, PIPE
from socketserver import (UnixStreamServer,
                          StreamRequestHandler)
import pdb

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from aireal.basespace.models import bsaccounts, users_bsaccounts
from aireal.basespace import Session
from aireal import create_app



def AuthHandler(app):
    class AuthHandler(StreamRequestHandler):
        def handle(self):
            user_id = int(self.rfile.readline().strip().decode())
            config_file = "auth-{}.cfg".format(os.getpid())
            process = Popen(["bs", "auth",
                             "--force",
                             "--config", config_file,
                             "--scopes", "READ GLOBAL"], stdout=PIPE)
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
            with app.extensions["engine"].begin() as conn:
                trans = conn.begin_nested()
                sql = bsaccounts.insert().values(name=current_user["Name"],
                                                 token=token)
                try:
                    bsaccount_id = conn.execute(sql).inserted_primary_key[0]
                    trans.commit()
                except IntegrityError:
                    trans.rollback()
                    sql = select([bsaccounts.c.id]). \
                            where(bsaccounts.c.name == current_user["Name"])
                    bsaccount_id = conn.execute(sql).scalar()
                
                trans = conn.begin_nested()
                try:
                    sql = users_bsaccounts.insert(). \
                            values(user_id=user_id, bsaccount_id=bsaccount_id)
                    conn.execute(sql)
                    trans.commit()
                except IntegrityError:
                    trans.rollback()
            
            conn.close()
    return AuthHandler



def main():
    if len(sys.argv) == 1:
        raise RuntimeError("Instance path is a required argument.")
    elif len(sys.argv) > 2:
        raise RuntimeError("Too many arguments.")
    
    app = create_app(sys.argv[1])
    auth_sock = os.path.join(app.instance_path ,"auth_sock")
    if os.path.exists(auth_sock):
        os.unlink(auth_sock)

    server = UnixStreamServer(auth_sock, AuthHandler(app))
    server.serve_forever()
    
    
    
if __name__ == "__main__":
    main()
    
    
 

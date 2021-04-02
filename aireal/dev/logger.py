import logging
from flask import has_request_context, current_app, request, session
    
    
    
def getLogger(name=""):
    name = "{}.{}".format(current_app.config["NAME"], name or "")
    return logging.getLogger(name)



class ContextFilter(logging.Filter):
    
    def filter(self, record):
        if has_request_context():
            record.user_id = session["user_id"]
            record.user_agent = request.user_agent
            record.remote_addr = request.remote_addr
            record.path = request.path
            record.method = request.method
            record.args = repr(request.args.to_dict())
            record.form = repr(request.form.to_dict())
        else:
            record.user_id = None
            record.user_agent = None
            record.remote_addr = None
            record.path = None
            record.method = None
            record.args = None
            record.form = None
        return True



def initialise():
    logger = getLogger()
    logger.propagate = False
    config = current_app.config
    
    log_level = getattr(logging, config.get("LOG_LEVEL", "INFO"), logging.INFO)
    
    #root_logger = logging.getLogger()
    #root_logger.setLevel(log_level)
    #logging.getLogger("sqlalchemy").setLevel(log_level)
    
    #if app.config.get("LOG_TO_FILE", False):
        #log_dir = os.path.join(instance_path, "logs")
        #log_file = os.path.join(log_dir, os.path.basename(sys.argv[0]))
        #if not os.path.exists(log_dir):
            #os.mkdir(log_dir)
        #handler = TimedRotatingFileHandler(log_file, when='D', interval=1, backupCount=30)
        #root_logger.addHandler(handler)
        
    #if app.config.get("LOG_TO_CONSOLE", False):
        #handler = logging.StreamHandler()
        #root_logger.addHandler(handler)
    
    #logging.captureWarnings(True)
    
    
    

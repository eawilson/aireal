export FLASK_APP="aireal:create_app('$1')"
export FLASK_DEBUG=1
flask run --port 5000

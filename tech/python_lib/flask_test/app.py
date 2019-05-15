import redis
import uuid
import json
from datetime import datetime


from flask import Flask, make_response, session, request
from flask.sessions import SessionInterface

reds_conn = redis.Redis()


class RedisSession(object):
    def __init__(self, data={}, session_id=None):
        self.modified = False
        self.session_id = session_id
        self.data = data

    def __setitem__(self, key, value):
        self.modified = True
        self.data[key] = value

    def __getitem__(self, key):
        return self.data[key]

    def __repr__(self):
        return str(self.data)


class RedisSessionInterface(SessionInterface):
    def open_session(self, app, request):
        session_id = request.cookies.get(app.session_cookie_name, False)
        if not session_id:
            session_id = str(uuid.uuid1())
        data = reds_conn.get(session_id)
        if data:
            data = json.loads(data.decode())
        else:
            data = {}
        return RedisSession(data=data, session_id=str(uuid.uuid1()))

    def save_session(self, app, session, response):
        if session.modified:
            reds_conn.set(session.session_id, json.dumps(
                session.data), ex=60*60*24*7)

        response.set_cookie(
            app.session_cookie_name,
            session.session_id,
            expires=datetime.utcnow() + app.permanent_session_lifetime,
            httponly=True
        )


app = Flask(__name__)


@app.route('/', methods=("PUT", "DELETE", "GET", "POST", "HEAD"))
def index():
    print(session)
    session['ddd'] = 'aaaa'
    return 'ddddd'


app.session_interface = RedisSessionInterface()
app.secret_key = 'hello'
app.auto_reload = True
app.run()

from flask import Flask
import config
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
# from flask_migrate import Migrate


app = Flask(__name__)
app.config.from_object(config)
socketio = SocketIO(app)
db = SQLAlchemy(app)
# migrate = Migrate(app, db)

from app import routes, models

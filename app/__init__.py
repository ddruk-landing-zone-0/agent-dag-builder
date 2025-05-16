from flask import Flask
from flask_cors import CORS
from app.controller.hello_controller import hello_blueprint
from app.controller.session_controller import session_controller_blueprint
from app.controller.ui_controller import ui_controller_blueprint


app = Flask(__name__)
CORS(app)
app.register_blueprint(hello_blueprint)
app.register_blueprint(session_controller_blueprint)
app.register_blueprint(ui_controller_blueprint)
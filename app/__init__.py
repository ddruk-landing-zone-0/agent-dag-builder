import os
from dotenv import load_dotenv

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "key.json"
os.environ["GOOGLE_CLOUD_PROJECT"] = "sample-project-0-455918"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"
# Load environment variables from .env file
load_dotenv()


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
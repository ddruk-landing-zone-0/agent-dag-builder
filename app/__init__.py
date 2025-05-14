from flask import Flask
from app.controller.hello_controller import hello_blueprint

app = Flask(__name__)
app.register_blueprint(hello_blueprint)
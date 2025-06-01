from flask import Blueprint, jsonify, request
from app.service.hello_service import get_hello_message
from flask_cors import cross_origin

hello_blueprint = Blueprint('hello', __name__)

@hello_blueprint.route('/', methods=['GET', 'POST'])
@hello_blueprint.route('/hello', methods=['GET', 'POST'])
def hello():
    return jsonify(get_hello_message()), 200


@hello_blueprint.route('/health', methods=['POST'])
def health():
    return jsonify({"status": "ok"}), 200
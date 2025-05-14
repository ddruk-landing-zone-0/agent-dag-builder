from flask import Blueprint, jsonify, request
from app.service.hello_service import get_hello_message

hello_blueprint = Blueprint('hello', __name__)

@hello_blueprint.route('/hello', methods=['GET'])
def hello():
    return jsonify(get_hello_message()), 200
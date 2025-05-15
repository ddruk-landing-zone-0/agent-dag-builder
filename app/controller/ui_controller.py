from flask import Blueprint, jsonify, request, render_template
from app.service.hello_service import get_hello_message

ui_controller_blueprint = Blueprint('ui_controller', __name__)


@ui_controller_blueprint.route('/ui/hello')
@ui_controller_blueprint.route('/ui/')
def hello():
    """
    Render the hello page.
    """
    message = get_hello_message()
    return "From UI " + message

@ui_controller_blueprint.route('/ui/view')
def index():
    """
    Render the main UI page.
    """
    return render_template('index-view.html')

@ui_controller_blueprint.route('/ui/create')
def create_session_ui():
    """
    Render the create session UI page.
    """
    return render_template('index-create.html')
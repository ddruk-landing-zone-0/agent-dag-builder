from flask import Blueprint, jsonify, request
from app.service.graph_session import get_graph_session_manager

session_controller_blueprint = Blueprint('session_controller', __name__)
graph_session_manager = get_graph_session_manager()

DEFAULT_LLM_CONFIG = {
    "model_name": "gemini-2.0-flash-001",
    "temperature": 0.5,
    "max_output_tokens": 1000,
    "max_retries": 5,
    "wait_time": 30,
    "deployed_gcp": False
}



@session_controller_blueprint.route('/create-session', methods=['POST'])
def create_session():
    """
    Create a new graph session.
    """
    try:
        session_id = request.json.get('session_id')
        if not session_id:
            return jsonify({"error": "Session ID is required."}), 400
        graph = graph_session_manager.create_session(session_id)
        return jsonify({"session_id": session_id, "graph": graph.to_dict()}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    


@session_controller_blueprint.route('/add-input', methods=['POST'])
def add_input():
    """
    Add input to a graph session.
    """
    try:
        session_id = request.json.get('session_id')
        input_fields = request.json.get('input_fields')
        if not session_id or not input_fields:
            return jsonify({"error": "Session ID and input fields are required."}), 400
        new_node = graph_session_manager.add_input_to_session(session_id, input_fields)
        return jsonify({"new_node": new_node.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@session_controller_blueprint.route('/add-node', methods=['POST'])
def add_node():
    """
    Add a node to a graph session.
    """
    try:
        session_id = request.json.get('session_id')
        node_name = request.json.get('node_name')
        system_instructions = request.json.get('system_instructions')
        user_prompt = request.json.get('user_prompt')
        python_code = request.json.get('python_code')
        output_schema = request.json.get('output_schema')
        useLLM = request.json.get('use_LLM', False)
        jsonMode = request.json.get('json_mode', False)
        tool_name = request.json.get('tool_name', '')
        tool_description = request.json.get('tool_description', '')
        kwargs = request.json.get('kwargs', DEFAULT_LLM_CONFIG)
        
        if not session_id or not node_name or not system_instructions or not user_prompt or not python_code or not output_schema:
            return jsonify({"error": "All fields are required."}), 400
        
        new_node = graph_session_manager.add_node_to_session(session_id, 
                                                             node_name, 
                                                             system_instructions, 
                                                             user_prompt, 
                                                             python_code, 
                                                             output_schema, 
                                                             useLLM, 
                                                             jsonMode,
                                                            tool_name, 
                                                            tool_description, 
                                                            **kwargs)
        return jsonify({"new_node": new_node.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@session_controller_blueprint.route('/update-node', methods=['POST'])
def update_node():
    """
    Update a node in a graph session.
    """
    try:
        session_id = request.json.get('session_id')
        node_name = request.json.get('node_name')
        system_instructions = request.json.get('system_instructions')
        user_prompt = request.json.get('user_prompt')
        python_code = request.json.get('python_code')
        output_schema = request.json.get('output_schema')
        useLLM = request.json.get('use_LLM', False)
        jsonMode = request.json.get('json_mode', False)
        tool_name = request.json.get('tool_name', '')
        tool_description = request.json.get('tool_description', '')
        kwargs = request.json.get('kwargs', DEFAULT_LLM_CONFIG)
        
        if not session_id or not node_name or not system_instructions or not user_prompt or not python_code or not output_schema:
            return jsonify({"error": "All fields are required."}), 400
        
        print("kwargs", kwargs)
        
        updated_node = graph_session_manager.update_node_in_session(session_id, 
                                                                    node_name, 
                                                                    system_instructions,
                                                                    user_prompt, 
                                                                    python_code, 
                                                                    output_schema, 
                                                                    useLLM, 
                                                                    jsonMode, 
                                                                    tool_name, 
                                                                    tool_description, 
                                                                    **kwargs
        )
        return jsonify({"updated_node": updated_node.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@session_controller_blueprint.route('/remove-node', methods=['POST'])
def remove_node():
    """
    Remove a node from a graph session.
    """
    try:
        session_id = request.json.get('session_id')
        node_name = request.json.get('node_name')
        
        if not session_id or not node_name:
            return jsonify({"error": "Session ID and node name are required."}), 400
        
        success = graph_session_manager.remove_node_from_session(session_id, node_name)
        return jsonify({"success": success}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    


@session_controller_blueprint.route('/compile-session', methods=['POST'])
def compile_session():
    """
    Compile a graph session.
    """
    try:
        session_id = request.json.get('session_id')
        if not session_id:
            return jsonify({"error": "Session ID is required."}), 400
        graph = graph_session_manager.compile_session(session_id)
        return jsonify({"graph": graph.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@session_controller_blueprint.route('/execute-session', methods=['POST'])
def execute_session():
    """
    Execute a graph session.
    """
    try:
        session_id = request.json.get('session_id')
        start_node = request.json.get('start_node')
        if not session_id or not start_node:
            return jsonify({"error": "Session ID and start node are required."}), 400
        graph = graph_session_manager.execute_session(session_id, start_node)
        return jsonify({"graph": graph.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@session_controller_blueprint.route('/get-session-graph', methods=['POST'])
def get_session_graph():
    """
    Get the graph of a session.
    """
    try:
        session_id = request.json.get('session_id')
        if not session_id:
            return jsonify({"error": "Session ID is required."}), 400
        graph = graph_session_manager.get_session_graph(session_id)
        return jsonify({"graph": graph.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@session_controller_blueprint.route('/delete-session', methods=['POST'])
def delete_session():
    """
    Delete a graph session.
    """
    try:
        session_id = request.json.get('session_id')
        if not session_id:
            return jsonify({"error": "Session ID is required."}), 400
        success = graph_session_manager.delete_session(session_id)
        return jsonify({"success": success}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@session_controller_blueprint.route('/list-sessions', methods=['GET'])
def list_sessions():
    """
    List all graph sessions.
    """
    try:
        sessions = graph_session_manager.list_sessions()
        return jsonify({"sessions": sessions}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    


@session_controller_blueprint.route('/get-config', methods=['POST'])
def get_config():
    """
    Get the configuration of the graph session manager.
    """
    try:
        session_id = request.json.get('session_id')
        if not session_id:
            return jsonify({"error": "Session ID is required."}), 400
        config = graph_session_manager.get_config(session_id)
        return jsonify({"config": config}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@session_controller_blueprint.route('/set-config', methods=['POST'])
def set_config():
    """
    Set the configuration of the graph session manager.
    """
    try:
        session_id = request.json.get('session_id') 
        config = request.json.get('config')
        if not session_id or not config:
            return jsonify({"error": "Session ID and config are required."}), 400
        success = graph_session_manager.set_config(session_id, config)
        return jsonify({"success": success}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@session_controller_blueprint.route('/downlaod-pypackages', methods=['POST'])
def download_python_packages():
    """
    Install packages in the graph session.
    """
    try:
        session_id = request.json.get('session_id')
        packages = request.json.get('packages')
        if not session_id or not packages:
            return jsonify({"error": "Session ID and packages are required."}), 400
        success = graph_session_manager.download_python_packages(session_id, packages)
        return jsonify({"success": success}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
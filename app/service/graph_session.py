from .logger import LOGGER
from .graphs import Graph
import time
import os
import shutil
from functools import lru_cache


class GraphSessionManager:
    """
    It is a wrapper around the Graph class to manage multiple graph sessions.
    It allows creating, updating, deleting, and executing graph sessions.
    Each session contains a unique graph object and metadata.
    """
    def __init__(self, session_root_dir, timeout=10, venv_path=None, create_env=False):
        self.timeout = timeout
        self.venv_path = venv_path
        self.create_env = create_env

        self.session_keys = os.listdir(session_root_dir)
        self.session_metadata = {}
        
        for session_key in self.session_keys:
            self.session_metadata[session_key] = {
                'session_id': session_key,
                'graph': None,
                'created_at': time.time(),
                'updated_at': time.time(),
            }
            self.session_metadata[session_key]['graph'] = self.load_graph_into_session(session_key)
            
    def load_graph_into_session(self, session_key):
        graph = Graph(timeout=self.timeout, venv_path=None, create_env=None, python_packages=None, save_dir=f"./saved_graphs/{session_key}/")
        graph.load_graph()
        return graph
    
    def create_session(self, session_id, venv_path=None, create_env=None, python_packages=[]):
        if session_id in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} already exists.")
        
        if venv_path is None:
            venv_path = self.venv_path
        if create_env is None:
            create_env = self.create_env
        if python_packages is None:
            python_packages = []
        
        ############# Create a new graph and save it to the session directory
        graph = Graph(timeout=self.timeout, venv_path=venv_path, create_env=create_env, python_packages=python_packages, save_dir=f"./saved_graphs/{session_id}/")
        os.makedirs(os.path.join("./saved_graphs/", session_id), exist_ok=True)
        graph.compile()
        
        self.session_metadata[session_id] = {
            'session_id': session_id,
            'graph': graph,
            'created_at': time.time(),
            'updated_at': time.time(),
        }
        return graph
    
    def add_input_to_session(self, session_id, inputFields):
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        graph = self.session_metadata[session_id]['graph']
        new_node = graph.addInput(inputFields)
        graph.compile()
        return new_node

    def add_node_to_session(self, session_id, nodeName, systemInstructions, userPrompt, pythonCode, outputSchema, **kwargs):
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        graph = self.session_metadata[session_id]['graph']
        new_node = graph.addNode(nodeName, systemInstructions, userPrompt, pythonCode, outputSchema, **kwargs)
        # graph.compile()
        return new_node
    
    def update_node_in_session(self, session_id, nodeName, systemInstructions, userPrompt, pythonCode, outputSchema, **kwargs):
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        graph = self.session_metadata[session_id]['graph']
        updated_node = graph.updateNode(nodeName, systemInstructions, userPrompt, pythonCode, outputSchema, **kwargs)
        # graph.compile()
        return updated_node
    
    def remove_node_from_session(self, session_id, nodeName):
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        graph = self.session_metadata[session_id]['graph']
        graph.removeNode(nodeName)
        # graph.compile()
        return True
    
    def compile_session(self, session_id):
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        graph = self.session_metadata[session_id]['graph']
        graph.compile()
        return graph
    
    def execute_session(self, session_id, start_node):
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        graph = self.session_metadata[session_id]['graph']
        graph.execute_from_node(start_node)
        return graph
    
    def get_session_graph(self, session_id):
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        return self.session_metadata[session_id]['graph']
    
    def delete_session(self, session_id):
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        del self.session_metadata[session_id]
        LOGGER.info(f"Session {session_id} deleted.")
        session_dir = os.path.join("./saved_graphs/", session_id)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
            LOGGER.info(f"Session directory {session_dir} deleted.")
        else:
            LOGGER.warning(f"Session directory {session_dir} does not exist.")
        return True
    
    def list_sessions(self):
        return list(self.session_metadata.keys())




@lru_cache(maxsize=None)
def get_graph_session_manager():
    """
    This function returns a singleton instance of the GraphSessionManager.
    It is used to manage multiple graph sessions.
    """
    if not hasattr(get_graph_session_manager, "_instance"):
        get_graph_session_manager._instance = GraphSessionManager(session_root_dir="./saved_graphs/", 
                                                                    timeout=10, 
                                                                    venv_path="./runner_envs/venv", 
                                                                    create_env=False
                                                                    )
    return get_graph_session_manager._instance
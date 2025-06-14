from .logger import LOGGER
from .graph import Graph
import time
import os
import shutil
from functools import lru_cache

# Add import for GCS
from google.cloud import storage

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

        # GCS logic
        self.access_gcs = os.environ.get("ACCESS_GCS", "false").lower() == "true"
        self.gcs_bucket = os.environ.get("GCS_BUCKET")
        self.session_root_dir = session_root_dir

        if self.access_gcs:
            if not self.gcs_bucket:
                raise ValueError("GCS_BUCKET environment variable is not set.")
            client = storage.Client()
            bucket = client.bucket(self.gcs_bucket)
            # List all "directories" (prefixes) under session_root_dir
            blobs = bucket.list_blobs(prefix=session_root_dir.strip("/") + "/", delimiter="/")
            self.session_keys = set()
            for page in blobs.pages:
                for prefix in page.prefixes:
                    session_key = prefix.rstrip("/").split("/")[-1]
                    self.session_keys.add(session_key)
            self.session_keys = list(self.session_keys)
        else:
            self.session_keys = os.listdir(session_root_dir)
        self.session_metadata = {}
        
        for session_key in self.session_keys:
            try:
                self.session_metadata[session_key] = {
                    'session_id': session_key,
                    'graph': None,
                    'created_at': time.time(),
                    'updated_at': time.time(),
                }
                self.session_metadata[session_key]['graph'] = self.load_graph_into_session(session_key)
            except Exception as e:
                LOGGER.error(f"Error loading session {session_key}: {e}")
                del self.session_metadata[session_key]
    

    def load_graph_into_session(self, session_key):
        """
        It initializes a dummy graph object and loads the graph from the session directory.
        The graph is stored as /saved_graphs/{session_key}/graph.json.
        """
        graph = Graph(timeout=self.timeout, venv_path=None, create_env=None, python_packages=None, save_dir=f"{self.session_root_dir.rstrip('/')}/{session_key}/")
        graph.load_graph()
        return graph
    
    def create_session(self, session_id, venv_path=None, create_env=None, python_packages=[]):
        """
        It creates a new graph session with the given session ID.
        If the session ID already exists, it raises a ValueError.
        """
        if session_id in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} already exists.")
        
        if venv_path is None:
            venv_path = self.venv_path # default to the class variable
        if create_env is None:
            create_env = self.create_env # default to the class variable
        if python_packages is None:
            python_packages = [] # default to empty list
        
        ############# Create a new graph and save it to the session directory
        graph = Graph(timeout=self.timeout, venv_path=venv_path, create_env=create_env, python_packages=python_packages, save_dir=f"{self.session_root_dir.rstrip('/')}/{session_id}/")
        if not self.access_gcs:
            os.makedirs(os.path.join(self.session_root_dir, session_id), exist_ok=True) # create the session directory if it doesn't exist

        # Add a dummy input node to the graph
        sampleInputFields = {
            "input1": "<Sample Input>",
        }
        graph.addInput(sampleInputFields)

        graph.compile() # compile the graph
        
        self.session_metadata[session_id] = {
            'session_id': session_id,
            'graph': graph,
            'created_at': time.time(),
            'updated_at': time.time(),
        }
        return graph
    
    def add_input_to_session(self, session_id, inputFields):
        """
        It is wrapper around the addInput method of the Graph class.
        """
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        graph = self.session_metadata[session_id]['graph']
        new_node = graph.addInput(inputFields)
        graph.compile()
        return new_node

    def add_node_to_session(self, session_id, nodeName, systemInstructions, userPrompt, pythonCode, outputSchema ,useLLM, jsonMode, toolName, toolDescription, **kwargs):
        """
        It is wrapper around the addNode method of the Graph class.
        """
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        graph = self.session_metadata[session_id]['graph']
        new_node = graph.addNode(nodeName, systemInstructions, userPrompt, pythonCode, outputSchema, useLLM, jsonMode, toolName, toolDescription, **kwargs)
        # graph.compile()
        return new_node
    
    def update_node_in_session(self, session_id, nodeName, systemInstructions, userPrompt, pythonCode, outputSchema, useLLM, jsonMode, toolName, toolDescription, **kwargs):
        """
        It is wrapper around the updateNode method of the Graph class.
        """
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        graph = self.session_metadata[session_id]['graph']
        updated_node = graph.updateNode(nodeName, systemInstructions, userPrompt, pythonCode, outputSchema ,useLLM, jsonMode, toolName, toolDescription, **kwargs)
        # graph.compile()
        return updated_node
    
    def remove_node_from_session(self, session_id, nodeName):
        """
        It is wrapper around the removeNode method of the Graph class.
        """
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        graph = self.session_metadata[session_id]['graph']
        graph.removeNode(nodeName)
        # graph.compile()
        return True
    
    def compile_session(self, session_id):
        """
        It is wrapper around the compile method of the Graph class.
        """
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        graph = self.session_metadata[session_id]['graph']
        graph.compile()
        return graph
    
    def execute_session(self, session_id, start_node):
        """
        It is wrapper around the execute method of the Graph class.
        """
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        graph = self.session_metadata[session_id]['graph']
        graph.execute_from_node(start_node)
        return graph
    
    def get_session_graph(self, session_id):
        """
        It returns the graph object of the session with the given session ID.
        """
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        return self.session_metadata[session_id]['graph']
    
    def delete_session(self, session_id):
        """
        It deletes the session with the given session ID from RAM.
        Then it deletes the session directory from the disk or GCS.
        """
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        del self.session_metadata[session_id]
        LOGGER.info(f"Session {session_id} deleted.")
        session_dir = os.path.join(self.session_root_dir, session_id)
        if self.access_gcs:
            # Delete all blobs under the session_dir prefix in GCS
            try:
                client = storage.Client()
                bucket = client.bucket(self.gcs_bucket)
                prefix = f"{self.session_root_dir.rstrip('/')}/{session_id}/"
                blobs = bucket.list_blobs(prefix=prefix)
                deleted_any = False
                for blob in blobs:
                    blob.delete()
                    deleted_any = True
                if deleted_any:
                    LOGGER.info(f"GCS session directory {prefix} deleted.")
                else:
                    LOGGER.warning(f"GCS session directory {prefix} does not exist or is empty.")
            except Exception as e:
                LOGGER.error(f"Error deleting GCS session directory {prefix}: {e}")
        else:
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)
                LOGGER.info(f"Session directory {session_dir} deleted.")
            else:
                LOGGER.warning(f"Session directory {session_dir} does not exist.")
        return True
    
    def list_sessions(self):
        """
        It returns a list of all session IDs.
        """
        return list(self.session_metadata.keys())
    
    def download_python_packages(self, session_id, python_packages=[]):
        """
        It is wrapper around the install_dependencies method of the Graph class.
        """
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        if not python_packages:
            raise ValueError(f"No python packages provided.")
        
        if self.venv_path is None:
            raise ValueError(f"Virtual environment path is not set.")
        
        graph = self.session_metadata[session_id]['graph']
        
        if graph.python_env_manager is None:
            raise ValueError(f"Graph does not have a virtual environment manager.")
        
        graph.python_env_manager.install_dependencies(python_packages)
        return True
    
    def get_config(self,session_id):
        """
        It returns the kwargs configuration of the GraphSessionManager.
        """
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        graph = self.session_metadata[session_id]['graph']

        configs = {}

        for nodeName,node in graph.nodePool.items():
            configs[node.nodeName] = {
                'useLLM': node.useLLM,
                'jsonMode': node.jsonMode,
                **node.kwargs
            } 

        return configs
    
    def set_config(self, session_id, config):
        """
        It sets the kwargs configuration of the GraphSessionManager.
        """
        if session_id not in self.session_metadata:
            raise ValueError(f"Session with ID {session_id} does not exist.")
        
        graph = self.session_metadata[session_id]['graph']


        for nodeName,node in graph.nodePool.items():
            if node.nodeName in config:
                # Check config's key are valid
                node.useLLM = config[node.nodeName].get('useLLM', node.useLLM)
                node.jsonMode = config[node.nodeName].get('jsonMode', node.jsonMode)
                for key, value in config[node.nodeName].items():
                    if key not in ['useLLM', 'jsonMode']:
                        node.kwargs[key] = value

        # Compile the graph after setting the config
        graph.compile()
        # Save the graph to the session directory
        graph.save_graph()
        return True

@lru_cache(maxsize=None)
def get_graph_session_manager():
    """
    This function returns a singleton instance of the GraphSessionManager.
    It is used to manage multiple graph sessions.
    """
    if not hasattr(get_graph_session_manager, "_instance"):
        get_graph_session_manager._instance = GraphSessionManager(session_root_dir="./saved_graphs/", 
                                                                    timeout=20, 
                                                                    venv_path="./runner_envs/venv", 
                                                                    create_env=True
                                                                    )
    return get_graph_session_manager._instance
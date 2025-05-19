
from .logger import LOGGER
from .pyenv_manager import PythonEnvironmentManager
from .graph_node import GraphNode
import hashlib
import json
import threading
import time
from collections import defaultdict
import os
import json



class Graph:
    """
    This class represents a directed acyclic graph (DAG) of nodes.
    Each node can have multiple parents and children, and the graph can be executed
    in a topological order.
    The graph can be saved to and loaded from a JSON file.
    Seperate threads are used to execute the nodes concurrently.
    If a node is waiting for its parent nodes to complete, it will wait for a specified timeout.
    The graph can also be compiled to check for circular dependencies and to generate a unique ID.
    The graph can be executed from a specific starting node, and the execution can be controlled with timeouts.
    """
    def __init__(self, timeout=10, venv_path=None, create_env=False, python_packages=[], save_dir=None):
        self.nodePool = {
        } # Dictionary to hold all nodes
        self.save_dir = save_dir # Directory to save the graph
        self.graph_id = None # Unique ID for the graph (auto-generated from the node hashes)
        self.conditions = defaultdict(threading.Condition) # Dictionary to hold conditional variables for each node
        self.lock = threading.Lock() # Lock for thread safety
        self.timeout = timeout # Timeout for node execution

        self.venv_path = venv_path # Path to the virtual environment
        self.python_packages = python_packages # List of Python packages to install in the virtual environment
        self.create_env = create_env # Flag to create a new virtual environment

        if self.venv_path is not None:
            self.python_env_manager = PythonEnvironmentManager(self.venv_path, self.create_env) # Initialize the Python environment manager
            if python_packages:
                self.python_env_manager.install_dependencies(python_packages) # Install the required packages
        else:
            self.python_env_manager = None

    def addInput(self, inputFields):
        """
        Add input fields to the graph.
        Example input fields:
        inputFields: Dict[str, str]
        {
            "input1": "value1",
            "input2": "value2"
        }

        Output:
        GraphNode object representing the input node.
        """
        # Add input fields to the graph
        if not isinstance(inputFields, dict):
            raise ValueError("Input fields must be a dictionary")
        
        # Validate the input fields
        for key, value in inputFields.items():
            if not isinstance(key, str):
                LOGGER.error(f"Key '{key}' in input fields must be a string")
                raise ValueError(f"Key '{key}' in input fields must be a string")
            if not isinstance(value, str):
                LOGGER.error(f"Value '{value}' in input fields must be a string")
                raise ValueError(f"Value '{value}' in input fields must be a string")
        
        # Create a new input node with dummy instructions. Only the outputSchema are important. The nodename is fixed as "inputs"
        new_node = GraphNode("inputs", # nodeName
                                "N/A", # systemInstructions
                                "N/A", # userPrompt
                                {}, # pythonCode
                                {**inputFields}, # outputSchema
                                False, # useLLM
                                False, # jsonMode
                                "N/A", # toolName
                                "N/A", # toolDescription
                                **inputFields # kwargs
                                )
        self.nodePool["inputs"] = new_node # Add the input node to the node pool
        return new_node


    def addNode(self, nodeName, systemInstructions, userPrompt, pythonCode, outputSchema, useLLM=True, jsonMode=False, toolName=None, toolDescription=None, **kwargs):
        """
        Add a new node to the graph.
        nodeName: str
        systemInstructions: str
        userPrompt: str
        pythonCode: A dictionary containing the arguments and function
        outputSchema: A dictionary containing the output schema with output names as keys and their description.
        useLLM: bool, whether to use LLM for this node
        jsonMode: bool, whether to use JSON mode for this node
        toolName: str, name of the tool
        toolDescription: str, description of the tool
        kwargs: Additional keyword arguments for the node.

        Example input for pythonCode:
        nodeName: "node1"
        systemInstructions: "This is a test node"
        userPrompt: "Please provide the input"
        pythonCode: {
            "function_body": "def my_function(arg1, arg2): return arg1 + arg2",
            "argument": {
                "arg1": "@[inputs.input1]",
                "arg2": "10"
            }
        }
        outputSchema: {
            "output1": "Description of output1",
            "output2": "Description of output2"
        }


        output:
        GraphNode object representing the new node.
        """
        # Add a new node to the graph
        if nodeName in self.nodePool:
            raise ValueError(f"Node with name {nodeName} already exists. Location: Graph.addNode")
        
        new_node = GraphNode(
            nodeName=nodeName,
            systemInstructions=systemInstructions,
            userPrompt=userPrompt,
            pythonCode=pythonCode,
            outputSchema=outputSchema,
            useLLM=useLLM,
            jsonMode=jsonMode,
            toolName=toolName,
            toolDescription=toolDescription,
            **kwargs
        )
        self.nodePool[nodeName] = new_node
        try:
            self.compile()
        except Exception as e:
            LOGGER.error(f"Error compiling graph after adding node {nodeName}: {e}. Location: Graph.addNode")
            self.removeNode(nodeName)
            raise ValueError(e)
        return new_node
    
    def removeNode(self, nodeName):
        """
        Remove a node from the graph.
        nodeName: str
        """
        # Remove a node from the graph
        if nodeName not in self.nodePool:
            raise ValueError(f"Node with name {nodeName} does not exist. Location: Graph.removeNode")

        # Dependency nodes are the nodes which are dependent on this node excluding this node
        dependency_nodes = self._traverse_nodes(nodeName)
        dependency_nodes.remove(nodeName)

        # Remove the node from its parents
        for parent in self.nodePool[nodeName]._parents:
            parent_node = self.nodePool[parent[0]]
            if nodeName in parent_node._children:
                parent_node._children.remove(nodeName)
        # Remove the node from its children
        for child in self.nodePool[nodeName]._children:
            child_node = self.nodePool[child]
            for parent in child_node._parents:
                if parent[0] == nodeName:
                    child_node._parents.remove(parent)


        # Remove the node from the node pool
        del self.nodePool[nodeName]
        LOGGER.info(f"Node {nodeName} removed from the graph. Location: Graph.removeNode")
        
        # Uncompile the graph which are dependent on this node including this node
        self.reset_compiled_nodes(dependency_nodes)
        # # Save the graph
        # self.save_graph()
        LOGGER.info(f"Graph reset after removing node {nodeName}. Location: Graph.removeNode")
        return True
    
    def updateNode(self, nodeName, systemInstructions, userPrompt, pythonCode, outputSchema, useLLM=True, jsonMode=False, toolName=None, toolDescription=None, **kwargs):
        """
        Update an existing node in the graph.
        nodeName: str
        systemInstructions: str
        userPrompt: str
        pythonCode: A dictionary containing the arguments and function
        outputSchema: A dictionary containing the output schema with output names as keys and their description.
        useLLM: bool, whether to use LLM for this node
        jsonMode: bool, whether to use JSON mode for this node
        toolName: str, name of the tool
        toolDescription: str, description of the tool
        kwargs: Additional keyword arguments for the node.

        Example input for pythonCode:
        nodeName: "node1"
        systemInstructions: "This is a test node"
        userPrompt: "Please provide the input"
        pythonCode: {
            "function_body": "def my_function(arg1, arg2): return arg1 + arg2",
            "argument": {
                "arg1": "@[inputs.input1]",
                "arg2": "10"
            }
        }
        outputSchema: {
            "output1": "Description of output1",
            "output2": "Description of output2"
        }

        output:
        new_node: GraphNode object representing the updated node.
        """
        # Update an existing node in the graph
        if nodeName not in self.nodePool:
            raise ValueError(f"Node with name {nodeName} does not exist. Location: Graph.updateNode")

        # Dependency nodes are the nodes which are dependent on this node excluding this node
        dependency_nodes = self._traverse_nodes(nodeName)
        dependency_nodes.remove(nodeName)

        # Dlelete the node from the graph
        self.removeNode(nodeName)

        # Add the updated node
        new_node = GraphNode(
            nodeName=nodeName,
            systemInstructions=systemInstructions,
            userPrompt=userPrompt,
            pythonCode=pythonCode,
            outputSchema=outputSchema,
            useLLM=useLLM,
            jsonMode=jsonMode,
            toolName=toolName,
            toolDescription=toolDescription,
            **kwargs
        )

        # Add the updated node to the node pool
        self.nodePool[nodeName] = new_node

        # Reset the compliation status of the graph which are dependent on this node including this node
        self.reset_compiled_nodes(dependency_nodes)

        # Compile the graph
        self.compile()

        return new_node
    
    def getNode(self, nodeName):
        """
        Retrieve a node from the graph by its name.
        nodeName: str
        output:
        GraphNode object representing the node.
        """
        # Retrieve a node from the graph
        if nodeName not in self.nodePool:
            raise ValueError(f"Node with name {nodeName} does not exist. Location: Graph.getNode")
        
        return self.nodePool[nodeName]
    
    def compile(self):
        """
        Compile the graph by checking dependencies and setting parent-child relationships.
        This method also checks for circular dependencies and generates a unique ID for the graph.
        The graph ID is generated from the hashes of the nodes in the graph.
        The graph is saved to a JSON file after compilation.
        """
        # Compile the graph by checking dependencies and setting parent-child relationships
        for node in self.nodePool.values():
            if self.nodePool[node.nodeName].resolve_parent_nodes(self.nodePool) is not None:
                self.nodePool[node.nodeName].resolve_engine()
                node._compiled = True
            else:
                node._compiled = False
                LOGGER.error(f"Node {node.nodeName} is not compiled. Location: Graph.compile")

        # Check for circular dependencies
        self.check_circular_dependency()

        # Gnerate a unique graph ID from the node hashes
        node_hashes = [node.hash() for node in self.nodePool.values()]
        self.graph_id = hashlib.sha256("".join(node_hashes).encode()).hexdigest()

        LOGGER.info(f"Graph compiled with ID: {self.graph_id}. Location: Graph.compile")

        # Save the graph
        self.save_graph()

    def reset_compiled_nodes(self,nodeNames=None):
        """
        Reset the compiled status of all nodes in the graph.
        This method sets the status of all nodes to "pending" and clears their parent and child relationships.
        It also clears the inputs and outputs of all nodes.
        The graph is saved to a JSON file after resetting.
        Exception: input node is not reset.
        """
        # Reset the compiled status of all nodes
        target_node_names = self.nodePool.keys() if nodeNames is None else nodeNames
        for node in self.nodePool.values():
            if node.nodeName == "inputs" or node.nodeName not in target_node_names:
                continue
            node._compiled = False
            node.status = "pending"
            node._parents = []
            node._children = []
            node._inputs = {}
            node._outputs = {}
        LOGGER.info("All nodes reset to uncompiled state. Location: Graph.reset_compiled_nodes")

        # self.compile() # Recompile the graph
        self.save_graph()
        
    def check_circular_dependency(self):
        """
        Check for circular dependencies in the graph.
        """
        # Check for circular dependencies in the graph
        visited = set()
        stack = set()
        def visit(node):
            if node in stack:
                raise ValueError(f"Circular dependency detected: {node}. Location: Graph.check_circular_dependency")
            if node not in visited:
                visited.add(node)
                stack.add(node)
                for child in self.nodePool[node]._children:
                    visit(child)
                stack.remove(node)
        for node in self.nodePool:
            if node not in visited:
                visit(node)
        return True
     
    
    def print_graph(self):
        """
        Print the graph in a readable format.
        """
        for node in self.nodePool.values():
            print(node.to_dict())
        print("\n")

    def _execute_node_with_condition(self, node, timeout, involved_nodes):
        """
        Execute a node with a condition to wait for its parent nodes to complete.
        node: GraphNode object representing the node to be executed.
        timeout: int, timeout for the node execution.
        involved_nodes: set, set of nodes involved in the execution

        This method uses a condition variable to wait for the parent nodes to complete before executing the node.
        It also handles timeouts and notifies all waiting threads when a node is completed.
        """

        start_time = time.time() # Record the start time
        condition = self.conditions[node.nodeName] # Get the condition variable for the node

        # Wait for the parent nodes to complete
        with condition:
            while not node.check_parent_status(self.nodePool):
                remaining = timeout - (time.time() - start_time)
                if remaining <= 0:
                    LOGGER.warning(f"Timeout reached for node {node.nodeName}. Location: Graph._execute_node_with_condition")
                    raise TimeoutError(f"Node {node.nodeName} timed out.")
                LOGGER.debug(f"Node {node.nodeName} is waiting for parent nodes to complete. Location: Graph._execute_node_with_condition")
                condition.wait(timeout=remaining)

        # Execute the node
        with self.lock:
            involved_nodes.add(node.nodeName)
            LOGGER.info(f"Running node: {node.nodeName}. Location: Graph._execute_node_with_condition")
            result = node.execute(self.nodePool, self.python_env_manager) # Execute the node
            LOGGER.info(f"Completed node: {node.nodeName} with result: {result} . Location: Graph._execute_node_with_condition")

        # Notify all waiting threads
        for child in node._children:
            # if all parents of the child node are completed
            if self.nodePool[child].check_parent_status(self.nodePool):
                with self.lock:
                    # Notify all waiting threads for the child node
                    with self.conditions[child]:
                        self.conditions[child].notify_all()

    def _traverse_nodes(self, start_node):
        """
        Depth-first traversal of the graph starting from a specific node.
        Returns a list of all visited nodenames
        """
        visited = set()
        queue = [start_node]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            node = self.nodePool[current]
            queue.extend(node._children)
        
        return list(visited)
    
    def execute_from_node(self, start_node):
        # Execute the graph from a specific starting node
        if start_node not in self.nodePool:
            LOGGER.error(f"Node with name {start_node} does not exist. Location: Graph.execute_from_node")
            raise ValueError(f"Node with name {start_node} does not exist.")
        
        visited = self._traverse_nodes(start_node)

        # Check if all nodes are compiled
        for node_name in visited:
            node = self.nodePool[node_name]
            if not node._compiled:
                LOGGER.error(f"Node {node_name} is not compiled. Location: Graph.execute_from_node")
                raise ValueError(f"Node {node_name} is not compiled.")
            
        # Check if all nodes are completed
        for node_name in visited:
            if node_name == "inputs":
                continue
            node = self.nodePool[node_name]
            if node.status == "running" or node.status == "waiting":
                LOGGER.error(f"Node {node_name} is already running or waiting. Location: Graph.execute_from_node")  
                raise ValueError(f"Node {node_name} is already running or waiting.")
            node.status = "pending"
            LOGGER.info(f"Node {node_name} status set to pending.")


        threads = [] # List to hold threads for concurrent execution
        involved_nodes = set() # Set to hold nodes involved in the traversal

        # Execute the nodes in a separate thread
        try:
            for node_name in visited:
                node = self.nodePool[node_name]
                if node.status == "pending":
                    # Create a new thread for each node
                    thread = threading.Thread(target=self._execute_node_with_condition, args=(node, self.timeout, involved_nodes))
                    threads.append(thread)
                    thread.start()
                    LOGGER.info(f"Thread started for node: {node_name} . Location: Graph.execute_from_node")
            
            for thread in threads:
                thread.join() # Wait for all threads to complete

        except TimeoutError as e:
            # Handle timeout error
            LOGGER.critical(f"Timeout error: {e}")
            # Set the status of all involved nodes to completed if they are still running (!!Unnecessary, already handled in finally block)
            for node_name in involved_nodes:
                node = self.nodePool[node_name]
                if node.status == "running":
                    node.status = "completed"
                    LOGGER.warning(f"Node {node_name} status set to completed due to timeout. Location: Graph.execute_from_node")
            LOGGER.error(f"Error during execution: {e}")
            
        finally:
            # # Set the status of all nodes to completed if they are still running
            # for node_name in visited:
            #     node = self.nodePool[node_name]
            #     if node.status == "running":
            #         node.status = "completed"
            #         LOGGER.info(f"Node {node_name} status set to completed. Location: Graph.execute_from_node")
            LOGGER.info("Execution completed for all nodes. Location: Graph.execute_from_node")

        self.save_graph()

    def to_dict(self):
        # Convert the graph to a dictionary representation
        graph_dict = {
            "graph_id": self.graph_id,
            "nodes": {node_name: node.to_dict() for node_name, node in self.nodePool.items()}, # Dictionary of nodes
            "venv_path": self.venv_path,
            "python_packages": self.python_packages,
            "create_env": self.create_env
        }
        return graph_dict


    def save_graph(self):
        """
        Save the graph to a JSON file.
        Path is resolved as : /self.save_dir(session_id)/graph.json
        The graph is saved in a directory specified by the save_dir attribute.
        """
        # Save the graph to a JSON file
        if not self.save_dir:
            LOGGER.error("Save directory is not set. Location: Graph.save_graph")
            raise ValueError("Save directory is not set. Location: Graph.save_graph")
        file_path = os.path.join(self.save_dir, f"graph.json")
        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=4)
        LOGGER.info(f"Graph saved to {file_path}. Location: Graph.save_graph")

    def load_graph(self):
        """
        Load the graph from a JSON file.
        Path is resolved as : /self.save_dir(session_id)/graph.json
        """
        # Load the graph from a JSON file
        file_path = os.path.join(self.save_dir, f"graph.json")
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                for node_name, node_data in data["nodes"].items():

                    # Create a new GraphNode object from the loaded data
                    node = GraphNode(
                        nodeName=node_data["nodeName"],
                        systemInstructions=node_data["systemInstructions"],
                        userPrompt=node_data["userPrompt"],
                        pythonCode=node_data["pythonCode"],
                        outputSchema=node_data["outputSchema"],
                        useLLM=node_data["useLLM"],
                        jsonMode=node_data["jsonMode"],
                        toolName=node_data["toolName"],
                        toolDescription=node_data["toolDescription"],
                        **node_data["kwargs"]
                    )

                    # Set the node's properties
                  #  print("fasdfasdfafas ",node_data["_inputs"])
                    node._compiled = node_data["_compiled"]
                    node._parents = node_data["_parents"]
                    node._children = node_data["_children"]
                    node._inputs = node_data["_inputs"]
                    node._outputs = node_data["_outputs"]
                    node.status = node_data["status"]
                    
                    # Add the node to the node pool
                    self.nodePool[node_name] = node


                # Tries to gerneate the python env object
                self.venv_path = data.get("venv_path", None)
                self.python_packages = data.get("python_packages", [])
                self.create_env = data.get("create_env", False)
                
                if self.venv_path is not None:
                    self.python_env_manager = PythonEnvironmentManager(self.venv_path, self.create_env)
                    if self.python_packages:
                        self.python_env_manager.install_dependencies(self.python_packages)
                
                LOGGER.info(f"Graph loaded from {file_path}. Location: Graph.load_graph")
        except FileNotFoundError:
            LOGGER.error(f"Graph file not found: {file_path}. Location: Graph.load_graph")
            raise
        except json.JSONDecodeError:
            LOGGER.error(f"Error decoding JSON from file: {file_path}. Location: Graph.load_graph")
            raise
        except Exception as e:
            LOGGER.error(f"Error loading graph: {e}. Location: Graph.load_graph")
            raise
        self.compile()
        LOGGER.info(f"Graph compiled after loading from {file_path}. Location: Graph.load_graph")
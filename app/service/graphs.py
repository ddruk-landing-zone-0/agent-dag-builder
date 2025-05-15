from .logger import LOGGER
from .pyenv_manager import PythonEnvironmentManager
import hashlib
import json
import re
import threading
import time
from collections import defaultdict
import os
import json



class GraphNode:
    def __init__(self, nodeName, systemInstructions, userPrompt, pythonCode, outputSchema, **kwargs):
        
        self.nodeName = nodeName # str: Name of the node
        self.systemInstructions = systemInstructions # str: Instructions for the system or the system prompt
        self.userPrompt = userPrompt # str: User prompt or question can include reference to other nodes
        self.pythonCode = pythonCode # str: Python code to be executed
        self.outputSchema = outputSchema # Dict: Schema for the output of the node. Dictionary to a dictionary with string keys and values
        self.kwargs = kwargs # Additional keyword arguments for flexibility

        self._validate() # Validate the node's properties
        self.id = self.hash() # str: Unique identifier for the node

        self._compiled = False # bool: Flag to indicate if the node has been compiled
        self._parents = [] # List: Parent nodes
        self._children = [] # List: Child nodes

        self._inputs = {} # It is a mutable mapping of input names to their values where the keys are the output keys of the parent nodes' outputs
        self._outputs = {} # It is a mutable mapping of output names to their values where the keys are the output keys of the current node's outputs

        self.status = "pending" # str: Status of the node, can be "pending", "running" or "completed" or "waiting"

        if nodeName=="inputs":
            self.status = "running"
            self._outputs = {**kwargs}
            self.status = "completed"
    
    def _validate(self):
        # Validate the node's properties
        if not isinstance(self.nodeName, str):
            LOGGER.error("nodeName must be a string. Location: GraphNode._validate")
            raise ValueError("nodeName must be a string")
        if not isinstance(self.systemInstructions, str):
            LOGGER.error("systemInstructions must be a string. Location: GraphNode._validate")
            raise ValueError("systemInstructions must be a string")
        if not isinstance(self.userPrompt, str):
            LOGGER.error("userPrompt must be a string. Location: GraphNode._validate")
            raise ValueError("userPrompt must be a string")
        if not isinstance(self.pythonCode, dict):
            LOGGER.error("pythonCode must be a dict format with a argument and the function_body as the value. Location: GraphNode._validate")
            raise ValueError("pythonCode must be a dict format with a argument and the function_body as the value")
        
        if self.pythonCode != {}:
            if not isinstance(self.pythonCode.get("argument"), dict):
                LOGGER.error("pythonCode must have an 'argument' key with a dict value of named arguments. Location: GraphNode._validate")
                raise ValueError("pythonCode must have an 'argument' key with a dict value of named arguments")
            if not all(isinstance(k, str) and isinstance(v, str) for k, v in self.pythonCode["argument"].items()):
                LOGGER.error("pythonCode['argument'] must be a dictionary with string keys and values. Location: GraphNode._validate")
                raise ValueError("pythonCode['argument'] must be a dictionary with string keys and values")
            if not isinstance(self.pythonCode.get("function_body"), str):
                LOGGER.error("pythonCode must have a 'function_body' key with a string value. Location: GraphNode._validate")
                raise ValueError("pythonCode must have a 'function_body' key with a string value")
        
        if not isinstance(self.outputSchema, dict):
            LOGGER.error("outputSchema must be a dictionary. Location: GraphNode._validate")
            raise ValueError("outputSchema must be a dictionary")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in self.outputSchema.items()):
            LOGGER.error("outputSchema must be a dictionary with string keys and values. Location: GraphNode._validate")
            raise ValueError("outputSchema must be a dictionary with string keys and values")
        if not isinstance(self.kwargs, dict):
            LOGGER.error("kwargs must be a dictionary. Location: GraphNode._validate")
            raise ValueError("kwargs must be a dictionary")
        for key, value in self.kwargs.items():
            if not isinstance(key, str):
                LOGGER.error(f"Key '{key}' in kwargs must be a string. Location: GraphNode._validate")
                raise ValueError(f"Key '{key}' in kwargs must be a string")
            if not isinstance(value, str):
                LOGGER.error(f"Value '{value}' in kwargs must be a string. Location: GraphNode._validate")
                raise ValueError(f"Value '{value}' in kwargs must be a string")
            
    
    def hash(self):
        # Generate a hash for the node based on its properties
        node_string = f"{self.nodeName}{self.systemInstructions}{self.userPrompt}{self.pythonCode}{str(self.outputSchema)}{str(self.kwargs)}"
        return hashlib.sha256(node_string.encode()).hexdigest()
    
    def _validate_references(self, parent_list, nodePool):
        for parent in parent_list:
            if parent[0] not in nodePool:
                LOGGER.error(f"Parent node {parent[0]} not found in node pool. Location: GraphNode._validate_parent")
                raise ValueError(f"Parent node {parent[0]} not found in node pool.")
            if parent[1] not in nodePool[parent[0]].outputSchema:
                LOGGER.error(f"Output key '{parent[1]}' not found in parent node {parent[0]}. Location: GraphNode._validate_parent")
                raise ValueError(f"Output key '{parent[1]}' not found in parent node {parent[0]}.")
        return True

    
    def resolve_parent_nodes(self, nodePool):
        self._parents = []
        pattern = r'@\[(\w+)\.(\w+)\]'
        
        references = re.findall(pattern, self.systemInstructions)
        references += re.findall(pattern, self.userPrompt)
        references += re.findall(pattern, self.pythonCode.get("function_body", ""))
        references += re.findall(pattern, str(self.pythonCode.get("argument", {})))
        
        self._validate_references(references, nodePool)

        for node_name, output_key in references:
            if [node_name, output_key] not in self._parents:
                self._parents.append([node_name, output_key])
            nodePool[node_name]._children.append(self.nodeName)
            # Remove duplicates
            nodePool[node_name]._children = list(set(nodePool[node_name]._children))

        return self._parents
    
    def resolve_references(self, input_str, nodePool):
        # Replace references in the input string with actual values from the node pool
        for node_name, output_key in self._parents:
            if node_name in nodePool and output_key in nodePool[node_name].outputSchema:
                try:
                    # Parent key
                    parent_key = nodePool[node_name]._outputs[output_key]
                    # Replace the reference with the actual value from the node pool
                    input_str = input_str.replace(f"@[{node_name}.{output_key}]", parent_key)
                    # Add the current node as a child of the referenced node
                    if f"@[{node_name}.{output_key}]" in input_str:
                        self._inputs[f"@[{node_name}.{output_key}]"] = parent_key
                except Exception as e:
                    LOGGER.error(f"Error replacing reference @{node_name}.{output_key}: {e}. Location: GraphNode.resolve_references")
                    # If there's an error, keep the original string
        return input_str
    

    def get_current_state(self, nodePool):
        nodeName = self.nodeName
        systemInstructions = self.resolve_references(self.systemInstructions, nodePool)
        userPrompt = self.resolve_references(self.userPrompt, nodePool)
        pythonCode = self.resolve_references(self.pythonCode.get("function_body", ""), nodePool)
        argument = self.pythonCode.get("argument", {})
        for key, value in argument.items():
            argument[key] = self.resolve_references(value, nodePool)
        outputs = self._outputs

        state = {
            "nodeName": nodeName,
            "systemInstructions": systemInstructions,
            "userPrompt": userPrompt,
            "pythonCode": {
                "function_body": pythonCode,
                "argument": argument
            },
            "outputs": outputs
        }

        return state

    def check_parent_status(self, nodePool):
        # Check if all parent nodes are completed
        for parent in self._parents:
            node_name, output_key = parent
            if node_name in nodePool:
                parent_node = nodePool[node_name]
                if output_key not in parent_node.outputSchema:
                    LOGGER.error(f"Output key '{output_key}' not found in parent node {node_name}. Location: GraphNode.check_parent_status")
                    raise ValueError(f"Output key '{output_key}' not found in parent node {node_name}.")
                    return False
                
                if parent_node.status != "completed":
                    LOGGER.warning(f"Parent node {node_name} of {self.nodeName} is not completed. Location: GraphNode.check_parent_status")
                    # raise ValueError(f"Parent node {node_name} of {self.nodeName} is not completed.")
                    return False
            else:
                LOGGER.error(f"Parent node {node_name} not found in node pool. Location: GraphNode.check_parent_status")
                raise ValueError(f"Parent node {node_name} not found in node pool.")
                return False
        return True
    
    def _validate_output(self, result):
        if result is None:
            LOGGER.error("Result is None. Location: GraphNode._validate_output")
            raise ValueError("Result is None.")
        # Validate the output against the output schema
        for key, value in self.outputSchema.items():
            if key not in result:
                LOGGER.error(f"Output key '{key}' not found in result. Location: GraphNode._validate_output")
                raise ValueError(f"Output key '{key}' not found in result.")
            if not isinstance(result[key], type(value)):
                raise ValueError(f"Output key '{key}' has incorrect type. Expected {type(value)}, got {type(result[key])}.")
        return True


    def execute(self, nodePool, python_env_manager: PythonEnvironmentManager):
        if self.status == "completed":
            LOGGER.warning(f"Node {self.nodeName} is already completed. Location: GraphNode.execute")
            return self._outputs
        
        if not self.check_parent_status(nodePool):
            LOGGER.warning(f"Parent nodes are not completed for {self.nodeName}. Location: GraphNode.execute")
            return None
        self.status = "running"
        # Execute the Python code with the resolved arguments
        state = self.get_current_state(nodePool)
        systemInstructions = state["systemInstructions"]
        userPrompt = state["userPrompt"]
        pythonFunctionBody = state["pythonCode"]["function_body"]
        pythonCodeArgument = state["pythonCode"]["argument"]

        if pythonFunctionBody != "" and python_env_manager is not None:
            # Prepare the arguments for output
            result = python_env_manager.execute_python_code(pythonFunctionBody, pythonCodeArgument)
            # Check if the result matches the output schema
            if not self._validate_output(result):
                LOGGER.error(f"Output does not match the schema for {self.nodeName}. Location: GraphNode.execute")
                return None
            # Store the result in _outputs
            self._outputs = result
        else:
            # If no Python code is provided, use the system instructions and user prompt (TODO: Implement this LLM logic)
            self._outputs = {
                k: f"LLM/{userPrompt}" for k, v in self.outputSchema.items()
            }
            
        self.status = "completed"
        return self._outputs

    def to_dict(self):
        # Convert the node to a dictionary representation
        key_value_pairs = {
            "nodeName": self.nodeName,
            "systemInstructions": self.systemInstructions,
            "userPrompt": self.userPrompt,
            "pythonCode": self.pythonCode,
            "outputSchema": self.outputSchema,
            "kwargs": self.kwargs,
            "id": self.id,
            "_compiled": self._compiled,
            "_parents": self._parents,
            "_children": self._children,
            "_inputs": self._inputs,
            "_outputs": self._outputs,
            "status": self.status
        }

        return key_value_pairs












class Graph:
    def __init__(self, timeout=10, venv_path=None, create_env=False, python_packages=[], save_dir=None):
        self.nodePool = {
        } # Dictionary to hold all nodes
        self.save_dir = save_dir
        self.graph_id = None
        self.conditions = defaultdict(threading.Condition)
        self.lock = threading.Lock()
        self.timeout = timeout # Timeout for node execution

        self.venv_path = venv_path
        self.python_packages = python_packages
        self.create_env = create_env

        if self.venv_path is not None:
            self.python_env_manager = PythonEnvironmentManager(self.venv_path, self.create_env)
            if python_packages:
                self.python_env_manager.install_dependencies(python_packages)
        else:
            self.python_env_manager = None

    def addInput(self, inputFields):
        # Add input fields to the graph
        if not isinstance(inputFields, dict):
            raise ValueError("Input fields must be a dictionary")
        
        for key, value in inputFields.items():
            if not isinstance(key, str):
                LOGGER.error(f"Key '{key}' in input fields must be a string")
                raise ValueError(f"Key '{key}' in input fields must be a string")
            if not isinstance(value, str):
                LOGGER.error(f"Value '{value}' in input fields must be a string")
                raise ValueError(f"Value '{value}' in input fields must be a string")
        
        new_node = GraphNode("inputs", "Input node", "Input node", {}, {**inputFields}, **inputFields)
        self.nodePool["inputs"] = new_node
        return new_node

    def addNode(self, nodeName, systemInstructions, userPrompt, pythonCode, outputSchema, **kwargs):
        # Add a new node to the graph
        if nodeName in self.nodePool:
            raise ValueError(f"Node with name {nodeName} already exists. Location: Graph.addNode")
        
        new_node = GraphNode(nodeName, systemInstructions, userPrompt, pythonCode, outputSchema, **kwargs)
        self.nodePool[nodeName] = new_node
        try:
            self.compile()
        except Exception as e:
            LOGGER.error(f"Error compiling graph after adding node {nodeName}: {e}. Location: Graph.addNode")
            self.removeNode(nodeName)
            raise ValueError(e)
        return new_node
    
    def removeNode(self, nodeName):
        # Remove a node from the graph
        if nodeName not in self.nodePool:
            raise ValueError(f"Node with name {nodeName} does not exist. Location: Graph.removeNode")
        
        # Remove the node from its parents' and children's lists
        for parent in self.nodePool[nodeName]._parents:
            parent_node = self.nodePool[parent[0]]
            if parent[1] in parent_node._children:
                parent_node._children.remove(nodeName)
        
        for child in self.nodePool[nodeName]._children:
            child_node = self.nodePool[child]
            for parent in child_node._parents:
                if parent[0] == nodeName:
                    child_node._parents.remove(parent)
        
        del self.nodePool[nodeName]
        LOGGER.info(f"Node {nodeName} removed from the graph. Location: Graph.removeNode")
        
        # Uncompile the graph
        self.reset_compiled_nodes()
        self.save_graph()
        LOGGER.info(f"Graph reset after removing node {nodeName}. Location: Graph.removeNode")
        return True
    
    def updateNode(self, nodeName, systemInstructions, userPrompt, pythonCode, outputSchema, **kwargs):
        # Update an existing node in the graph
        if nodeName not in self.nodePool:
            raise ValueError(f"Node with name {nodeName} does not exist. Location: Graph.updateNode")
        
        # Dlelete the node from the graph
        self.removeNode(nodeName)

        # Add the updated node
        new_node = GraphNode(nodeName, systemInstructions, userPrompt, pythonCode, outputSchema, **kwargs)
        self.nodePool[nodeName] = new_node

        # Reset the compliation status of the graph
        self.reset_compiled_nodes()

        return True
    
    def getNode(self, nodeName):
        # Retrieve a node from the graph
        if nodeName not in self.nodePool:
            raise ValueError(f"Node with name {nodeName} does not exist. Location: Graph.getNode")
        
        return self.nodePool[nodeName]
    
    def compile(self):
        # Compile the graph by checking dependencies and setting parent-child relationships
        for node in self.nodePool.values():
            self.nodePool[node.nodeName].resolve_parent_nodes(self.nodePool)
            node._compiled = True

        self.check_circular_dependency()

        # Gnerate a unique graph ID from the node hashes
        node_hashes = [node.hash() for node in self.nodePool.values()]
        self.graph_id = hashlib.sha256("".join(node_hashes).encode()).hexdigest()
        LOGGER.info(f"Graph compiled with ID: {self.graph_id}. Location: Graph.compile")
        self.save_graph()

    def reset_compiled_nodes(self):
        # Reset the compiled status of all nodes
        for node in self.nodePool.values():
            if node.nodeName == "inputs":
                continue
            node._compiled = False
            node.status = "pending"
            node._parents = []
            node._children = []
            node._inputs = {}
            node._outputs = {}
        LOGGER.info("All nodes reset to uncompiled state. Location: Graph.reset_compiled_nodes")
        self.save_graph()
        
    def check_circular_dependency(self):
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
        # Print the graph in a readable format
        for node in self.nodePool.values():
            print(node.to_dict())
        print("\n")

    def _execute_node_with_condition(self, node, timeout, involved_nodes):
        start_time = time.time()
        condition = self.conditions[node.nodeName]

        with condition:
            while not node.check_parent_status(self.nodePool):
                remaining = timeout - (time.time() - start_time)
                if remaining <= 0:
                    LOGGER.warning(f"Timeout reached for node {node.nodeName}. Location: Graph._execute_node_with_condition")
                    raise TimeoutError(f"Node {node.nodeName} timed out.")
                LOGGER.debug(f"Node {node.nodeName} is waiting for parent nodes to complete. Location: Graph._execute_node_with_condition")
                condition.wait(timeout=remaining)

        with self.lock:
            involved_nodes.add(node.nodeName)
            LOGGER.info(f"Running node: {node.nodeName}. Location: Graph._execute_node_with_condition")
            result = node.execute(self.nodePool, self.python_env_manager)
            LOGGER.info(f"Completed node: {node.nodeName} with result: {result} . Location: Graph._execute_node_with_condition")

        # Notify all waiting threads
        for child in node._children:
            if self.nodePool[child].check_parent_status(self.nodePool):
                with self.lock:
                    with self.conditions[child]:
                        self.conditions[child].notify_all()

    def _traverse_nodes(self, start_node):
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


        threads = []
        involved_nodes = set()

        try:
            for node_name in visited:
                node = self.nodePool[node_name]
                if node.status == "pending":
                    thread = threading.Thread(target=self._execute_node_with_condition, args=(node, self.timeout, involved_nodes))
                    threads.append(thread)
                    thread.start()
                    LOGGER.info(f"Thread started for node: {node_name} . Location: Graph.execute_from_node")
            
            for thread in threads:
                thread.join()
        except TimeoutError as e:
            LOGGER.critical(f"Timeout error: {e}")
            for node_name in involved_nodes:
                node = self.nodePool[node_name]
                if node.status == "running":
                    node.status = "completed"
                    LOGGER.warning(f"Node {node_name} status set to completed due to timeout. Location: Graph.execute_from_node")
            for node_name in involved_nodes:
                node = self.nodePool[node_name]
                if node.status == "running":
                    node.status = "completed"
                    LOGGER.warning(f"Node {node_name} status set to completed due to timeout. Location: Graph.execute_from_node")
            LOGGER.error(f"Error during execution: {e}")
            
        finally:
            for node_name in visited:
                node = self.nodePool[node_name]
                if node.status == "running":
                    node.status = "completed"
                    LOGGER.info(f"Node {node_name} status set to completed. Location: Graph.execute_from_node")
            LOGGER.info("Execution completed for all nodes. Location: Graph.execute_from_node")

        self.save_graph()

    def to_dict(self):
        # Convert the graph to a dictionary representation
        graph_dict = {
            "graph_id": self.graph_id,
            "nodes": {node_name: node.to_dict() for node_name, node in self.nodePool.items()},
            "venv_path": self.venv_path,
            "python_packages": self.python_packages,
            "create_env": self.create_env
        }
        return graph_dict

    def save_graph(self):
        # Save the graph to a JSON file
        if not self.save_dir:
            LOGGER.error("Save directory is not set. Location: Graph.save_graph")
            raise ValueError("Save directory is not set. Location: Graph.save_graph")
        file_path = os.path.join(self.save_dir, f"graph.json")
        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=4)
        LOGGER.info(f"Graph saved to {file_path}. Location: Graph.save_graph")

    def load_graph(self):
        # Load the graph from a JSON file
        file_path = os.path.join(self.save_dir, f"graph.json")
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                for node_name, node_data in data["nodes"].items():
                    node = GraphNode(
                        node_data["nodeName"],
                        node_data["systemInstructions"],
                        node_data["userPrompt"],
                        node_data["pythonCode"],
                        node_data["outputSchema"],
                        **node_data["kwargs"]
                    )
                    # Set the node's properties
                    node._compiled = node_data["_compiled"]
                    node._parents = node_data["_parents"]
                    node._children = node_data["_children"]
                    node._inputs = node_data["_inputs"]
                    node._outputs = node_data["_outputs"]
                    node.status = node_data["status"]
                    
                    # Add the node to the node pool
                    self.nodePool[node_name] = node

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
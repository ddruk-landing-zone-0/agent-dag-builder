from .logger import LOGGER
from .pyenv_manager import PythonEnvironmentManager
import hashlib
import re



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

        # inputs are always set to completed
        if nodeName=="inputs":
            self.status = "running"
            self._outputs = {**kwargs}
            self.status = "completed"
    
    def _validate(self):
        """
        Validate the properties of the GraphNode instance.
        """
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
            
    
    def _validate_references(self, parent_list, nodePool):
        """
        Validate the references to parent nodes in the node pool.
        Input:
            parent_list: List of parent nodes in the format [nodeName, outputKey]
            nodePool: Dictionary of all nodes in the graph
        Output:
            True if all references are valid, raises ValueError otherwise
        """
        for parent in parent_list:
            if parent[0] not in nodePool:
                LOGGER.error(f"Parent node {parent[0]} not found in node pool. Location: GraphNode._validate_parent")
                raise ValueError(f"Parent node {parent[0]} not found in node pool.")
            if parent[1] not in nodePool[parent[0]].outputSchema:
                LOGGER.error(f"Output key '{parent[1]}' not found in parent node {parent[0]}. Location: GraphNode._validate_parent")
                raise ValueError(f"Output key '{parent[1]}' not found in parent node {parent[0]}.")
        return True


    def _validate_output(self, result):
        """
        Validate the output of the node against the output schema. Expects a dictionary with string keys and values.
        Input:
            result: The result of the node's execution
        Output:
            True if the output matches the schema, raises ValueError otherwise
        """
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



    def hash(self):
        # Generate a hash for the node based on its properties
        node_string = f"{self.nodeName}{self.systemInstructions}{self.userPrompt}{self.pythonCode}{str(self.outputSchema)}{str(self.kwargs)}"
        return hashlib.sha256(node_string.encode()).hexdigest()
    
    def resolve_parent_nodes(self, nodePool):
        """
        Resolve the parent nodes of the current node by finding references in the system instructions, user prompt, and Python code.
        Input:
            nodePool: Dictionary of all nodes in the graph. This is prvided from the Graph class
        Output:
            List of parent nodes in the format [nodeName, outputKey]
        """

        self._parents = []
        pattern = r'@\[(\w+)\.(\w+)\]' # Regex pattern to match references in the format @[nodeName.outputKey]
        
        # Creates a list of references of the form [nodeName, outputKey] from the system instructions, user prompt, and Python code
        references = re.findall(pattern, self.systemInstructions)
        references += re.findall(pattern, self.userPrompt)
        references += re.findall(pattern, self.pythonCode.get("function_body", ""))
        references += re.findall(pattern, str(self.pythonCode.get("argument", {})))
        
        # Check if the references are valid i.e. if the node names and output keys exist in the node pool
        self._validate_references(references, nodePool)

        # Add the references to the _parents list and update the _children list of the referenced nodes
        for node_name, output_key in references:
            # Handle duplicate parent references
            if [node_name, output_key] not in self._parents:
                self._parents.append([node_name, output_key])
            # Add the current node as a child of the referenced node
            nodePool[node_name]._children.append(self.nodeName)
            # Remove duplicate children
            nodePool[node_name]._children = list(set(nodePool[node_name]._children))

        return self._parents
    
    def resolve_references(self, input_str, nodePool):
        """
        Resolve references in the input string by replacing them with actual values from the node pool.
        Input:
            input_str: The input string containing references in the format @[nodeName.outputKey]
            nodePool: Dictionary of all nodes in the graph
        Output:
            The input string with references replaced by actual values from the node pool

        Example:
            input_str = "The result is @[node1.outputKey1]"
            
            resolve_references(input_str, nodePool) => "The result is value"

            where value is the output of node1 with the key outputKey1
        """
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
        """
        Get the current state of the node, including resolved references and outputs.
        Input:
            nodePool: Dictionary of all nodes in the graph
        Output:
            Dictionary containing the current state of the node
        """
        nodeName = self.nodeName # str: Name of the node
        systemInstructions = self.resolve_references(self.systemInstructions, nodePool) # Replace references in the system instructions
        userPrompt = self.resolve_references(self.userPrompt, nodePool) # Replace references in the user prompt
        pythonCode = self.resolve_references(self.pythonCode.get("function_body", ""), nodePool) # Replace references in the Python code
        argument = self.pythonCode.get("argument", {}) # Replace references in the Python code arguments
        for key, value in argument.items():
            argument[key] = self.resolve_references(value, nodePool) # Replace references in the Python code arguments

        outputs = self._outputs # Get the outputs of the node

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
        """
        Check the status of parent nodes to ensure they are completed before executing the current node.
        Input:
            nodePool: Dictionary of all nodes in the graph
        Output:
            True if all parent nodes are completed, raises ValueError otherwise
        """
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

    def execute(self, nodePool, python_env_manager: PythonEnvironmentManager):
        """
        Execute the node by running the Python code or generating output based on the system instructions and user prompt using LLM.
        """

        # Check if the node is already completed
        if self.status == "completed":
            LOGGER.warning(f"Node {self.nodeName} is already completed. Location: GraphNode.execute")
            return self._outputs
        
        # Check if parent nodes are completed
        if not self.check_parent_status(nodePool):
            LOGGER.warning(f"Parent nodes are not completed for {self.nodeName}. Location: GraphNode.execute")
            return None
        
        # Set the status to running
        self.status = "running"

        # Execute the Python code with the resolved arguments

        # Get the current state of the node
        state = self.get_current_state(nodePool)
        systemInstructions = state["systemInstructions"]
        userPrompt = state["userPrompt"]
        pythonFunctionBody = state["pythonCode"]["function_body"]
        pythonCodeArgument = state["pythonCode"]["argument"]

        # Check if the Python code is provided
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
            
        # Set the status to completed
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






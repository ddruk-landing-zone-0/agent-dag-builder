from .logger import LOGGER
from .pyenv_manager import PythonEnvironmentManager
import hashlib
import re

from ..llms.gemini import GeminiJsonEngine, GeminiSimpleChatEngine
from ..llms.openai import LangchainOpenaiJsonEngine, LangchainOpenaiSimpleChatEngine


class GraphNode:
    def __init__(self, nodeName, systemInstructions, userPrompt, pythonCode, outputSchema, useLLM, jsonMode, toolName, toolDescription, **kwargs):
        
        self.nodeName = nodeName # str: Name of the node
        self.pythonCode = pythonCode # str: Python code to be executed
        self.outputSchema = outputSchema # Dict: Schema for the output of the node. Dictionary to a dictionary with string keys and values
        self.kwargs = kwargs # Additional keyword arguments for flexibility

        # LLM Specific
        self.useLLM = useLLM # bool: Flag to indicate if the node uses LLM ( Resolved from user input )
        self.jsonMode = jsonMode # bool: Flag to indicate if the node uses JSON mode ( Resolved from user input )
        self.toolName = toolName # str: Name of the tool to be used ( Resolved from user input )
        self.toolDescription = toolDescription # str: Description of the tool to be used ( Resolved from user input )
        self.systemInstructions = systemInstructions # str: Instructions for the system or the system prompt
        self.userPrompt = userPrompt # str: User prompt or question can include reference to other nodes


        self._validate() # Validate the node's properties
        self.id = self.hash() # str: Unique identifier for the node

        self._compiled = False # bool: Flag to indicate if the node has been compiled
        self._parents = [] # List: Parent nodes
        self._children = [] # List: Child nodes

        self._inputs = {} # It is a mutable mapping of input names to their values where the keys are the output keys of the parent nodes' outputs
        self._outputs = {} # It is a mutable mapping of output names to their values where the keys are the output keys of the current node's outputs

        self.status = "pending" # str: Status of the node, can be "pending", "running" or "completed" or "waiting" or "error"

        # inputs are always set to completed
        if nodeName=="inputs":
            self.status = "running"
            self._outputs = {**outputSchema} # It seems weird. But we set the output values to the description of the output schema
            self.status = "completed"

        self.engine = None # LLM Engine object: The LLM engine to be used for generating output ( Resolved while compiling the graph )

    
    def _validate(self):
        """
        Validate the properties of the GraphNode instance.
        """
        # Validate the node's properties
        if not isinstance(self.nodeName, str):
            LOGGER.error("nodeName must be a string. Location: GraphNode._validate")
            raise ValueError("nodeName must be a string")
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
        


        # Validate LLM specific properties
        if not isinstance(self.useLLM, bool):
            LOGGER.error("useLLM must be a boolean. Location: GraphNode._validate")
            raise ValueError("useLLM must be a boolean")
        if not isinstance(self.jsonMode, bool):
            LOGGER.error("jsonMode must be a boolean. Location: GraphNode._validate")
            raise ValueError("jsonMode must be a boolean")
        if not isinstance(self.toolName, str):
            LOGGER.error("toolName must be a string. Location: GraphNode._validate")
            raise ValueError("toolName must be a string")
        if not isinstance(self.toolDescription, str):
            LOGGER.error("toolDescription must be a string. Location: GraphNode._validate")
            raise ValueError("toolDescription must be a string")
        if not isinstance(self.systemInstructions, str):
            LOGGER.error("systemInstructions must be a string. Location: GraphNode._validate")
            raise ValueError("systemInstructions must be a string")
        if not isinstance(self.userPrompt, str):
            LOGGER.error("userPrompt must be a string. Location: GraphNode._validate")
            raise ValueError("userPrompt must be a string")


        for key, value in self.kwargs.items():
            if not isinstance(key, str):
                LOGGER.error(f"Key '{key}' in kwargs must be a string. Location: GraphNode._validate")
                raise ValueError(f"Key '{key}' in kwargs must be a string")
            # if not isinstance(value, str):
            #     LOGGER.error(f"Value '{value}' in kwargs must be a string. Location: GraphNode._validate")
            #     raise ValueError(f"Value '{value}' in kwargs must be a string")
            
    
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
                LOGGER.error(f"Cur Node: {self.nodeName} // Parent node {parent[0]} not found in node pool. Location: GraphNode._validate_references")
                return False
                # raise ValueError(f"Cur Node: {self.nodeName}Parent node {parent[0]} not found in node pool.")
            if parent[1] not in nodePool[parent[0]].outputSchema:
                LOGGER.error(f"Cur Node: {self.nodeName} // Parent node {parent[0]} // Output key '{parent[1]}' not found in parent node {parent[0]}. Location: GraphNode._validate_references")
                return False
                # raise ValueError(f"Cur Node: {self.nodeName} // Parent node {parent[0]} // Output key '{parent[1]}' not found in parent node {parent[0]}.")
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

    def resolve_engine(self):
        if self.useLLM:
            if self.systemInstructions is not None and self.userPrompt is not None and self.systemInstructions != "" and self.userPrompt != "":
                
                model_name = self.kwargs.get("model_name", "gemini-2.0-flash-001")
                temperature = self.kwargs.get("temperature", 0.5)
                max_output_tokens = self.kwargs.get("max_tokens", 1000)
                max_retries = self.kwargs.get("max_retries", 5)
                wait_time = self.kwargs.get("wait_time", 30)
                deployed_gcp = self.kwargs.get("deployed_gcp", False)

                if len(self.outputSchema.keys()) == 0:
                    raise ValueError("outputSchema must have at least one key for LLM mode.")

                if self.jsonMode:
                    if self.toolName is not None and self.toolDescription is not None:
                        basemodel = {
                            "tool_name": self.toolName,
                            "description" : self.toolDescription,
                            "output_schema": {
                                **self.outputSchema
                            }
                        }
                        if "gemini" in model_name:
                            self.engine = GeminiJsonEngine(
                                model_name=model_name,
                                basemodel=basemodel,
                                temperature=temperature,
                                max_output_tokens=max_output_tokens,
                                systemInstructions=self.systemInstructions,
                                max_retries=max_retries,
                                wait_time=wait_time,
                                deployed_gcp=deployed_gcp
                            )
                        elif "gpt" in model_name:
                            self.engine = LangchainOpenaiJsonEngine(
                                model_name=model_name,
                                sampleBaseModel=basemodel,
                                temperature=temperature,
                                systemPromptText=self.systemInstructions
                            )

                    else:
                        raise ValueError("toolName and toolDescription must be provided for JSON mode.")
                else:
                    if len(self.outputSchema.keys()) > 1:
                        raise ValueError("outputSchema must have only one key for Non JSON LLM mode.")
                        
                    if "gemini" in model_name:
                        self.engine = GeminiSimpleChatEngine(
                            model_name=model_name,
                            temperature=temperature,
                            max_output_tokens=max_output_tokens,
                            systemInstructions=self.systemInstructions,
                            max_retries=max_retries,
                            wait_time=wait_time,
                            deployed_gcp=deployed_gcp
                        )
                    elif "gpt" in model_name:
                        self.engine = LangchainOpenaiSimpleChatEngine(
                            model_name=model_name,
                            temperature=temperature,
                            systemPromptText=self.systemInstructions
                        )
            else:
                raise ValueError("systemInstructions and userPrompt must be provided for LLM mode.")

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
        success_validate_references = self._validate_references(references, nodePool)

        if not success_validate_references:
            return None

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
                    # Add the current node as a child of the referenced node
                    if f"@[{node_name}.{output_key}]" in input_str:
                        self._inputs[f"@[{node_name}.{output_key}]"] = parent_key

                    input_str = input_str.replace(f"@[{node_name}.{output_key}]", parent_key)
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
        args_replaced = {}
        for key, value in argument.items():
            args_replaced[key] = self.resolve_references(value, nodePool) # Replace references in the Python code arguments

        outputs = self._outputs # Get the outputs of the node

        state = {
            "nodeName": nodeName,
            "systemInstructions": systemInstructions,
            "userPrompt": userPrompt,
            "pythonCode": {
                "function_body": pythonCode,
                "argument": args_replaced
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

        try:
            # Get the current state of the node
            state = self.get_current_state(nodePool)
            userPrompt = state["userPrompt"]
            pythonFunctionBody = state["pythonCode"]["function_body"]
            pythonCodeArgument = state["pythonCode"]["argument"]

            # Check if the Python code is provided
            if self.useLLM is False:
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
                if self.engine is None:
                    self.resolve_engine()
                
                # Generate output using LLM
                engine_result = self.engine.run([
                    userPrompt
                ])
                
                result = {}
                if self.jsonMode:
                    # Parse the JSON output
                    try:
                        # In case of JSON mode, the output is expected to be a list of dictionaries
                        result = engine_result[0]
                    except Exception as e:
                        LOGGER.error(f"Error parsing JSON output: {e}. Location: GraphNode.execute")
                        raise ValueError(f"Error parsing JSON output: {e}")
                else:
                    # Parse the output for non-JSON mode
                    try:
                        # In case of non-JSON mode, the output is expected to be a string and outputSchema is a dictionary with only one key
                        result = {output_key: engine_result for output_key in self.outputSchema.keys()}
                    except Exception as e:
                        LOGGER.error(f"Error parsing output: {e}. Location: GraphNode.execute")
                        raise ValueError(f"Error parsing output: {e}")
                
                # Check if the result matches the output schema
                if not self._validate_output(result):
                    LOGGER.error(f"Output does not match the schema for {self.nodeName}. Location: GraphNode.execute")
                    return None
                
                # Store the result in _outputs
                self._outputs = result
                
            # Set the status to completed
            self.status = "completed"

        except Exception as e:
            LOGGER.critical(f"Error executing node {self.nodeName}: {e}. Location: GraphNode.execute")
            self.status = "error"
            self._outputs = {"error": f"Error executing node {self.nodeName}: {e}. Location: GraphNode.execute"}

        return self._outputs

    def to_dict(self):
        # Convert the node to a dictionary representation
        key_value_pairs = {
            "nodeName": self.nodeName,
            "systemInstructions": self.systemInstructions,
            "userPrompt": self.userPrompt,
            "pythonCode": self.pythonCode,
            "outputSchema": self.outputSchema,
            "useLLM": self.useLLM,
            "jsonMode": self.jsonMode,
            "toolName": self.toolName,
            "toolDescription": self.toolDescription,
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






from pydantic import BaseModel, Field
from typing import List, Dict, Any, Type


####################################################################################################
# The following code is used to generate the function declaration for the GeminiModel class.
# IT receives a Pydantic model schema and converts it to the required format for the function declaration.
# It recursively processes the properties of the schema, resolving references if needed.
####################################################################################################

def pydantic_schema_to_tool_format(schema: Type[BaseModel]) -> Dict[str, Any]:
    """
    Convert a Pydantic model schema to the required function declaration format, 
    handling nested schemas with $refs.

    :param schema: Pydantic model class
    :return: Dictionary in the required format
    """
    try:
        schema_dict = schema.model_json_schema()
    except AttributeError:
        # Version Issue: model_json_schema() is not available in Pydantic some version
        schema_dict = schema.schema_json()

    defs = schema_dict.get("$defs", {})  # Extract nested schema definitions

    def resolve_ref(ref: str) -> Dict[str, Any]:
        """
        Resolve a $ref reference from the schema.
        """
        ref_key = ref.split("/")[-1]  # Extract the referenced key
        return defs.get(ref_key, {})  # Return the resolved schema

    def process_properties(properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively process the properties of the schema, resolving references if needed.
        """
        processed = {}
        for key, value in properties.items():
            value.pop("title", None)  # Remove unnecessary 'title' field
            
            # Resolve references
            if "$ref" in value:
                value = resolve_ref(value["$ref"])

            # If the property is an object with properties, process recursively
            if value.get("type") == "object" and "properties" in value:
                value["properties"] = process_properties(value["properties"])

            # If the property is an array and references an object, resolve it
            elif value.get("type") == "array" and "items" in value:
                if "$ref" in value["items"]:  # If items reference another object
                    value["items"] = resolve_ref(value["items"]["$ref"])
                if "properties" in value["items"]:  # Process nested object in list
                    value["items"]["properties"] = process_properties(value["items"]["properties"])

            processed[key] = value
        
        return processed

    return {
        "name": schema_dict["title"].replace("Params", "").lower(),  # Convert class name to lowercase
        "description": schema_dict.get("description", ""),
        "parameters": {
            "type": "object",
            "properties": process_properties(schema_dict["properties"]),
            "required": schema_dict.get("required", [])
        }
    }



def dict_to_tool_format(tool_dict):
    # Normalize tool name to lowercase
    tool_name = tool_dict.get("tool_name", "").lower()
    
    # Extract description
    description = tool_dict.get("description", "")
    
    # Extract output_schema and build the parameters object
    output_schema = tool_dict.get("output_schema", {})
    properties = {
        key: {
            "description": desc,
            "type": "string"
        }
        for key, desc in output_schema.items()
    }
    required = list(output_schema.keys())
    
    # Build the final transformed dictionary
    converted = {
        "name": tool_name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required
        }
    }
    
    return converted
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage,ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any, List
from .utils.tool_formatter import dict_to_pydantic_model


####################################################################################################
# The following code is used to generate the function declaration for the LangchainOpenaiJsonEngine class.
# It initializes a GPT 3.5 Turbo model and binds it to a Pydantic model schema.
# It ensures a structured JSON output from the model following the Pydantic model schema.
####################################################################################################

class LangchainOpenaiJsonEngine:
    def __init__(self, model_name, sampleBaseModel, systemPromptText: str=None, humanPromptText: str=None, temperature: float=0.0):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)

        if isinstance(sampleBaseModel, dict):
            sampleBaseModel = dict_to_pydantic_model(sampleBaseModel)

        self.structured_llm = self.llm.with_structured_output(sampleBaseModel)
        
        if systemPromptText is None:
            self.systemPromptText = """
            You are an AI assistant. You are helping a user with a task. The user is asking you questions and you are answering them.
            """
        else:
            self.systemPromptText = systemPromptText

        if humanPromptText is None:
            self.HumanPromptText = """
            Human: {query}
            """
        else:
            self.humanPromptText = humanPromptText

        self.prompt = ChatPromptTemplate.from_messages(
            [("system", self.systemPromptText), ("human", "Query:\n\n {query}")])
        
        self.micro_agent = self.prompt | self.structured_llm

    def run(self, query: List[str]):
        query = "\n".join(query)
        result = self.micro_agent.invoke({
            "query": query
        })
        return [dict(result)]


####################################################################################################
# The following code is used to generate the function declaration for the LangchainOpenaiSimpleChatEngine class.
# It initializes a GPT 3.5 Turbo model and binds it to a list of tools.
# It runs the tools and the model in sequence to generate a response.
####################################################################################################

class LangchainOpenaiSimpleChatEngine:
    def __init__(self, model_name, tools:List[tool]=[], systemPromptText: str=None, humanPromptText: str=None, temperature: float=0.0):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.tools = tools
        
        if len(tools) == 0:
            self.llm_with_tools = self.llm
        else:
            self.llm_with_tools = self.llm.bind_tools(tools)
            
        if systemPromptText is None:
            self.systemPromptText = """
            You are an AI assistant. You are helping a user with a task. The user is asking you questions and you are answering them.
            """
        else:
            self.systemPromptText = systemPromptText

        if humanPromptText is not None: 
            print("Skipping human prompt text ...")

    def run(self, query: List[str]):
        query = "\n".join(query)

        messages = [
            SystemMessage(self.systemPromptText),
            HumanMessage(content=query)
        ]
        level1_result = self.llm_with_tools.invoke(messages)
        if len(level1_result.tool_calls) == 0:
            print("No tools to run ...")
            return level1_result.content
        else:
            print("Running tools ...")
            for tool_call in level1_result.tool_calls:
                tool_output = tool_call.invoke()
                messages.append(ToolMessage(tool_output, tool_call_id=tool_call["id"]))
            level2_result = self.llm_with_tools.invoke(messages)
            return level2_result.content
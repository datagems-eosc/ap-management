from typing import List, Optional

import litellm
from agent_framework import Agent
from agent_framework.openai import OpenAIChatCompletionClient
from litellm import Message, completion
from pydantic import BaseModel


class LLM:
    """
    A generic class to call LLMs 
    """

    def __init__(self, api_base: str, model: str, api_key: Optional[str] = None, *, ssl_verify: bool = True):
        self.api_base = api_base
        self.model = model
        self.api_key = api_key

        # Some LLM Api use self-signed certificates
        litellm.ssl_verify = ssl_verify

    def completion[T: BaseModel](self, messages: List[Message], response_format: type[T], *, timeout: int = 60) -> T:
        response = completion(
            api_base=self.api_base,
            # Do not pass api_key if it's None, litellm will complain
            **({"api_key": self.api_key} if self.api_key else {}),
            model=self.model,
            messages=messages,
            response_format=response_format,
            timeout=timeout,
        )

        return response_format.model_validate_json(response.choices[0].message.content)

    def create_agent(self, name: str, instructions: str, tools: Optional[dict] = None, max_tool_iterations: int = 5) -> Agent:
        return OpenAIChatCompletionClient(
            api_key=self.api_key,
            base_url=self.api_base,
            # Use the model name without the path, e.g. "gpt-4" instead of "openai/gpt-4"
            model=self.model.split("/")[-1],
            function_invocation_configuration={"max_iterations": max_tool_iterations},
        ).as_agent(
            name=name,
            instructions=instructions,
            tools=tools,
        )

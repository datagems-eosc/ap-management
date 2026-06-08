from typing import List, Optional

import litellm
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

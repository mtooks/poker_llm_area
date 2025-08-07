import os
import env
from pathlib import Path
from dotenv import load_dotenv
from .base_player import BasePlayer
from xai_sdk import Client
from xai_sdk.chat import user,system    

class GrokPlayer(BasePlayer):
    def __init__(self, 
                name: str, 
                model: str, 
                initial_stack: int = 400, 
                system_prompt: str = None):
        super().__init__(name, model, initial_stack, system_prompt)

        self.client = Client(api_key=os.getenv("GROK_API_KEY"),timeout = 100)

    def _setup_grok_client(self):
        env_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / '.env'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            
        grok_key = os.getenv("GROK_KEY", "")
        if not grok_key:
            raise ValueError("GROK_KEY environment variable is not set")
        self.client = Client(api_key=os.getenv("GROK_API_KEY"),timeout = 100)

    def _chat(self, messages):
        chat = self.client.chat.create(model = 'grok-4')
        chat.append(system(self._get_default_system_prompt()))
        chat.append(user(messages))

        response = chat.sample()
        print(response)
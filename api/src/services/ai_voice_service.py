import asyncio
from openai import AsyncAzureOpenAI
from azure.core.credentials import AzureKeyCredential

from src.config.settings import Config

## TODO: Implement use of interface for AI Voice Service
class AIVoiceService:
    def __init__(self, config: Config):
        self.config = config
        self.aoai_client = AsyncAzureOpenAI(
            endpoint=config.AZURE_OPENAI_SERVICE_ENDPOINT,
            key=AzureKeyCredential(config.AZURE_OPENAI_SERVICE_KEY),
            deployment_model=config.AZURE_OPENAI_DEPLOYMENT_MODEL_NAME
        )

    async def start_conversation(self):
        pass
from api.src.services.openai_service import get_chat_completions_async, has_intent_async
import os
import jinja2
from datetime import datetime
import asyncio
from dotenv import load_dotenv

load_dotenv(override=True)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "api\src\prompts")
JINJA_ENV = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES_DIR))

azure_cognitive_service_endpoint = os.environ["COGNITIVE_SERVICE_ENDPOINT"]
azure_openai_deployment_model_name = os.environ["AZURE_OPENAI_SEARCHAGENT_DEPLOYMENT"]
azure_openai_service_key = os.environ["AZURE_OPENAI_API_KEY"]
azure_openai_service_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
azure_openai_api_version = os.environ["AZURE_OPENAI_API_VERSION"]


# ——— Agent instructions ———
instruction_template = JINJA_ENV.get_template("instructions.jinja")
instructions = instruction_template.render(
    current_date=datetime.now().strftime("%Y-%m-%d"),
)

async def main():
    # print(await get_chat_completions_async(
    #     instructions,
    #     "What is the weather like today?",
    #     azure_openai_deployment_model_name,
    #     azure_openai_service_key,
    #     azure_openai_service_endpoint,
    #     azure_openai_api_version
    # ))

    print( await has_intent_async(
        "What is the weather like today?",
        "talk to agent",
        azure_openai_deployment_model_name,
        azure_openai_service_key,
        azure_openai_service_endpoint,
        azure_openai_api_version
    ))

if __name__ == "__main__":
    asyncio.run(main())

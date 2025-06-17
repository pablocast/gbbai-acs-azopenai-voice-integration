from typing import List, Dict, Any, Optional
from openai import AsyncAzureOpenAI
from azure.identity import DefaultAzureCredential
from azure.search.documents.aio import SearchClient
from azure.communication.callautomation import (
    PhoneNumberIdentifier,
    RecognizeInputType,
    TextSource,
)
from azure.search.documents.agent.aio import KnowledgeAgentRetrievalClient
import os
import logging
from pydantic import BaseModel, Field
import json
from src.tools.tool_base import (
    _search_tool,
    _inform_loan_tool
)

search_endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
search_index = os.environ["AZURE_SEARCH_INDEX"]
credentials = DefaultAzureCredential()
search_client = SearchClient(
    search_endpoint, search_index, credentials, user_agent="my-user-agent"
)

agent_client = KnowledgeAgentRetrievalClient(
    search_endpoint, "voicerag-intvect-agent", credentials
)

tools = {
    "search": lambda args: _search_tool(
        agent_client,
        search_index_name="voicerag-intvect",
        reranker_threshold=2.2,
        max_docs_for_reranker=100,
        filter_add_on=None,
        args=args,
    ),
    "inform_loan": _inform_loan_tool,
}


class ResponseFormat(BaseModel):
    content: str = Field(..., description="Responda à consulta do cliente de forma breve e clara em duas linhas e pergunte se há algo mais com que você possa ajudar", min_length=1, max_length=1000)
    score: int = Field(..., description="Pontuação de sentimento com base no tom do cliente", ge=0, le=10)
    intent: str = Field(..., description="Intenção identificada na consulta do cliente")
    category: str = Field(..., description="Classifique a intenção em uma das categorias")

class IntentFormat(BaseModel):
    agent_intent: bool = Field(..., description="Intenção de falar com um agente humano")


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_chat_completions_async(
    system_prompt,
    user_prompt,
    azure_openai_deployment_model_name,
    azure_openai_service_key,
    azure_openai_service_endpoint,
    azure_openai_api_version,
    tools_description=None,
    tool_choice="auto"
):
    client = AsyncAzureOpenAI(
        api_key=azure_openai_service_key,
        api_version=azure_openai_api_version,
        azure_endpoint=azure_openai_service_endpoint,
    )

    # Define your chat completions request
    chat_request = [
        {"role": "system", "content": f"{system_prompt}"},
        {
            "role": "user",
            "content": f" Respond to this question: {user_prompt}?",
        },
    ]
    global response_content
    try:
        response = await client.chat.completions.create(
            model=azure_openai_deployment_model_name,
            messages=chat_request,
            max_tokens=1000,
            tools=tools_description,
            tool_choice=tool_choice
        )

        response_message = response.choices[0].message
        chat_request.append(response_message)
        print(f"Response: {response_message.content}")
         # Handle function calls
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                print(f"Tool call: {tool_call.function.name}")
                args = json.loads(tool_call.function.arguments)
                print(f"Function arguments: {args}")  

                function = tools.get(
                    tool_call.function.name
                )

                function_response = await function(
                    args
                )

                print(f"Function result: {function_response}")

                chat_request.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": "get_current_time",
                    "content": function_response,
                })
        else:
            print("No tool calls were made by the model.")  

        # Second API call: Get the final response from the model
        final_response = await client.beta.chat.completions.parse(
            model=azure_openai_deployment_model_name,
            messages=chat_request,
            max_tokens=1000,
            response_format=ResponseFormat
        )

    except Exception as ex:
        logger.error("error in openai api call : %s", ex)

    # Extract the response content
    if response is not None:
        response_content = final_response.choices[0].message.content
    else:
        response_content = ""
    return response_content

async def handle_recognize(
    call_automation_client,
    replyText,
    callerId,
    call_connection_id,
    voice_name,
    context="",
):
    play_source = TextSource(text=replyText, voice_name=voice_name)
    connection_client = call_automation_client.get_call_connection(call_connection_id)
    try:
        recognize_result = await connection_client.start_recognizing_media(
            input_type=RecognizeInputType.SPEECH,
            target_participant=PhoneNumberIdentifier(callerId),
            end_silence_timeout=0.2,
            play_prompt=play_source,
            operation_context=context,
            speech_language="pt-BR",
        )
        logger.info("handle_recognize : data=%s", recognize_result)
    except Exception as ex:
        logger.info("Error in recognize: %s", ex)


async def handle_play(
    call_automation_client, call_connection_id, text_to_play, voice_name, context
):
    play_source = TextSource(text=text_to_play, voice_name=voice_name)
    await call_automation_client.get_call_connection(
        call_connection_id
    ).play_media_to_all(play_source, operation_context=context)


async def handle_hangup(call_automation_client, call_connection_id):
    await call_automation_client.get_call_connection(call_connection_id).hang_up(
        is_for_everyone=True
    )

async def has_intent_async(
    user_query,
    intent_description,
    azure_openai_deployment_model_name,
    azure_openai_service_key,
    azure_openai_service_endpoint,
    azure_openai_api_version,
):
    is_match = False
    system_prompt = "You are a helpful assistant"
    combined_prompt = (
        f"does {user_query} have a similar meaning as {intent_description}"
    )
    # combined_prompt = base_user_prompt.format(user_query, intent_description)
    client = AsyncAzureOpenAI(
        api_key=azure_openai_service_key,
        api_version=azure_openai_api_version,
        azure_endpoint=azure_openai_service_endpoint,
    )
    response = await client.beta.chat.completions.parse(
        model=azure_openai_deployment_model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": combined_prompt}
        ],
        response_format=IntentFormat
    )

    is_match = response.choices[0].message.content

    logger.info(
        f"OpenAI results: is_match={is_match}, customer_query='{user_query}', intent_description='{intent_description}'"
    )
    return is_match


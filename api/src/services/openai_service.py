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
    _transaction_decision_tool
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
    "transaction_decision": _transaction_decision_tool ,
}


class ResponseFormat(BaseModel):
    content: str = Field(..., description="Responda à consulta do cliente de forma breve e clara em duas linhas e pergunte se há algo mais com que você possa ajudar", min_length=1, max_length=1000)
    intent: str = Field(..., description="Intenção identificada na consulta do cliente")

class IntentFormat(BaseModel):
    agent_intent: bool = Field(..., description="Intenção de falar com um agente humano")


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_chat_completions_async(
    conversation_history,
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
    global response_content
    try:
        response = await client.chat.completions.create(
            model=azure_openai_deployment_model_name,
            messages= conversation_history,
            max_tokens=1000,
            tools=tools_description,
            tool_choice=tool_choice
        )

        response_message = response.choices[0].message

        conversation_history.append(
            response_message
        )

        print(f"Response: {response_message.content}")
        
         # Handle function calls
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                if tool_call.function.name == "transaction_decision":
                    if has_transaction_decision_been_called(conversation_history):
                        logger.info("transaction_decision already called, informing model to retry.")
                        conversation_history.append({
                            "role": "assistant",
                            "content": "La decisión sobre esta transacción ya se ha tomado anteriormente. Por favor, continúe con otra solicitud o pregunta."
                        })
                    else:
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
                        conversation_history.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_call.function.name,
                            "content": function_response,
                        })       
                else:
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

                    conversation_history.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_call.function.name,
                        "content": function_response,
                    })
        else:
            print("No tool calls were made by the model.")  

        # Second API call: Get the final response from the model
        final_response = await client.beta.chat.completions.parse(
            model=azure_openai_deployment_model_name,
            messages=conversation_history,
            max_tokens=1000,
            response_format=ResponseFormat
        )
        
    except Exception as ex:
        logger.error("error in openai api call : %s", ex)

    # Extract the response content
    if final_response is not None:
        response_content = final_response.choices[0].message.content
    else:
        response_content = ""
    return response_content, conversation_history

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
            end_silence_timeout=0.1,
            play_prompt=play_source,
            operation_context=context,
            speech_language="es-CL",
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


def has_transaction_decision_been_called(history):
    for message in history:
        if isinstance(message, dict):
            if (
                message.get('role') == 'tool' and
                message.get('name') == 'transaction_decision' and
                'tool_call_id' in message  # explicitly check for tool_call_id
            ):
                return True
    return False
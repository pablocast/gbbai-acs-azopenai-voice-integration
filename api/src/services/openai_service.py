from typing import List, Dict, Any, Optional
from openai import AsyncAzureOpenAI
from azure.communication.callautomation import (
    PhoneNumberIdentifier,
    RecognizeInputType,
    TextSource,
)
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_chat_completions_async(
    system_prompt,
    user_prompt,
    azure_openai_deployment_model_name,
    azure_openai_service_key,
    azure_openai_service_endpoint,
    azure_openai_api_version,
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
        )

    except Exception as ex:
        logger.error("error in openai api call : %s", ex)

    # Extract the response content
    if response is not None:
        response_content = response["choices"][0]["message"]["content"]
    else:
        response_content = ""
    return response_content


async def get_chat_gpt_response(
    instructions,
    speech_input,
    azure_openai_deployment_model_name,
    azure_openai_service_key,
    azure_openai_service_endpoint,
    azure_openai_api_version,
):
    return await get_chat_completions_async(
        instructions,
        speech_input,
        azure_openai_deployment_model_name,
        azure_openai_service_key,
        azure_openai_service_endpoint,
        azure_openai_api_version,
    )


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
            end_silence_timeout=0.5,
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


async def detect_escalate_to_agent_intent(
    speech_text,
    azure_openai_deployment_model_name,
    azure_openai_service_key,
    azure_openai_service_endpoint,
    azure_openai_api_version,
):
    return await has_intent_async(
        user_query=speech_text,
        intent_description="talk to agent",
        azure_openai_deployment_model_name=azure_openai_deployment_model_name,
        azure_openai_service_key=azure_openai_service_key,
        azure_openai_service_endpoint=azure_openai_service_endpoint,
        azure_openai_api_version=azure_openai_api_version,
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
    system_prompt = "You are a helpful assistant. You only respond with 'yes' or 'no'."
    combined_prompt = (
        f"does {user_query} have a similar meaning as {intent_description}"
    )
    # combined_prompt = base_user_prompt.format(user_query, intent_description)
    response = await get_chat_completions_async(
        system_prompt,
        combined_prompt,
        azure_openai_deployment_model_name,
        azure_openai_service_key,
        azure_openai_service_endpoint,
        azure_openai_api_version,
    )

    if "yes" in response.lower():
        is_match = True
    logger.info(
        f"OpenAI results: is_match={is_match}, customer_query='{user_query}', intent_description='{intent_description}'"
    )
    return is_match


def get_sentiment_score(sentiment_score):
    pattern = r"(\d)+"
    regex = re.compile(pattern)
    match = regex.search(sentiment_score)
    return int(match.group()) if match else -1

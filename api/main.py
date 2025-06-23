import asyncio
import base64
import logging
import os
import uuid
from datetime import datetime
from random import randint
from urllib.parse import urlencode, urlparse, urlunparse

from azure.communication.callautomation import PhoneNumberIdentifier
from azure.communication.callautomation.aio import CallAutomationClient
from azure.eventgrid import EventGridEvent, SystemEventNames
from numpy import ndarray
from quart import Quart, Response, json, request, redirect
from dotenv import load_dotenv
import jinja2
from azure.core.messaging import CloudEvent
import re

from src.services.openai_service import (
    handle_play,
    handle_recognize,
    get_chat_completions_async,
    handle_hangup,
)

from src.tools.tool_base import _search_tool_schema, _transaction_decision_tool_schema

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "src\prompts")
JINJA_ENV = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES_DIR))

load_dotenv(override=True)
# ——— Store active calls ———
active_calls = {}

# ——— Callback events URI to handle callback events. ———
CALLBACK_URI_HOST = os.environ["CALLBACK_URI_HOST"]
CALLBACK_EVENTS_URI = CALLBACK_URI_HOST + "/api/callbacks"

# ——— Create ACS Client ———
acs_client = CallAutomationClient.from_connection_string(
    os.environ["ACS_CONNECTION_STRING"]
)

# ——— Azure Services ———
azure_cognitive_service_endpoint = os.environ["COGNITIVE_SERVICE_ENDPOINT"]
azure_openai_deployment_model_name = os.environ["AZURE_OPENAI_SEARCHAGENT_DEPLOYMENT"]
azure_openai_service_key = os.environ["AZURE_OPENAI_API_KEY"]
azure_openai_service_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
azure_openai_api_version = os.environ["AZURE_OPENAI_API_VERSION"]

# ——— Create App ———
app = Quart(__name__)

# ——— Agent instructions ———
instruction_template = JINJA_ENV.get_template("instructions.jinja")
instructions = instruction_template.render(
    current_date=datetime.now().strftime("%Y-%m-%d"),
)

greeting_template = JINJA_ENV.get_template("greeting.jinja")

farewell_template = JINJA_ENV.get_template("farewell.jinja")

escalate_template = JINJA_ENV.get_template("escalate.jinja")
escalate = escalate_template.render()

connect_agent_template = JINJA_ENV.get_template("connect_agent.jinja")
connect_agent = connect_agent_template.render()

timeout_silence_prompt_template = JINJA_ENV.get_template("timeout_silence.jinja")
timeout_silence_prompt = timeout_silence_prompt_template.render()

empty_agent_template = JINJA_ENV.get_template("empty_agent.jinja")
empty_agent = empty_agent_template.render()

call_transfer_failure_template = JINJA_ENV.get_template("call_failure_transfer.jinja")
call_transfer_failure = call_transfer_failure_template.render()

# ——— Tools for OpenAI ———
tools = [_search_tool_schema, _transaction_decision_tool_schema]

# ——— Voice Name ———
voice_name = os.environ.get("VOICE_NAME", "en-US-JennyNeural")

# ——— Agent Phone Number ———
AGENT_PHONE_NUMBER = os.environ.get("AGENT_PHONE_NUMBER", None)

max_retry = 2

# ——— Conversation History ———
conversation_histories = {} 

# ——— Incoming Call endpoint ———
@app.route("/api/incomingCall", methods=["POST"])
async def incoming_call_handler() -> Response:
    for event_dict in await request.json:
        event = EventGridEvent.from_dict(event_dict)
        if (
            event.event_type
            == SystemEventNames.EventGridSubscriptionValidationEventName
        ):
            print("Validating subscription")
            validation_code = event.data["validationCode"]
            validation_response = {"validationResponse": validation_code}
            return Response(response=json.dumps(validation_response), status=200)
        elif event.event_type == "Microsoft.Communication.IncomingCall":
            print("Incoming call received: data=%s", event.data)
            caller_id = (
                event.data["from"]["phoneNumber"]["value"]
                if event.data["from"]["kind"] == "phoneNumber"
                else event.data["from"]["rawId"]
            )
            print("incoming call handler caller id: %s", caller_id)
            incoming_call_context = event.data["incomingCallContext"]
            guid = uuid.uuid4()
            query_parameters = urlencode({"callerId": caller_id})
            callback_uri = f"{CALLBACK_EVENTS_URI}/{guid}?{query_parameters}"

            print(f"callback url {callback_uri}")

            answer_call_result = await acs_client.answer_call(
                incoming_call_context=incoming_call_context,
                cognitive_services_endpoint=azure_cognitive_service_endpoint,
                callback_url=callback_uri,
            )

            active_calls[guid] = answer_call_result.call_connection_id

            print(
                f"Answered call for connection id: {answer_call_result.call_connection_id}"
            )

        return Response(status=200)


# ——— Call back endpoint ———
@app.route("/api/callbacks/<contextId>", methods=["POST"])
async def handle_callback(contextId):
    try:
        global caller_id
        app.logger.info("Request Json: %s", await request.json)
        for event_dict in await request.json:
            event = CloudEvent.from_dict(event_dict)
            app.logger.info(
                "%s event received for call connection id: %s",
                event.type,
                event.data["callConnectionId"],
            )

            caller_id = request.args.get("callerId").strip()
            customer_name = request.args.get("customerName").strip()
            transaction_value = request.args.get("transactionValue").strip()
            transaction_site = request.args.get("transactionSite").strip()
            transaction_id = request.args.get("transactionId").strip()
            transaction_currency = request.args.get("transactionCurrency").strip()

            if "+" not in caller_id:
                caller_id = "+".strip() + caller_id.strip()

            call_connection_id = event.data["callConnectionId"]

            if call_connection_id not in conversation_histories:
                conversation_histories[call_connection_id] = [
                    {"role": "system", "content": instructions}
                ]

            app.logger.info("call connected : data=%s", event.data)
            if event.type == "Microsoft.Communication.CallConnected":

                greeting = greeting_template.render(
                    nome=customer_name, valor=transaction_value, moeda = transaction_currency ,site=transaction_site
                )

                await handle_recognize(
                    acs_client,
                    greeting,
                    caller_id,
                    event.data["callConnectionId"],
                    voice_name=voice_name,
                    context="GetFreeFormText",
                )

            elif event.type == "Microsoft.Communication.RecognizeCompleted":
                if event.data["recognitionType"] == "speech":
                    speech_text = event.data["speechResult"]["speech"]
                    app.logger.info(
                        "Recognition completed, speech_text =%s", speech_text
                    )
                    if speech_text is not None and len(speech_text) > 0:
                        conversation_histories[call_connection_id].append({
                            "role": "user",
                            "content": speech_text + f"\n\n (Transaction ID: {transaction_id})"
                        })
                        
                        gpt_response, updated_history = await get_chat_completions_async(
                            conversation_histories[call_connection_id],
                            azure_openai_deployment_model_name,
                            azure_openai_service_key,
                            azure_openai_service_endpoint,
                            azure_openai_api_version,
                            tools
                        )

                        conversation_histories[call_connection_id] = updated_history

                        app.logger.info(
                            f"Chat GPT response for call connection id {call_connection_id}: {gpt_response}"
                        )

                        if gpt_response:
                            gpt_response = json.loads(gpt_response)
                            answer = gpt_response.get("content", "")
                            intent = gpt_response.get("intent", "")

                            conversation_histories[call_connection_id].append({
                                "role": "assistant",
                                "content": answer,
                            })

                            app.logger.info(
                                f"Chat GPT Answer={answer}, Intent={intent}"
                            )
                            if intent == "escalar_agente":
                                await handle_play(
                                    acs_client,
                                    call_connection_id=event.data["callConnectionId"],
                                    text_to_play=escalate,
                                    voice_name=voice_name,
                                    context="ConnectAgent",
                            )
                            elif intent == "repetir_informacoes":
                                await handle_recognize(
                                    acs_client,
                                    instructions,
                                    caller_id,
                                    event.data["callConnectionId"],
                                    voice_name=voice_name,
                                    context="GetFreeFormText",
                                )
                            else:
                                await handle_recognize(
                                    acs_client,
                                    answer,
                                    caller_id,
                                    event.data["callConnectionId"],
                                    voice_name=voice_name,
                                    context="OpenAISample",
                                )
                        else:
                            app.logger.info("No match found")
                            await handle_recognize(
                                acs_client,
                                empty_agent,
                                caller_id,
                                event.data["callConnectionId"],
                                voice_name=voice_name,
                                context="OpenAISample",
                            )

            elif event.type == "Microsoft.Communication.RecognizeFailed":
                resultInformation = event.data["resultInformation"]
                reasonCode = resultInformation["subCode"]
                context = event.data["operationContext"]
                global max_retry
                app.logger.info(
                    f"Recognize failed event received for connection id: {event.data['callConnectionId']}, reasonCode={reasonCode}, max_retry={max_retry}"
                )
                if reasonCode == 8510 and 0 < max_retry:
                    await handle_recognize(
                        acs_client,
                        timeout_silence_prompt,
                        caller_id,
                        event.data["callConnectionId"],
                        voice_name,
                    )
                    max_retry -= 1
                else:
                    farewell = farewell_template.render(
                        nome=customer_name
                      )
                    
                    await handle_play(
                        acs_client,
                        event.data["callConnectionId"],
                        farewell,
                        voice_name,
                        "Goodbye",
                    )

            elif event.type == "Microsoft.Communication.PlayCompleted":
                context = event.data["operationContext"]
                if context == "TransferFailed" or context.lower() == "Goodbye":
                    await handle_hangup(event.data["callConnectionId"])
                elif context == "ConnectAgent":
                    app.logger.info(f"Initializing the Call transfer...")
                    transfer_destination = PhoneNumberIdentifier(AGENT_PHONE_NUMBER)
                    call_connection_client = acs_client.get_call_connection(
                        call_connection_id=event.data["callConnectionId"]
                    )
                    await call_connection_client.transfer_call_to_participant(
                        target_participant=transfer_destination
                    )
                    app.logger.info(f"Transfer call initiated: {context}")

            elif event.type == "Microsoft.Communication.CallTransferAccepted":
                app.logger.info(
                    f"Call transfer accepted event received for connection id: {event.data['callConnectionId']}"
                )

            elif event.type == "Microsoft.Communication.CallTransferFailed":
                app.logger.info(
                    f"Call transfer failed event received for connection id: {event.data['callConnectionId']}"
                )
                resultInformation = event.data["resultInformation"]
                sub_code = resultInformation["subCode"]
                # check for message extraction and code
                app.logger.info(
                    f"Encountered error during call transfer, message=, code=, subCode={sub_code}"
                )
                await handle_play(
                    acs_client,
                    call_connection_id=event.data["callConnectionId"],
                    text_to_play=call_transfer_failure,
                    voice_name=voice_name,
                    context="TransferFailed",
                )

        return Response(status=200)
    except Exception as ex:
        app.logger.info("error in event handling")


@app.route("/outboundCall", methods=["POST"])
async def outbound_call():
    body = await request.get_json()

    target_phone_number = body.get("targetPhoneNumber")
    customer_name = body.get("customerName")
    transaction_value = body.get("transactionValue")
    transaction_currency = body.get("transactionCurrency")
    transaction_site = body.get("transactionSite")
    transaction_id = body.get("transactionId")

    if not (
        target_phone_number
        and customer_name
        and transaction_value
        and transaction_site
        and transaction_id
    ):
        return Response(
            "Missing "
            + ", ".join(
                [
                    n
                    for n, v in zip(
                        [
                            "targetPhoneNumber",
                            "customerName",
                            "transactionValue",
                            "transactionSite",
                            "transactionId",
                            "transaction_currency"
                        ],
                        [
                            target_phone_number,
                            customer_name,
                            transaction_value,
                            transaction_site,
                            transaction_id,
                            transaction_currency
                        ],
                    )
                    if not v
                ]
            ),
            status=400,
        )

    print(f"Outbound call to {target_phone_number}")
    target_participant = PhoneNumberIdentifier(target_phone_number)
    source_caller = PhoneNumberIdentifier(AGENT_PHONE_NUMBER)

    guid = uuid.uuid4()
    query_parameters = urlencode(
        {
            "callerId": target_phone_number,
            "customerName": customer_name,
            "transactionValue": transaction_value,
            "transactionCurrency": transaction_currency,
            "transactionSite": transaction_site,
            "transactionId": transaction_id
        }
    )
    callback_uri = f"{CALLBACK_EVENTS_URI}/{guid}?{query_parameters}"

    call_connection_properties = await acs_client.create_call(
        target_participant,
        callback_uri,
        cognitive_services_endpoint=azure_cognitive_service_endpoint,
        source_caller_id_number=source_caller,
    )
    app.logger.info(
        "Created call with connection id: %s",
        call_connection_properties.call_connection_id,
    )
    return Response(status=200)


@app.route("/")
def home():
    return "Hello SKxACS CallAutomation!"


if __name__ == "__main__":
    app.logger.setLevel(logging.INFO)
    app.run(port=8000)

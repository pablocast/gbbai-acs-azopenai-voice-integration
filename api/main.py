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
from quart import Quart, Response, json, request, websocket
from dotenv import load_dotenv
import jinja2
from azure.core.messaging import CloudEvent
import re

from src.services.openai_service import (
    handle_play,
    handle_recognize,
    get_chat_gpt_response,
    detect_escalate_to_agent_intent,
    get_sentiment_score,
    handle_hangup,
)

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
greeting = greeting_template.render()

farewell_template = JINJA_ENV.get_template("farewell.jinja")
farewell = farewell_template.render()

escalate_template = JINJA_ENV.get_template("escalate.jinja")
escalate = escalate_template.render()

connect_agent_template = JINJA_ENV.get_template("connect_agent.jinja")
connect_agent = connect_agent_template.render()

timeout_silence_prompt_template = JINJA_ENV.get_template("timeout_silence.jinja")
timeout_silence_prompt = timeout_silence_prompt_template.render()

empty_agent_phone_number_template = JINJA_ENV.get_template("empty_agent.jinja")
empty_agent_phone_number = empty_agent_phone_number_template.render()

call_transfer_failure_template = JINJA_ENV.get_template("call_failure_transfer.jinja")
call_transfer_failure = call_transfer_failure_template.render()

CHAT_RESPONSE_EXTRACT_PATTERN = (
    r"\s*Content:(.*)\s*Score:(.*\d+)\s*Intent:(.*)\s*Category:(.*)"
)

# ——— Voice Name ———
voice_name = os.environ.get("VOICE_NAME", "en-US-JennyNeural")

# ——— Agent Phone Number ———
AGENT_PHONE_NUMBER = os.environ.get("AGENT_PHONE_NUMBER", None)


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
            if "+" not in caller_id:
                caller_id = "+".strip() + caller_id.strip()

            app.logger.info("call connected : data=%s", event.data)
            if event.type == "Microsoft.Communication.CallConnected":
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
                        detect_escalate = await detect_escalate_to_agent_intent(
                            speech_text,
                            azure_openai_deployment_model_name,
                            azure_openai_service_key,
                            azure_openai_service_endpoint,
                            azure_openai_api_version,
                        )
                        app.logger.info(
                            f"Detect escalate to agent intent: {detect_escalate}"
                        )
                        if detect_escalate:
                            await handle_play(
                                acs_client,
                                call_connection_id=event.data["callConnectionId"],
                                text_to_play=escalate,
                                voice_name=voice_name,
                                context="ConnectAgent",
                            )
                        else:
                            chat_gpt_response = await get_chat_gpt_response(
                                instructions,
                                speech_text,
                                azure_openai_deployment_model_name,
                                azure_openai_service_key,
                                azure_openai_service_endpoint,
                                azure_openai_api_version
                            )
                            app.logger.info(f"Chat GPT response:{chat_gpt_response}")
                            regex = re.compile(CHAT_RESPONSE_EXTRACT_PATTERN)
                            match = regex.search(chat_gpt_response)
                            if match:
                                answer = match.group(1)
                                sentiment_score = match.group(2).strip()
                                intent = match.group(3)
                                category = match.group(4)
                                app.logger.info(
                                    f"Chat GPT Answer={answer}, Sentiment Rating={sentiment_score}, Intent={intent}, Category={category}"
                                )
                                score = get_sentiment_score(sentiment_score)
                                app.logger.info(f"Score={score}")
                                if -1 < score < 5:
                                    app.logger.info(f"Score is less than 5")
                                    await handle_play(
                                        acs_client,
                                        call_connection_id=event.data[
                                            "callConnectionId"
                                        ],
                                        text_to_play=connect_agent,
                                        voice_name=voice_name,
                                        context="ConnectAgent",
                                    )
                                else:
                                    app.logger.info(f"Score is more than 5")
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
                                    chat_gpt_response,
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
                    await handle_play(
                        acs_client, event.data["callConnectionId"], farewell, voice_name, "Goodbye"
                    )

            elif event.type == "Microsoft.Communication.PlayCompleted":
                context = event.data["operationContext"]
                if context == "TransferFailed" or context.lower() == "Goodbye":
                    await handle_hangup(event.data["callConnectionId"])
                elif context == "ConnectAgent":
                    if not AGENT_PHONE_NUMBER:
                        app.logger.info(f"Agent phone number is empty")
                        await handle_play(
                            acs_client,
                            call_connection_id=event.data["callConnectionId"],
                            text_to_play=empty_agent_phone_number,
                            voice_name=voice_name
                        )
                    else:
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
                    context="TransferFailed"
                )

        return Response(status=200)
    except Exception as ex:
        app.logger.info("error in event handling")


@app.route("/")
def home():
    return "Hello SKxACS CallAutomation!"


if __name__ == "__main__":
    app.logger.setLevel(logging.INFO)
    app.run(port=8000)

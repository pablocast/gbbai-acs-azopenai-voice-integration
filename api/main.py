import asyncio
import base64
import logging
import os
import uuid
from datetime import datetime
from random import randint
from urllib.parse import urlencode, urlparse, urlunparse

from azure.communication.callautomation import (
    AudioFormat,
    MediaStreamingAudioChannelType,
    MediaStreamingContentType,
    MediaStreamingOptions,
    MediaStreamingTransportType,
)
from azure.communication.callautomation.aio import CallAutomationClient
from azure.eventgrid import EventGridEvent, SystemEventNames
from numpy import ndarray
from quart import Quart, Response, json, request, websocket
from dotenv import load_dotenv
import jinja2

from src.services.openai_realtime_service import (
    init_websocket,
    start_conversation,
    process_websocket_message_async,
)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "src\prompts")
JINJA_ENV = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES_DIR))

load_dotenv(override=True)

# ——— Callback events URI to handle callback events. ———
CALLBACK_URI_HOST = os.environ["CALLBACK_URI_HOST"]
CALLBACK_EVENTS_URI = CALLBACK_URI_HOST + "/api/callbacks"

# ——— Create ACS Client ———
acs_client = CallAutomationClient.from_connection_string(
    os.environ["ACS_CONNECTION_STRING"]
)

# ——— Azure Realtime Service ———
azure_openai_service_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
azure_openai_service_key = os.environ["AZURE_OPENAI_API_KEY"]
azure_openai_deployment_model_name = os.environ["AZURE_OPENAI_REALTIME_DEPLOYMENT"]

# ——— Create App ———
app = Quart(__name__)

# ——— Agent instructions ———
instruction_template = JINJA_ENV.get_template("instructions.jinja")
instructions = instruction_template.render(
    current_date=datetime.now().strftime("%Y-%m-%d"),
    functions=["search", "report_grounding", "inform_loan"],
    grounding_function=["report_grounding"],
)
greeting_template = JINJA_ENV.get_template("greeting.jinja")
greeting = greeting_template.render()


# ——— WebSocket endpoint ———
@app.websocket("/ws")
async def ws():
    print("Client connected to WebSocket")
    await init_websocket(websocket)
    await start_conversation(
        greeting,
        instructions,
        azure_openai_service_endpoint,
        azure_openai_service_key,
        azure_openai_deployment_model_name,
    )
    while True:
        try:
            # Receive data from the client
            data = await websocket.receive()
            await process_websocket_message_async(data)
        except Exception as e:
            print(f"WebSocket connection closed: {e}")
            break


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

            parsed_url = urlparse(CALLBACK_EVENTS_URI)
            websocket_url = urlunparse(("wss", parsed_url.netloc, "/ws", "", "", ""))

            print(f"callback url {callback_uri}")
            print(f"websocket url {websocket_url}")

            media_streaming = MediaStreamingOptions(
                transport_url=websocket_url,
                transport_type=MediaStreamingTransportType.WEBSOCKET,
                content_type=MediaStreamingContentType.AUDIO,
                audio_channel_type=MediaStreamingAudioChannelType.MIXED,
                start_media_streaming=True,
                enable_bidirectional=True,
                audio_format=AudioFormat.PCM24_K_MONO,
            )

            answer_call_result = await acs_client.answer_call(
                incoming_call_context=incoming_call_context,
                operation_context="incomingCall",
                callback_url=callback_uri,
                media_streaming=media_streaming,
            )

            print(
                f"Answered call for connection id: {answer_call_result.call_connection_id}"
            )

        return Response(status=200)


# ——— Call back endpoint ———
@app.route("/api/callbacks/<contextId>", methods=["POST"])
async def callbacks(contextId):
    for event in await request.json:
        # Parsing callback events
        global call_connection_id
        event_data = event["data"]
        call_connection_id = event_data["callConnectionId"]
        app.logger.info(
            f"Received Event:-> {event['type']}, Correlation Id:-> {event_data['correlationId']}, CallConnectionId:-> {call_connection_id}"
        )
        if event["type"] == "Microsoft.Communication.CallConnected":
            call_connection_properties = await acs_client.get_call_connection(
                call_connection_id
            ).get_call_properties()
            media_streaming_subscription = (
                call_connection_properties.media_streaming_subscription
            )
            app.logger.info(
                f"MediaStreamingSubscription:--> {media_streaming_subscription}"
            )
            app.logger.info(
                f"Received CallConnected event for connection id: {call_connection_id}"
            )
            app.logger.info("CORRELATION ID:--> %s", event_data["correlationId"])
            app.logger.info("CALL CONNECTION ID:--> %s", event_data["callConnectionId"])
        elif event["type"] == "Microsoft.Communication.MediaStreamingStarted":
            app.logger.info(
                f"Media streaming content type:--> {event_data['mediaStreamingUpdate']['contentType']}"
            )
            app.logger.info(
                f"Media streaming status:--> {event_data['mediaStreamingUpdate']['mediaStreamingStatus']}"
            )
            app.logger.info(
                f"Media streaming status details:--> {event_data['mediaStreamingUpdate']['mediaStreamingStatusDetails']}"
            )
        elif event["type"] == "Microsoft.Communication.MediaStreamingStopped":
            app.logger.info(
                f"Media streaming content type:--> {event_data['mediaStreamingUpdate']['contentType']}"
            )
            app.logger.info(
                f"Media streaming status:--> {event_data['mediaStreamingUpdate']['mediaStreamingStatus']}"
            )
            app.logger.info(
                f"Media streaming status details:--> {event_data['mediaStreamingUpdate']['mediaStreamingStatusDetails']}"
            )
        elif event["type"] == "Microsoft.Communication.MediaStreamingFailed":
            app.logger.info(
                f"Code:->{event_data['resultInformation']['code']}, Subcode:-> {event_data['resultInformation']['subCode']}"
            )
            app.logger.info(f"Message:->{event_data['resultInformation']['message']}")
        elif event["type"] == "Microsoft.Communication.CallDisconnected":
            pass
    return Response(status=200)


@app.route("/")
def home():
    return "Hello SKxACS CallAutomation!"


if __name__ == "__main__":
    app.logger.setLevel(logging.INFO)
    app.run(port=8000)

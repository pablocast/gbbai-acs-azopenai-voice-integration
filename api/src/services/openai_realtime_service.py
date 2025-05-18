import asyncio
import json
from rtclient import (
    RTLowLevelClient,
    SessionUpdateMessage,
    ServerVAD,
    SessionUpdateParams,
    InputAudioBufferAppendMessage,
    InputAudioTranscription,
    ItemCreateMessage,
    ResponseCreateMessage,
    UserMessageItem,
    InputTextContentPart,
)
from azure.core.credentials import AzureKeyCredential
from src.tools.tool_base import (
    _search_tool_schema,
    _report_grounding_tool_schema,
    _inform_loan_tool_schema,
    _search_tool,
    _report_grounding_tool,
    _inform_loan_tool,
)
import uuid

tools_schema = [_search_tool_schema, _report_grounding_tool_schema, _inform_loan_tool_schema]
tools = { "search": _search_tool, "report_grounding": _report_grounding_tool, "inform_loan": _inform_loan_tool}

active_websocket = None

class RTToolCall:
    tool_call_id: str
    previous_id: str

    def __init__(self, tool_call_id: str, previous_id: str):
        self.tool_call_id = tool_call_id
        self.previous_id = previous_id

async def start_conversation(
    greeting: str,
    instructions: str,
    azure_openai_service_endpoint: str,
    azure_openai_service_key: str,
    azure_openai_deployment_model_name: str,
):
    global client
    global conversation_call_id
    client = RTLowLevelClient(
        url=azure_openai_service_endpoint,
        key_credential=AzureKeyCredential(azure_openai_service_key),
        azure_deployment=azure_openai_deployment_model_name,
    )
    await client.connect()
    await client.send(
        SessionUpdateMessage(
            session=SessionUpdateParams(
                instructions=instructions,
                turn_detection=ServerVAD(type="server_vad", prefix_padding_ms=300, silence_duration_ms=800, threshold=0.4),
                voice="shimmer",
                input_audio_format="pcm16",
                output_audio_format="pcm16",
                input_audio_transcription=InputAudioTranscription(model="whisper-1"),
                tools=tools_schema
            )
        )
    )

    # Start receiving messages from the server
    conversation_call_id = str(uuid.uuid4())
    content_part = InputTextContentPart(
            text=greeting,
        )
    
    initial_conversation_item = ItemCreateMessage(
        item=UserMessageItem(content=[content_part]),
        call_id=conversation_call_id
    )

    await client.ws.send_json(
                        {
                            "type":"conversation.item.create",
                            "item": {
                                "role": "system",
                                "type": "message",
                                "text": greeting
                        }
                        }
                    )
 
    await client.ws.send_json(
            {
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "instructions": f"Greet the user with '{greeting}' and ask them how you can help. Be concise and friendly.",
                }
            }
    )

    asyncio.create_task(receive_messages(client))


async def send_audio_to_external_ai(audioData: str):
    await client.send(
        message=InputAudioBufferAppendMessage(
            type="input_audio_buffer.append", audio=audioData, _is_azure=True
        )
    )

async def receive_messages(client: RTLowLevelClient):
    _tools_pending = {}
    while not client.closed:
        message = await client.recv()
        updated_message = message
        if message is None:
            continue
        match message.type:
            case "session.created":
                print("Session Created Message")
                print(f"  Session Id: {message.session.id}")
                pass
            case "error":
                print(f"  Error: {message.error}")
                pass
            case "input_audio_buffer.cleared":
                print("Input Audio Buffer Cleared Message")
                pass
            case "input_audio_buffer.speech_started":
                print(
                    f"Voice activity detection started at {message.audio_start_ms} [ms]"
                )
                await stop_audio()
                pass
            case "input_audio_buffer.speech_stopped":
                pass
            case "conversation.item.input_audio_transcription.completed":
                print(f" User:-- {message.transcript}")
            case "conversation.item.input_audio_transcription.failed":
                print(f"  Error: {message.error}")
            case "response.done":
                print("Response Done Message")
                print(f"  Response Id: {message.response.id}")
                if message.response.status_details:
                    print(
                        f"  Status Details: {message.response.status_details.model_dump_json()}"
                    )
            case "response.audio_transcript.done":
                print(f" AI:-- {message.transcript}")
            case "response.audio.delta":
                await receive_audio_for_outbound(message.delta)
                pass
            case "function_call":
                print(f"Function Call Message: {message}")
                # Store the original call_id from the function call
                call_id = message.call_id
                pass
            case "response.function_call_arguments.done":
                print(f"Message: {message}")
                function_name = message.name
                args = json.loads(message.arguments)
                # Use the call_id from the original function call
                call_id = message.call_id
                
                print(f"Function args: {message.arguments}")
                try:
                    tool = tools[function_name]
                    result = await tool(args)
                    print(f"Function result: {result}")
                    
                    await client.ws.send_json(
                        {
                            "type":"conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "output": f"Here are the results: {result}",
                                "call_id": call_id  
                            }
                        }
                    )
 
                    await client.ws.send_json(
                            {
                                "type": "response.create",
                                "response": {
                                    "modalities": ["text", "audio"],
                                    "instructions": f"Respond to the user that you found {result}. Be concise and friendly."
                                }
                            }
                    )

                except Exception as e:
                    print(f"Error calling function {function_name}: {e}")
                    await client.ws.send_json(
                            {
                                "type": "response.create",
                                "response": {
                                    "modalities": ["text", "audio"],
                                    "instructions": f"Respond to the user that you didn't find any results. Be concise and friendly."
                                }
                            }

                    )
            case _:
                pass


async def init_websocket(socket):
    global active_websocket
    active_websocket = socket


async def receive_audio_for_outbound(data):
    try:
        data = {"Kind": "AudioData", "AudioData": {"Data": data}, "StopAudio": None}

        # Serialize the server streaming data
        serialized_data = json.dumps(data)
        await send_message(serialized_data)

    except Exception as e:
        print(e)


async def stop_audio():
    stop_audio_data = {"Kind": "StopAudio", "AudioData": None, "StopAudio": {}}

    json_data = json.dumps(stop_audio_data)
    await send_message(json_data)


async def send_message(message: str):
    global active_websocket
    try:
        await active_websocket.send(message)
    except Exception as e:
        print(f"Failed to send message: {e}")


async def process_websocket_message_async(stream_data):
    try:
        data = json.loads(stream_data)
        kind = data["kind"]
        if kind == "AudioData":
            audio_data = data["audioData"]["data"]
            await send_audio_to_external_ai(audio_data)
    except Exception as e:
        print(f"Error processing WebSocket message: {e}")

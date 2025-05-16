import asyncio
import json
from rtclient import (
    RTLowLevelClient,
    SessionUpdateMessage,
    ServerVAD,
    SessionUpdateParams,
    InputAudioBufferAppendMessage,
    InputAudioTranscription,
)
from azure.core.credentials import AzureKeyCredential

active_websocket = None


async def start_conversation(
    instructions: str,
    azure_openai_service_endpoint: str,
    azure_openai_service_key: str,
    azure_openai_deployment_model_name: str,
):
    global client
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
            )
        )
    )

    asyncio.create_task(receive_messages(client))


async def send_audio_to_external_ai(audioData: str):
    await client.send(
        message=InputAudioBufferAppendMessage(
            type="input_audio_buffer.append", audio=audioData, _is_azure=True
        )
    )


async def receive_messages(client: RTLowLevelClient):
    while not client.closed:
        message = await client.recv()
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

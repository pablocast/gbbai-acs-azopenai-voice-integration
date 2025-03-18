import asyncio
import json
from  rtclient import (
    RTLowLevelClient,
    SessionUpdateMessage,
    ServerVAD, 
    SessionUpdateParams, 
    InputAudioBufferAppendMessage, 
    InputAudioTranscription,
    )
from azure.core.credentials import AzureKeyCredential

from src.config.settings import Config
from src.services.cache_service import CacheService
from src.config.constants import OpenAIPrompts


class OpenAIRealtimeService:
    def __init__(self, config:Config, cache: CacheService):
        self.config = config
        self.cache_service = cache
        self.clients = {}
        self.active_websockets = {}
    
    active_websocket = None

    async def _get_system_message_persona_from_payload(
        self, 
        call_id:str,
        promtps:OpenAIPrompts = OpenAIPrompts, 
        persona:str='default'
    ):
        """Method to add logic to configure agent persona leveraging the system prompt and candidate and job cached data"""
        ## Add your logic ##
        acs_call_id = await self.cache_service.get(f'acs_call_id:{call_id}')
        req_payload = await self.cache_service.get(f'payload_dict:{acs_call_id}')
        sys_msg = self._construct_system_message(
            promtps.system_message_dict.get(persona), 
            [
                "\n## ADDITIONAL INFORMATION\n" + json.dumps(req_payload)
            ]
        )
        print(f"\n\n{sys_msg}\n\n")
        return sys_msg
    
    def _construct_system_message(
        self,
        sys_msg:str, 
        str_list_to_append: list[str]=None
    )-> str:
        """Method to construct the system message based on the standard plus customizations"""
        if str_list_to_append:
            return f"{sys_msg} {' '.join(str_list_to_append)}"
        return sys_msg

    async def start_conversation(self, call_id: str):
        """
        Method to start a conversation with the Azure OpenAI service via the RTLowLevelClient.
        Official voice options: 'amuch', 'dan', 'elan', 'marilyn', 'meadow', 'breeze', 'cove', 'ember', 'jupiter', 'alloy', 'echo', and 'shimmer'
        Note that these voices are in preview and will depend on the version of the RTClient your using.
        - ...
        """
        sys_msg = await self._get_system_message_persona_from_payload(call_id)
        client = RTLowLevelClient(
            url=self.config.AZURE_OPENAI_SERVICE_ENDPOINT, 
            key_credential=AzureKeyCredential(self.config.AZURE_OPENAI_SERVICE_KEY), 
            azure_deployment=self.config.AZURE_OPENAI_DEPLOYMENT_MODEL_NAME
        )
        await client.connect()
        self.clients[call_id] = client
        await client.send(
                SessionUpdateMessage(
                    session=SessionUpdateParams(
                        instructions=sys_msg,
                        turn_detection=ServerVAD(type="server_vad"),
                        voice= 'marilyn',
                        input_audio_format='pcm16',
                        output_audio_format='pcm16',
                        input_audio_transcription=InputAudioTranscription(model="whisper-1")
                    )
                )
            )
        
        # maybe start by sending welcome message
        asyncio.create_task(self.receive_messages(call_id=call_id, client=client))
        

    async def send_audio_to_external_ai(self, call_id:str, audioData: str):
        client = self.clients.get(call_id)
        await client.send(
            message=InputAudioBufferAppendMessage(
                type="input_audio_buffer.append", 
                audio=audioData, 
                _is_azure=True
            )
        )


    async def receive_messages(self, call_id: str, client: RTLowLevelClient):
        client = self.clients.get(call_id)
        while not client.closed:
            message = await client.recv()
            if message is None:
                continue
            match message.type:
                case "session.created":
                    print("Session Created Message")
                    print(f"  Session Id: {message.session.id}")
                    #TODO: for this to work it needs to be enconded in base64 audio
                    #greeting = "Hello {name}, this is Kira, an AI recruiter at Contoso. I have a job opportunity that matches your profile. Do you have a few minutes to discuss it?"
                    #await send_audio_to_external_ai(greeting)
                    pass
                #case "session.updated":
                #    message
                #    text_message = {
                #    'event_id':message['event_id'],
                #    "type": "conversation.item.create",
                #    "item": {
                #        "type": "message",
                #        "role": "user",
                #        "content": [{"type": "input_text", "text":"Say hello to me using my name, introduce yourself and ask me if I have a few mins to talk about a job opportunity"}]
                #    }
                #}
                #    await client.send(json.dumps(text_message))
                case "error":
                    print(f"  Error: {message.error}")
                    pass
                case "input_audio_buffer.cleared":
                    print("Input Audio Buffer Cleared Message")
                    pass
                case "input_audio_buffer.speech_started":
                    print(f"Voice activity detection started at {message.audio_start_ms} [ms]")
                    await self.stop_audio(call_id)
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
                        print(f"  Status Details: {message.response.status_details.model_dump_json()}")
                case "response.audio_transcript.done":
                    print(f" AI:-- {message.transcript}")
                    # consider if it should hang up the call
                    if any(keyword in message.transcript.lower() for keyword in ["bye", "goodbye", "take care"]):
                        # await _handle_hangup(acs_call_connection_id)
                        # TODO: implement hangup
                        #await self.cleanup_call_resources(call_id)
                        print("### Should hangup the call ###")
                case "response.audio.delta":
                    await self.receive_audio_for_outbound(call_id, message.delta)
                    pass
                case _:
                    pass


    async def _handle_hangup(self, call_connection_id:str):
        pass        

    async def init_websocket(self, call_id:str, socket):
        #global active_websocket
        self.active_websockets[call_id] = socket


    async def receive_audio_for_outbound(self, call_id:str, data):
        try:
            data = {
                "Kind": "AudioData",
                "AudioData": {
                        "Data":  data
                },
                "StopAudio": None
            }

            # Serialize the server streaming data
            serialized_data = json.dumps(data)
            await self.send_message(call_id, serialized_data)
            
        except Exception as e:
            print(e)


    async def stop_audio(self, call_id: str):
            stop_audio_data = {
                "Kind": "StopAudio",
                "AudioData": None,
                "StopAudio": {}
            }

            json_data = json.dumps(stop_audio_data)
            await self.send_message(call_id, json_data)


    async def send_message(self, call_id:str, message: str):
        active_websocket = self.active_websockets.get(call_id)
        try:
            await active_websocket.send(message)
        except Exception as e:
            print(f"Failed to send message: {e}")
            
    # orignally in media_streming_handler.py
    async def process_websocket_message_async(self, call_id, stream_data):
        try:
            data = json.loads(stream_data)
            kind = data['kind']
            if kind == "AudioData":
                audio_data = data["audioData"]["data"]
                await self.send_audio_to_external_ai(call_id, audio_data)
        except Exception as e:
            print(f'Error processing WebSocket message: {e}')
    
        
    async def cleanup_call_resources(self, call_id:str, is_acs_id:bool=True):
        """Method to cleanup resources for a call
        :param call_id: The call_id or acs_id to cleanup resources for
        :param is_acs_id: A boolean flag to indicate if the call_id is an acs_id or websocket_id
        """
        if is_acs_id:
            call_id = await self.cache_service.get(f'websocket_id:{call_id}')
            
        client = self.clients.pop(call_id, None)
        websocket = self.active_websockets.pop(call_id, None)
        if websocket:
            print(f"Closing websocket for call_id {call_id} ...")
            await websocket.close()
        if client:
            print(f"Closing client for call_id {call_id} ...")
            await client.close()



from enum import Enum

class StatusCodes:
    """HTTP Status Codes"""
    OK = 200
    BAD_REQUEST = 400
    SERVER_ERROR = 500

class EventTypes(str, Enum):
    """Azure Communication Service Event Types"""
    INCOMING_CALL = "Microsoft.Communication.IncomingCall"
    CALL_CONNECTED = "Microsoft.Communication.CallConnected"
    RECOGNIZE_COMPLETED = "Microsoft.Communication.RecognizeCompleted"
    PLAY_COMPLETED = "Microsoft.Communication.PlayCompleted"
    RECOGNIZE_FAILED = "Microsoft.Communication.RecognizeFailed"
    CALL_DISCONNECTED = "Microsoft.Communication.CallDisconnected"
    PARTICIPANTS_UPDATED = "Microsoft.Communication.ParticipantsUpdated"

class ErrorMessages:
    """Error and Fallback Messages"""
    PLAY_ERROR = "I apologize, but I'm having trouble responding. Let me try again."
    RECOGNIZE_ERROR = "I apologize, but I need to repeat the question. Could you please respond?"

class ConversationPrompts:
    """Conversation Prompts"""
    HELLO = "I’m Kira, a virtual recruitment assistant at Contoso Solutions. I’ve come across an open position at one of our partner companies that seems like a great fit for your skill set."
    TIMEOUT_SILENCE = "I am sorry, I did not hear anything. Please could you confirm you are there"
    GOODBYE = "Thank you for your time. Have a great day. Bye for now!"
    LOCATION_QUESTION = "Could you please let me know where you're currently based?"
    THANK_YOU = "Great! For the next steps, I'll follow up with you via email. Thank you so much for your time today, and I look forward to staying in touch. Have a wonderful day!"

class AppConstants:
    """Application Constants"""
    MAX_TEXT_LENGTH = 400
    MAX_RETRY = 2
    
class ApiPayloadKeysForValidation:
    """API Payload Keys for Validation for the outbound call trigger"""
    API_KEYS = [
        "candidate_name", 
        "job_role", 
        "company", 
        "location", 
        "rate", 
        "skills", 
        "responsibility", 
        "sector", 
        "phone_number", 
        "remote_onsight_status"
    ]
    CANDIDATE_DATA_KEYS = [
        "candidate_name",
        "phone_number"
    ]
    JOB_DATA_KEYS = list(set(API_KEYS) - set(CANDIDATE_DATA_KEYS))
    
class OpenAIPrompts:
    
    SYSTEM_MESSAGE_DEFAULT = f"""
    You are Kira, an AI travel agent at Contoso Travels, a leading travel agency specializing in luxury vacations.
    Your role is to assist customers in planning their dream vacations, providing recommendations, and booking their travel arrangements.
    Your personality should be professional, knowledgeable, and attentive, reflecting the brand's image of delivering exceptional customer service.
    Your job starts after a customer requests to be contacted about a trip they are interested in. You goal is to assist them in the booking process.
    
    ## GENERAL GUIDELINES
    - Address the customer by their name.
    
    ## CONVERSATION FLOW
    - Always greet customers with a warm welcome, explicitly mentioning who you are and why you're calling.
    - Check if the customer is okay with you being AI and offer to transfer them to a human agent if needed, mentioning that it will take a longer time in that case.
    - Start by providing an overview of the trip they are interested in and ask if they have any specific preferences or requirements.
    - Offer recommendations based on their preferences to expand their options for that trip.
    - Explore the trip details:
        - #1: Dates and origin
        - #2: Transportation preferences: flight or train (if applicable based on origin)
        - #3: Class preferences: economy, business, or first class
        - #4: Accommodation preferences: hotel or resort
        - #5: Budget range for the hotel
    - Offer the send a detailed itinerary via email for their review with some options for transport and accommodation based on their budget.
    - If they agree, confirm their email address.
    - End the call by thanking them for their time and confirming the next steps (they need to review the email and provide an answer).
    """
 
    system_message_dict = {
        "default": SYSTEM_MESSAGE_DEFAULT
    }

    
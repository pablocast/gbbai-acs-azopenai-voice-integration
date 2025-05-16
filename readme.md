# Recruitment Voice Assistant 

## Features
- **PSTN Calling**: Users can call a phone number, and the voice assistant will interact with them using speech-to-text and text-to-speech capabilities.
- **OpenAI GPT-4o Integration**: Generates dynamic recruitment filtering chat for the potential candidate based on job description.
- **Event-Driven Architecture**: Uses **Azure EventGrid** for event-driven routing of call-related events.
- **Redis Caching**: Stores precomputed job details, competency questions, and location data to minimize repeated API calls and reduce latency.
- **Azure Services**: Leverages **Azure Maps**, **Azure Search**, and **Azure Cognitive Services** for grounding the call into relevant job description and in future in the candidate CV. 
- **Session History**: Session data and call recordings are stored in **Cosmos DB** for long-term storage.
---

## Architecture Overview
The following Azure services and technologies are used in this project:

1. **Azure Communication Services (ACS)**: Handles incoming and (to be implemented) outgoing PSTN calls.
2. **Azure OpenAI GPT-4o**: Generates responses to user inputs using large language models.
3. **Azure Cognitive Services**: Provides speech-to-text and text-to-speech capabilities for interacting with the caller.
4. **Azure EventGrid**: Routes call events (CallConnected, RecognizeCompleted, etc.) to the **Quart API**.
5. **Azure Search**: Queries job details and other information for candidate interaction.
6. **Azure Maps**: Provides geographic location data for determining candidate proximity to job roles.
7. **Redis Cache**: Caches job details and other global variables to reduce API calls and improve performance.
8. **Azure Cosmos DB**: Stores call session data, including recordings and conversation history, for long-term storage.
---

## Prerequisites
- **Azure Subscription** with access to Azure OpenAI models.  
- **Python 3.10+** installed on your local environment.  
- [Azure Dev Tunnel](https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/get-started?tabs=windows) (or alternative) for handling ACS callback URLs if testing locally.  
- [Terraform](https://learn.microsoft.com/pt-br/azure/developer/terraform/get-started-windows-bash) to deploy the IaC in the `automation` folder.
- [azd](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd), used to deploy all Azure resources and assets used in this sample.
- **Install the Azure CLI Communication extension**
```bash
az extension add --name communication --yes
```

---

## Setup and Installation
### 1. Clone the Repository

```bash
git clone https://github.com/your-repository-name/voice-assistant
cd voice-assistant
```

### 2. Install Python Dependencies
Create a virtual environment and install the required Python libraries listed in `requirements.txt`.

#### Bash
```bash
python3 -m venv .venv
source venv/bin/activate
pip install -r requirements.txt
pip install api/rtclient-0.5.1-py3-none-any.whl
```

#### PowerShell
```powershell
python3 -m venv .venv
.venv/Scripts/Activate.ps1
pip install -r api/requirements.txt
pip install api/rtclient-0.5.1-py3-none-any.whl
```

### 3. Deploy the Terraform IaC
> [!Note]
> You need to have activated the venv and installed the requirements as the IaC automation contains python scripts that require specific libraries.

Navigate to for the details for the [Terraform automation deployment Doc](automation/README.md).

Make sure to follow the manual step of navigating inside the ACS resource and connecting it to the Cognitive Service (aka AI multiservices account) via Managed Identity. This process happens in the background when you do it from ACS. If this step is not done, the phone call will happen but it will hang up instantly.


## Running it locally

### 1. Add the Environment Variable values to a .env file
Based on `.env.sample`, create and construct your `.env` file to allow your local app to access your Azure resource.

### 2. Enable and run a Microsoft DevTunnel
> [!NOTE]
>- Azure Dev Tunnels CLI. For details, see  >[Enable dev tunnel](https://docs.tunnels.api.>visualstudio.com/cli)
>- Create an Azure Cognitive Services resource. >For details, see [Create an Azure Cognitive >Services Resource](https://learn.microsoft.com/>en-us/azure/cognitive-services/>cognitive-services-apis-create-account)
>- Create and host a Azure Dev Tunnel. > Instructions [here](https://learn.microsoft.com/>en-us/azure/developer/dev-tunnels/get-started)

[Azure DevTunnels](https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/overview) is an Azure service that enables you to share local web services hosted on the internet. Use the commands below to connect your local development environment to the public internet. This creates a tunnel with a persistent endpoint URL and which allows anonymous access. We will then use this endpoint to notify your application of calling events from the ACS Call Automation service.

#### Running it for the first time:
```bash
devtunnel login
devtunnel create --allow-anonymous
devtunnel port create -p 8000
devtunnel host
```
Add the devtunnel link structured as `https://<name>.devtunnels.ms:8080` to the `.env` file as callback URI host.

#### Leveragin a previously created DevTunnel:
```bash
devtunnel login
devtunnel list
# copy the name of the devtunnel you want to target
devtunnel host <your devtunnel name> 
```
Then run the python app by running `python3 api/main.py` on your terminal and check that it runs with no issues before proceeding.

### Register an EventGrid Webhook for the IncomingCall(`https://<your devtunnel name>/api/incomingCall`) event that points to your devtunnel URI. 
Instructions [here](https://learn.microsoft.com/en-us/azure/communication-services/concepts/call-automation/incoming-call-notification).
  - To register the event, navigate to your ACS resource in the Azure Portal (follow the Microsoft Learn Docs if you prefer to use the CLI). 
  - On the left menu bar click "Events."
  - Click on "+Event Subscription."
    - Provide a unique name for the event subscription details, for example, "IncomingCallWebhook"
    - Leave the "Event Schema" as "Event Grid Schema"
    - Provide a unique "System Topic Name"
    - For the "Event Types" select "Incoming Call"
    - For the "Endpoint Details" select "Webhook" from the drop down
      - Once "Webhook" is selected, you will need to configure the URI for the incoming call webhook, as mentioned above: `https://<your devtunnel name>/api/incomingCall`.
    - **Important**: before clicking on "Create" to create the event subscription, the `/api/main.py` script must be running, as well as your devtunnel. ACS sends a verification payload to the app to make sure that the communication is configured properly. The event subscription will not succeed in the portal without the script running. If you see an error, this is most likely the root cause.


## Running it on Azure
Once the IaC has been deployed, the web API should be ready to use. Feel free to configure the system message within constants.

## Test the app with an outbound phone call

Send an HTTP request to the web API following the sample on `outbound.http`. To make the request on VSCode, you can use the *Rest Client* extension and then, on the file, click on *Send Request* on top of the `POST` method.

Make sure you send a payload that meets the requirements by leveraging the existing sample on the same file. The validation can be edited on `./api/src/core/app.py` within the `initiate_outbound_call()` function.



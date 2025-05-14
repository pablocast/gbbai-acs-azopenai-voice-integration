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
```

#### PowerShell
```powershell
python3 -m venv .venv
.venv/Scripts/Activate.ps1
pip install -r api/requirements.txt
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

Once the tunnel is running, navigate to your Azure Event Grid System Topic resource and click on *+ Event Subscription*. Create a local subscription to your local app for the event `IncomingCall` as a webhook, with the URL `https://<your devtunnel name>.devtunnels.ms:8000/api/incomingCall`. Note that both the devtunnel and the python app should be running for this step to work.

## Running it on Azure
Once the IaC has been deployed, the web API should be ready to use. Feel free to configure the system message within constants.

## Test the app with an outbound phone call

Send an HTTP request to the web API following the sample on `outbound.http`. To make the request on VSCode, you can use the *Rest Client* extension and then, on the file, click on *Send Request* on top of the `POST` method.

Make sure you send a payload that meets the requirements by leveraging the existing sample on the same file. The validation can be edited on `./api/src/core/app.py` within the `initiate_outbound_call()` function.



# Azure Solution Deployment Using Terraform

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Forking the Repository](#forking-the-repository)
4. [Setting Up GitHub Token for CI/CD](#setting-up-github-token-for-cicd)
5. [Terraform State Management](#terraform-state-management)
6. [Deployment Steps](#deployment-steps)
7. [Automation for the Recruitment Voice Assistant](#automation-for-the-recruitment-voice-assistant)
8. [Testing and Validation](#testing-and-validation)
9. [Additional Resources](#additional-resources)

## Overview
This repository contains Terraform code to deploy an Azure-based AI solution. The structure and scripts herein can be adapted for various use cases, including the Recruitment Voice Assistant solution.

## Prerequisites
Before you start, ensure you have:
- [Terraform](https://www.terraform.io/downloads.html) installed locally.
- Access to an Azure subscription.
- A GitHub account and personal access token with necessary permissions.
- An Azure storage account and container for Terraform state management (see [Terraform State Management](#terraform-state-management) section).

## Forking the Repository
1. Navigate to the main page of the repository.
2. Click the "Fork" button in the upper-right corner.
3. Select your GitHub account as the destination for the fork.
4. Once forked, clone your repository to your local machine:
   ```bash
   git clone https://github.com/YOUR_GITHUB_USERNAME/ACSOpenAIVoice.git
   cd ACSOpenAIVoice/automation
   ```

## Terraform State Management
### Creating Azure Storage for Terraform State
```bash
az group create --name terraform --location eastus
az storage account create --name terraform<your-prefix> --resource-group terraform --sku Standard_LRS
az storage container create --name tfstate --account-name terraform<your-prefix>
```

### Configuring Terraform Backend
Update `backend.tf` as needed:
```hcl
terraform {
  backend "azurerm" {
    resource_group_name  = "terraform"
    storage_account_name = "terraform<your-unique-prefix>"
    container_name       = "tfstate"
    key                  = "terraform.tfstate"
    use_azuread_auth     = true
  }
}
```

## Deployment Steps
1. **Clone the Repository (if not already done):**
   ```bash
   git clone https://github.com/YOUR_GITHUB_USERNAME/azure-ai-translator-accelerators.git
   cd azure-ai-translator-accelerators/deployment-scripts/terraform
   ```

2. **Initialize Terraform:**
   ```bash
   terraform init
   ```

3. **Plan the Deployment:**
   ```bash
   terraform plan
   ```

4. **Apply the Configuration:**
   **Bash:**
   ```bash
   export TF_VAR_principal_object_id=$(az ad signed-in-user show --query id -o tsv)
   terraform apply -auto-approve
   ```

   **PowerShell:**
   ```powershell
   $env:TF_VAR_principal_object_id = (az ad signed-in-user show --query id -o tsv)
   terraform apply -auto-approve
   ```

## Automation for the Recruitment Voice Assistant
The repository includes an `automation` folder containing Terraform definitions and scripts that facilitate the provisioning of resources for the Recruitment Voice Assistant project. The Terraform templates create and configure essential Azure services—such as Cognitive Services, Azure Communication Services (ACS), Azure OpenAI, Event Grid, Redis, Cosmos DB, Azure Functions, and Log Analytics—needed to run the recruitment voice assistant application.

**Key Points:**
- **Project**: Recruitment Voice Assistant  
- **URL**: [https://github.com/Aastha2024/ACSOpenAIVoice](https://github.com/Aastha2024/ACSOpenAIVoice)
- **Folder**: `automation` (root of Terraform files)

Within the `automation` directory, you will find:
- **Terraform Configuration Files**: Files like `acs.tf`, `openai.tf`, `cognitive_services.tf`, `cosmos.tf`, and `redis.tf` define the services required for the Recruitment Voice Assistant.
- **Modules**: The `modules` directory provides reusable Terraform modules, enabling a modular and maintainable infrastructure codebase.
- **API Deployment**: The `api_zip.zip` file, along with `app.tf` and other resource definitions, illustrate how the application is packaged and deployed onto Azure Functions or Web Apps.
- **State Management**: The `backend.tf` file ensures that Terraform maintains state in remote Azure storage.
- **Phone Number Acquisition**: Scripts like `purchase_phone_number.py` can integrate with ACS to provision phone numbers for voice interaction.
- **Environment Variables**: Before running the automation, rename the `.env.sample` file to `.env` and populate it with the required environment variables for local development and testing.

**Steps for the Recruitment Voice Assistant Automation:**
1. **Initialize and Apply Terraform:**
   - Navigate to `automation` folder.
   - Run `terraform init` to set up providers and modules.
   - Run `terraform plan` to review the changes.
   - Run `terraform apply -auto-approve` to provision resources.

2. **Validate Resources:**
   - Check Azure Portal for deployed resources.
   - Test voice interaction features using the provisioned phone number and endpoints.

By leveraging this Terraform automation, teams can rapidly deploy, update, and tear down the infrastructure required for the Recruitment Voice Assistant, ensuring consistent environments and enabling a continuous delivery pipeline.

## Understanding the Terraform Configuration Files

Below is a high-level overview of what each of the primary Terraform files does, helping you understand the role they play in provisioning and configuring the infrastructure for the Recruitment Voice Assistant solution.

### rg.tf
This file creates the **Azure Resource Group**, a fundamental organizational unit in Azure. By defining a resource group:

- You establish a logical container for all your related Azure resources.
- It simplifies management, deployment, and lifecycle operations for the infrastructure associated with the Recruitment Voice Assistant.

This ensures that all provisioned resources remain organized, easily manageable, and share a consistent location and tagging strategy.

### variables.tf
This file declares **input variables** used throughout the Terraform configuration. It provides a centralized location for specifying deployment parameters, such as:

- **Subscription and Location Details**: Variables like `subscription_id` and `location` determine where resources are deployed.
- **Naming Conventions**: Variables like `prefix`, `name`, and `environment` help ensure consistent resource naming and support multiple deployment environments.
- **Service-Specific Settings**: Variables for resources like `openai_sku`, `speech_sku`, and `acs_data_location` define the characteristics of specific services.
- **Logging and Monitoring Configuration**: Variables like `log_analytics_sku` and `log_analytics_retention_days` control the configuration of the logging and monitoring resources.
- **Other Resource Details**: Parameters like `resource_group_name`, `postgres_db_name`, and `custom_domain` allow for flexible and customizable deployments.

By adjusting these variables, you can quickly adapt the infrastructure to different environments, regions, and performance requirements without modifying the core Terraform logic.

### acs.tf
This file provisions the **Azure Communication Services (ACS)** resource, which handles telephony and messaging capabilities for the voice assistant. Specifically, it:

- Creates an ACS resource with a system-assigned identity.
- Runs a Python script (`purchase_phone_number.py`) to buy and assign a phone number from ACS.
  
By managing ACS configuration here, the voice assistant can make and receive calls, enabling its core telephony features.

> [!TIP]  
> If you prefer not to run the Python script, you can comment it out in the `acs.tf` file and purchase a phone number manually via the Azure portal. In that case, add a placeholder random string to the Terraform configuration and then manually update the phone number in the application settings. This approach provides flexibility if you encounter issues with automated phone number provisioning.

### app.tf
The `app.tf` file orchestrates the deployment and configuration of core application components, including:

- **Application Insights**: For monitoring and observability of the application’s performance.
- **Log Analytics**: For centralized logging and diagnostic data.
- **App Service Plan**: To host and scale the voice assistant’s application workload.
- **Azure Web App (API)**: Deploys the Python-based API application, sets environment variables, and integrates it with other services such as ACS, Cognitive Services, and Cosmos DB.

This file ensures that all application dependencies are properly wired together, enabling a seamless, fully functional backend for the voice assistant.

### cognitive_services.tf
The `cognitive_services.tf` file sets up a **Cognitive Services** resource that provides AI capabilities like speech recognition, language understanding, and other cognitive functionalities. Key points include:

- Configuring a Cognitive Services account (including speech features).
- Enabling a system-assigned identity for secure access and integration with other Azure services.
  
By managing Cognitive Services here, the voice assistant can process and understand user speech, offering a more intelligent and interactive call experience.

### cosmos.tf
This file provisions and configures **Azure Cosmos DB**, a globally distributed, multi-model database service, to store session data and call records for the Recruitment Voice Assistant. Specifically, it:

- Creates a **Cosmos DB account** configured for high availability and serverless capacity.
- Sets up a **SQL database** and a **SQL container** (`CallSessions`) to store call session information, including partitioning and indexing policies.
- Defines **role definitions** for data reader and data contributor, enabling granular access control for services and applications interacting with the Cosmos DB. 

By implementing Cosmos DB resources and appropriate role assignments, this file ensures the voice assistant can efficiently query, record, and manage call session data.

### event_grid.tf
This file configures **Event Grid** resources to handle event-driven integrations between Azure Communication Services (ACS) and the application's API. It:

- Creates a **system topic** that listens for ACS events, such as incoming calls.
- Sets up an **event subscription** that routes these events to the API’s designated endpoint.

By leveraging Event Grid, the Recruitment Voice Assistant can automatically respond to call-related events, enabling a real-time, event-driven workflow for the voice assistant logic.

### log_analytics.tf
This file sets up a **Log Analytics Workspace**, which centralizes and stores logs, metrics, and diagnostic data from various Azure resources. By provisioning this workspace:

- You gain a dedicated environment for querying and analyzing application and infrastructure logs.
- It can integrate with Application Insights and other services for enhanced observability and troubleshooting.
  
Overall, this resource helps ensure comprehensive monitoring, diagnostics, and performance insights for the Recruitment Voice Assistant’s environment.

### openai.tf
This file provisions and configures **Azure OpenAI resources** to provide AI-driven text generation, embeddings, and other advanced language capabilities for the Recruitment Voice Assistant. It includes:

- **Azure Cognitive Account (OpenAI Kind)**: Establishes a dedicated Azure OpenAI service instance, enabling interaction with GPT-based models.
- **OpenAI Deployments**: Deploys specific models (e.g., `gpt-4o`, `text-embedding-ada-002`) to the OpenAI service with defined SKUs and capacities. Each deployment specifies the model format, name, version, and scaling options.
- **Diagnostic Settings**: Integrates OpenAI logs and metrics with a Log Analytics Workspace, facilitating monitoring, troubleshooting, and performance analysis.

In essence, `openai.tf` sets up a scalable, monitored, and model-rich environment where the voice assistant can leverage advanced AI language capabilities.

### redis.tf
This file sets up an **Azure Redis Cache** resource to provide a high-performance, in-memory data store. Key aspects include:

- **Premium SKU with Zone Redundancy**: Ensures high availability, fault tolerance, and low-latency data access.
- **TLS Encryption and Configuration**: Enforces secure connections (minimum TLS version 1.2) and customizable memory policies.
- **Multiple Replica Support**: Creates multiple replicas for robust failover and improved reliability.

By provisioning Redis here, the voice assistant can rapidly store and retrieve session state, caching frequently accessed data and improving overall application responsiveness.


> [!IMPORTANT]
> Post-Deployment Mandatory Step
After deploying your resources with Terraform, you need to manually connect Azure Communication Services (ACS) to Azure Cognitive Services through the Azure portal. This process involves enabling a managed identity on the ACS resource and granting the appropriate role assignments to your Cognitive Services resource. For detailed instructions, please follow this guide: [Azure Communication Services and Azure Cognitive Services Integration](https://learn.microsoft.com/en-us/azure/communication-services/concepts/call-automation/azure-communication-services-azure-cognitive-services-integration).

## Testing and Validation
1. Log into the [Azure Portal](https://portal.azure.com/).
2. Navigate to the resource group(s) deployed by Terraform.
3. Confirm that all resources (e.g., ACS, Cognitive Services, Redis, Cosmos DB, and Azure Functions) are deployed.
4. Test the Recruitment Voice Assistant or your AI translation solution by invoking the endpoints, making phone calls (if integrated), and verifying application responses.

## Additional Resources
- [Terraform Documentation](https://www.terraform.io/docs/index.html)
- [Azure Subscription Management](https://docs.microsoft.com/en-us/azure/cost-management-billing/manage/create-subscription)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Azure Functions Documentation](https://docs.microsoft.com/en-us/azure/azure-functions/)
- [Azure Cognitive Services Documentation](https://docs.microsoft.com/en-us/azure/cognitive-services/)

## Project URL
[ACSOpenAIVoice](https://github.com/Aastha2024/ACSOpenAIVoice.git)

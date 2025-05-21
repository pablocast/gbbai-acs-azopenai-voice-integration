# Variables
variable "subscription_id" {
  description = "The Azure subscription ID"
  type        = string
}

# Random string
resource "random_string" "unique" {
  length  = 4
  special = false
  upper   = false
}

# Variables
variable "prefix" {
  default = "tf-"
}

variable "name" {
  default = "ai-aivoice"
}
## This could be replaced with terraform workspaces
variable "environment" {
  default = "dev"
}

variable "resource_group_name" {
  default = "accelerator-rg"
}

variable "location" {
  default = "eastus2"
}

variable "postgres_db_name" {
  default = "CallSessions"
}

variable "postgres_administrator_login" {
  default = "citus"
}

variable "custom_domain" {
  default = "ai-aivoice"
}

variable "openai_service_name" {
  default = "az-openai-service"
}
variable "public_network_access_enabled" {
  default = true
}

variable "openai_sku" {
  default = "S0"
}

variable "speech_sku" {
  default = "S0"
}

variable "acs_data_location" {
  default = "United States"
}

variable "openai_location" {
  default = "eastus2"
}

variable "voice_location" {
  default = "eastus2"
}

variable "log_analytics_sku" {
  default = "PerGB2018"
}

variable "log_analytics_workspace_name" {
  description = "Specifies the name of the log analytics workspace"
  default     = "Workspace"
  type        = string
}

variable "log_analytics_retention_days" {
  description = "Specifies the number of days of the retention policy"
  type        = number
  default     = 30
}

variable "principal_object_id" {
  description = "The object ID of the principal to assign Cosmos DB permissions to"
  type        = string
}

variable "sku" {
  description = "The pricing tier of the search service you want to create (for example, basic or standard)."
  default     = "standard"
  type        = string
  validation {
    condition     = contains(["free", "basic", "standard", "standard2", "standard3", "storage_optimized_l1", "storage_optimized_l2"], var.sku)
    error_message = "The sku must be one of the following values: free, basic, standard, standard2, standard3, storage_optimized_l1, storage_optimized_l2."
  }
}

variable "replica_count" {
  type        = number
  description = "Replicas distribute search workloads across the service. You need at least two replicas to support high availability of query workloads (not applicable to the free tier)."
  default     = 1
  validation {
    condition     = var.replica_count >= 1 && var.replica_count <= 12
    error_message = "The replica_count must be between 1 and 12."
  }
}

variable "partition_count" {
  type        = number
  description = "Partitions allow for scaling of document count as well as faster indexing by sharding your index over multiple search units."
  default     = 1
  validation {
    condition     = contains([1, 2, 3, 4, 6, 12], var.partition_count)
    error_message = "The partition_count must be one of the following values: 1, 2, 3, 4, 6, 12."
  }
}

variable "principal_id" {
  description = "The object ID of the principal to assign permissions to"
  type        = string
}

variable "storage_container_name" {
  description = "The name of the storage container."
  type        = string
  default     = "content"
}
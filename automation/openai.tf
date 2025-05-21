
variable "openai_deployments" {
  description = "(Optional) Specifies the deployments of the Azure OpenAI Service"
  type = list(object({
    name = string
    model = object({
      format  = string
      name    = string
      version = string
    })
    sku = object({
      name     = string
      capacity = number
      # tier     = string
    })
  }))
  default = [
    {
      name = "gpt-4o-realtime"
      model = {
        format  = "OpenAI"
        name    = "gpt-4o-realtime-preview"
        version = "2024-12-17"
      }
      sku = {
        name     = "GlobalStandard"
        capacity = 6
      }
    },
    {
      name = "text-embedding-3-large"
      model = {
        format  = "OpenAI"
        name    = "text-embedding-3-large"
        version = "1"
      }
      sku = {
        name     = "GlobalStandard"
        capacity = 350
      }
    }
  ]
}

resource "azurerm_cognitive_account" "openai" {
  resource_group_name           = azurerm_resource_group.rg.name
  custom_subdomain_name         = "${local.name_prefix}-openai-${random_string.unique.result}"
  kind                          = "OpenAI"
  local_auth_enabled            = true
  location                      = var.openai_location
  name                          = "${local.name_prefix}-openai"
  public_network_access_enabled = true
  sku_name                      = var.openai_sku
  tags                          = local.default_tags
  identity {
    type = "SystemAssigned"
  }

  lifecycle {
    ignore_changes = [
      tags
    ]
  }
}

resource "azurerm_cognitive_deployment" "openai_deployments" {
  for_each               = { for deployment in var.openai_deployments : deployment.name => deployment }
  cognitive_account_id   = azurerm_cognitive_account.openai.id
  name                   = each.key
  version_upgrade_option = "OnceNewDefaultVersionAvailable"


  model {
    format  = each.value.model.format
    name    = each.value.model.name
    version = each.value.model.version
  }

  sku {
    name     = each.value.sku.name
    capacity = each.value.sku.capacity
    # tier     = each.value.sku.tier
  }

}

resource "azurerm_monitor_diagnostic_setting" "settings" {
  name                       = "${local.name_prefix}-openai-diagnostic"
  target_resource_id         = azurerm_cognitive_account.openai.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.log_analytics_workspace.id

  metric {
    category = "AllMetrics"
  }

  enabled_log {
    category = "Audit"
  }

  enabled_log {
    category = "RequestResponse"
  }

  enabled_log {
    category = "Trace"
  }


}

resource "azurerm_role_assignment" "openai_user_on_search" {
  scope                 = azurerm_cognitive_account.openai.id
  role_definition_name  = "Cognitive Services OpenAI User"
  principal_id          = azurerm_search_service.search.identity[0].principal_id
}
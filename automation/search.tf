resource "azurerm_search_service" "search" {
  name                = "${local.name_prefix}-search-${random_string.unique.result}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = var.sku
  replica_count       = var.replica_count
  partition_count     = var.partition_count

  # Disable local auth
  local_authentication_enabled   = false

  # Enable semantic search
  semantic_search_sku       = "standard"

  # Enable system-assigned managed identity
  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_role_assignment" "search_index_data_reader" {
  scope                = azurerm_search_service.search.id
  role_definition_name = "Search Index Data Reader"
  principal_id         = var.principal_id
}

resource "azurerm_role_assignment" "search_index_data_contributor" {
  scope                = azurerm_search_service.search.id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = var.principal_id
}

resource "azurerm_role_assignment" "search_service_contributor" {
  scope                = azurerm_search_service.search.id
  role_definition_name = "Search Service Contributor"
  principal_id         = var.principal_id
}

resource "azurerm_storage_account" "storage" {
  name                     = replace("${local.name_prefix}st${random_string.unique.result}", "-", "")
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_kind             = "StorageV2"
  account_replication_type = "LRS"
  public_network_access_enabled = true
  shared_access_key_enabled = true
  network_rules {
      default_action = "Allow"
      bypass         = ["AzureServices"]
  }
  default_to_oauth_authentication_enabled = true
  tags = {}
}

resource "azurerm_storage_container" "content" {
  name                  = var.storage_container_name
  storage_account_id  = azurerm_storage_account.storage.id
  container_access_type = "private"
}

resource "azurerm_role_assignment" "blob_data_reader" {
  scope                = azurerm_storage_account.storage.id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = var.principal_id
  principal_type       = "User"
}

resource "azurerm_role_assignment" "blob_data_contributor" {
  scope                = azurerm_storage_account.storage.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.principal_id
  principal_type       = "User"
}

resource "azurerm_role_assignment" "storage_blob_data_reader_search_service" {
  scope                = azurerm_storage_account.storage.id
  role_definition_name = "Storage Blob Data Reader" 
  principal_id         = lookup(azurerm_search_service.search.identity[0], "principal_id")
}
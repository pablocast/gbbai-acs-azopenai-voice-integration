terraform {
  backend "azurerm" {
    resource_group_name  = "terraform"
    storage_account_name = "terraformuvx"
    container_name       = "tfstate"
    key                  = "terraform.tfstate"
    use_azuread_auth     = false
  }
}

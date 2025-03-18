
output "cognitive_deployment_id" {
  value = azurerm_cognitive_account.CognitiveServices.id
}

output "open_ai_deployments" {
  value = azurerm_cognitive_deployment.openai_deployments
}

from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
endpoint = 'https://tf-ai-aivoice-dev-search-2gbe.search.windows.net'
agent_name = "voicerag-intvect-agent"

index_client = SearchIndexClient(endpoint=endpoint, credential=credential)
index_client.delete_agent(agent_name)
print(f"Knowledge agent '{agent_name}' deleted successfully")
import re
from typing import Any
from dataclasses import dataclass
import json
from azure.search.documents.aio import SearchClient
from azure.search.documents.agent.aio import KnowledgeAgentRetrievalClient
from azure.search.documents.models import VectorizableTextQuery, QueryCaptionResult
from azure.search.documents.agent.models import (
    KnowledgeAgentAzureSearchDocReference,
    KnowledgeAgentIndexParams,
    KnowledgeAgentMessage,
    KnowledgeAgentMessageTextContent,
    KnowledgeAgentRetrievalRequest,
    KnowledgeAgentSearchActivityRecord,
)
from datetime import date
from datetime import timedelta, datetime
import random
import os
from typing import Any, Callable, Optional, TypedDict, Union, cast
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
import asyncio

load_dotenv(override=True)

async def _search_tool(
    agent_client: KnowledgeAgentRetrievalClient,
    search_index_name: str,
    reranker_threshold: float,
    max_docs_for_reranker: int,
    results_merge_strategy: str,
    top: Optional[int] | None,
    filter_add_on: Optional[str] | None,
    args: Any,
) -> str:
    print(f"Searching for '{args['query']}' in the knowledge base.")
    # Hybrid query using Azure AI Search with (optional) Semantic Ranker
    # STEP 1: Invoke agentic retrieval
    query = args["query"]
    context = args["conversation_summary"]

    messages = [
        {
            "role": "user",
            "content": f"The conversation context is: {context}. The user asked: {query}",
        }
    ]
    try:
        retrieval_results = await agent_client.retrieve(
            retrieval_request=KnowledgeAgentRetrievalRequest(
                messages=[
                    KnowledgeAgentMessage(
                        role=str(msg["role"]),
                        content=[
                            KnowledgeAgentMessageTextContent(text=str(msg["content"]))
                        ],
                    )
                    for msg in messages
                    if msg["role"] != "system"
                ],
                target_index_params=[
                    KnowledgeAgentIndexParams(
                        index_name=search_index_name,
                        reranker_threshold=reranker_threshold,
                        max_docs_for_reranker=max_docs_for_reranker,
                        filter_add_on=filter_add_on,
                        include_reference_source_data=True,
                    )
                ],
            )
        )
        documents = json.loads(retrieval_results.response[0].content[0].text)
        result = ""
        for document in documents :
            result += f"[{document['title']}]: {document['content']}\n-----\n"
        return result
    except Exception as e:
        print(f"Error during retrieval: {e}")
        return "Error during retrieval"

search_endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
search_index = os.environ["AZURE_SEARCH_INDEX"]
credentials = DefaultAzureCredential()

agent_client = KnowledgeAgentRetrievalClient(
    search_endpoint, "voicerag-intvect-agent", credentials
)

async def main():
    result = await _search_tool(
        agent_client,
        search_index_name="voicerag-intvect",
        reranker_threshold=2.2,
        max_docs_for_reranker=100,
        results_merge_strategy="interleaved",
        top=None,
        filter_add_on=None,
        args={
            "query": "Planes de cuentas de ahorro", 
            "conversation_summary": "El usuario ha sido recibido con un saludo detallado de bienvenida a la sucursal telefónica de Contoso, destacando las nuevas facilidades de la sucursal virtual. Se ofreció ayudarle con información sobre cuentas de ahorro, tarjetas de crédito, préstamos y la TRM. Ahora, el usuario ha preguntado por los planes de cuentas de ahorro disponibles."
        },
    )
    print("Result:", result)

if __name__ == "__main__":
    asyncio.run(main())

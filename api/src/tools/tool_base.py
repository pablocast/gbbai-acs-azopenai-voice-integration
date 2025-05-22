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


_search_tool_schema = {
    "type": "function",
    "name": "search",
    "description": "Search the knowledge base. The knowledge base is in Spanish, translate to and from Spanish if "
    "needed. Results are formatted as a source name first in square brackets, followed by the text "
    "content, and a line with '-----' at the end of each result.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "search query including any context needed"},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

_report_grounding_tool_schema = {
    "type": "function",
    "name": "report_grounding",
    "description": "Report use of a source from the knowledge base as part of an answer (effectively, cite the source). Sources "
    + "appear in square brackets before each knowledge base passage. Always use this tool to cite sources when responding "
    + "with information from the knowledge base.",
    "parameters": {
        "type": "object",
        "properties": {
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of source names from last statement actually used, do not include the ones not used to formulate a response",
            }
        },
        "required": ["sources"],
        "additionalProperties": False,
    },
}

_inform_loan_tool_schema = {
    "type": "function",
    "name": "inform_loan",
    "description": "Inform bank customers about their loan information including status, amount, and other details. Respond with clear and concise details about the customer's loan.",
    "parameters": {
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "The unique identifier for the bank customer",
            }
        },
        "required": ["customer_id", "query"],
        "additionalProperties": False,
    },
}

_goodbye_tool_schema = {
    "type": "function",
    "name": "goodbye",
    "description": "Say goodbye to the user with a farewell message.",
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}


_exchange_rate_tool_schema = {
    "type": "function",
    "name": "exchange_rate",
    "description": "Get the exchange rate for a given date. If date is not provided, defaults to today.",
    "parameters": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "ISO format date (YYYY-MM-DD). If not provided, defaults to today's date.",
            }
        },
        "additionalProperties": False,
    },
}


async def _goodbye_tool(args: Any) -> str:
    import jinja2

    TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..\prompts")
    JINJA_ENV = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES_DIR))

    farewell_message = JINJA_ENV.get_template("farewell.jinja").render()
    return f"Say: {farewell_message}"


# async def _search_tool(
#     search_client: SearchClient,
#     semantic_configuration: str | None,
#     identifier_field: str,
#     content_field: str,
#     embedding_field: str,
#     use_vector_query: bool,
#     args: Any,
# ) -> str:
#     print(f"Searching for '{args['query']}' in the knowledge base.")
#     # Hybrid query using Azure AI Search with (optional) Semantic Ranker
#     vector_queries = []
#     if use_vector_query:
#         vector_queries.append(
#             VectorizableTextQuery(
#                 text=args["query"], k_nearest_neighbors=50, fields=embedding_field
#             )
#         )
#     search_results = await search_client.search(
#         search_text=args["query"],
#         query_type="semantic" if semantic_configuration else "simple",
#         semantic_configuration_name=semantic_configuration,
#         top=5,
#         vector_queries=vector_queries,
#         select=", ".join([identifier_field, content_field]),
#     )
#     result = ""
#     async for r in search_results:
#         result += f"[{r[identifier_field]}]: {r[content_field]}\n-----\n"
#     return result


KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_=\-]+$")


async def _report_grounding_tool(
    search_client: SearchClient,
    identifier_field: str,
    title_field: str,
    content_field: str,
    args: Any,
) -> str:
    sources = [s for s in args["sources"] if KEY_PATTERN.match(s)]
    list = " OR ".join(sources)
    print(f"Grounding source: {list}")
    # Use search instead of filter to align with how detailt integrated vectorization indexes
    # are generated, where chunk_id is searchable with a keyword tokenizer, not filterable
    search_results = await search_client.search(
        search_text=list,
        search_fields=[identifier_field],
        select=[identifier_field, title_field, content_field],
        top=len(sources),
        query_type="full",
    )

    # If your index has a key field that's filterable but not searchable and with the keyword analyzer, you can
    # use a filter instead (and you can remove the regex check above, just ensure you escape single quotes)
    # search_results = await search_client.search(filter=f"search.in(chunk_id, '{list}')", select=["chunk_id", "title", "chunk"])

    docs = []
    async for r in search_results:
        docs.append(
            {
                "chunk_id": r[identifier_field],
                "title": r[title_field],
                "chunk": r[content_field],
            }
        )
    return json.dumps({"sources": docs})


# Function to inform bank customers about their loan. Randomly generated for demo purposes.
async def _inform_loan_tool(args: Any) -> str:
    customer_id = args["customer_id"]
    # Simulate fetching loan information from a database or service
    random_days = random.randint(1, 5)
    # Simulate a random next payment date
    due_amount = str(random.randint(100, 1000)) + " pesos"
    interest_rate = f"{random.uniform(1.0, 5.0):.2f}% efectivo anual"

    next_payment_date = (date.today() + timedelta(days=random_days)).isoformat()
    loan_info = {
        "customer_id": customer_id,
        "status": "active",
        "due_amount": due_amount,
        "interest_rate": interest_rate,
        "next_payment_date": next_payment_date,
    }
    return json.dumps(loan_info)


async def _exchange_rate_tool(args: Any) -> str:
    # If a date is provided, parse it; otherwise default to today's date.
    input_date = args.get("date")
    if input_date:
        try:
            queried_date = datetime.strptime(input_date, "%Y-%m-%d").date()
        except ValueError:
            queried_date = date.today()
    else:
        queried_date = date.today()

    # Simulate fetching exchange rate data for the given date.
    # For demo purposes, a random exchange rate is generated.
    exchange_rate = round(random.uniform(4000, 5000), 2)
    result = {
        "date": queried_date.isoformat(),
        "exchange_rate": exchange_rate,
        "currency": "USD to COP",
    }
    return json.dumps(result)


@dataclass
class Document:
    id: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    sourcepage: Optional[str] = None
    sourcefile: Optional[str] = None
    oids: Optional[list[str]] = None
    groups: Optional[list[str]] = None
    captions: Optional[list[QueryCaptionResult]] = None
    score: Optional[float] = None
    reranker_score: Optional[float] = None
    search_agent_query: Optional[str] = None

    def serialize_for_results(self) -> dict[str, Any]:
        result_dict = {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "sourcepage": self.sourcepage,
            "sourcefile": self.sourcefile,
            "oids": self.oids,
            "groups": self.groups,
            "captions": (
                [
                    {
                        "additional_properties": caption.additional_properties,
                        "text": caption.text,
                        "highlights": caption.highlights,
                    }
                    for caption in self.captions
                ]
                if self.captions
                else []
            ),
            "score": self.score,
            "reranker_score": self.reranker_score,
            "search_agent_query": self.search_agent_query,
        }
        return result_dict


async def _search_tool(
    agent_client: KnowledgeAgentRetrievalClient,
    search_index_name: str,
    reranker_threshold: float,
    max_docs_for_reranker: int,
    filter_add_on: Optional[str] | None,
    args: Any,
) -> str:
    print(f"Searching for '{args['query']}' in the knowledge base.")
    # Hybrid query using Azure AI Search with (optional) Semantic Ranker
    # STEP 1: Invoke agentic retrieval
    query = args.get("query", "")

    messages = [
        {
            "role": "user",
            "content": f"The user asked: {query}",
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

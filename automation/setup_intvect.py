import json
import logging
import os
import subprocess

from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.search.documents.indexes.models import (
    AzureOpenAIEmbeddingSkill,
    AzureOpenAIVectorizerParameters,
    AzureOpenAIVectorizer,
    FieldMapping,
    HnswAlgorithmConfiguration,
    HnswParameters,
    IndexProjectionMode,
    InputFieldMappingEntry,
    OutputFieldMappingEntry,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchIndexer,
    SearchIndexerDataContainer,
    SearchIndexerDataSourceConnection,
    SearchIndexerDataSourceType,
    SearchIndexerIndexProjection,
    SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters,
    SearchIndexerSkillset,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    SplitSkill,
    VectorSearch,
    VectorSearchAlgorithmMetric,
    VectorSearchProfile,
    KnowledgeAgent,
    KnowledgeAgentAzureOpenAIModel,
    KnowledgeAgentRequestLimits,
    KnowledgeAgentTargetIndex,
)
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv(override=True)


def setup_index(
    azure_credential,
    index_name,
    azure_search_endpoint,
    azure_storage_connection_string,
    azure_storage_container,
    azure_openai_embedding_endpoint,
    azure_openai_embedding_deployment,
    azure_openai_embedding_model,
    azure_openai_embeddings_dimensions,
    searchagent_max_output_tokens,
    azure_openai_searchagent_deployment,
    azure_openai_searchagent_model
):
    index_client = SearchIndexClient(azure_search_endpoint, azure_credential)
    indexer_client = SearchIndexerClient(azure_search_endpoint, azure_credential)

    data_source_connections = indexer_client.get_data_source_connections()
    if index_name in [ds.name for ds in data_source_connections]:
        logger.info(
            f"Data source connection {index_name} already exists, not re-creating"
        )
    else:
        logger.info(f"Creating data source connection: {index_name}")
        indexer_client.create_data_source_connection(
            data_source_connection=SearchIndexerDataSourceConnection(
                name=index_name,
                type=SearchIndexerDataSourceType.AZURE_BLOB,
                connection_string=azure_storage_connection_string,
                container=SearchIndexerDataContainer(name=azure_storage_container),
            )
        )

    index_names = [index.name for index in index_client.list_indexes()]
    if index_name in index_names:
        logger.info(f"Index {index_name} already exists, not re-creating")
    else:
        logger.info(f"Creating index: {index_name}")
        index_client.create_index(
            SearchIndex(
                name=index_name,
                fields=[
                    SearchableField(
                        name="chunk_id",
                        key=True,
                        analyzer_name="keyword",
                        sortable=True,
                    ),
                    SimpleField(
                        name="parent_id",
                        type=SearchFieldDataType.String,
                        filterable=True,
                    ),
                    SearchableField(name="title"),
                    SearchableField(name="chunk"),
                    SearchField(
                        name="text_vector",
                        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                        vector_search_dimensions=EMBEDDINGS_DIMENSIONS,
                        vector_search_profile_name="vp",
                        stored=True,
                        hidden=False,
                    ),
                ],
                vector_search=VectorSearch(
                    algorithms=[
                        HnswAlgorithmConfiguration(
                            name="algo",
                            parameters=HnswParameters(
                                metric=VectorSearchAlgorithmMetric.COSINE
                            ),
                        )
                    ],
                    vectorizers=[
                        AzureOpenAIVectorizer(
                            vectorizer_name="openai_vectorizer",
                            parameters=AzureOpenAIVectorizerParameters(
                                resource_url=azure_openai_embedding_endpoint,
                                deployment_name=azure_openai_embedding_deployment,
                                model_name=azure_openai_embedding_model,
                            ),
                        )
                    ],
                    profiles=[
                        VectorSearchProfile(
                            name="vp",
                            algorithm_configuration_name="algo",
                            vectorizer_name="openai_vectorizer",
                        )
                    ],
                ),
                semantic_search=SemanticSearch(
                    configurations=[
                        SemanticConfiguration(
                            name="default",
                            prioritized_fields=SemanticPrioritizedFields(
                                title_field=SemanticField(field_name="title"),
                                content_fields=[SemanticField(field_name="chunk")],
                            ),
                        )
                    ],
                    default_configuration_name="default",
                ),
            )
        )

    skillsets = indexer_client.get_skillsets()
    if index_name in [skillset.name for skillset in skillsets]:
        logger.info(f"Skillset {index_name} already exists, not re-creating")
    else:
        logger.info(f"Creating skillset: {index_name}")
        indexer_client.create_skillset(
            skillset=SearchIndexerSkillset(
                name=index_name,
                skills=[
                    SplitSkill(
                        text_split_mode="pages",
                        context="/document",
                        maximum_page_length=2000,
                        page_overlap_length=500,
                        inputs=[
                            InputFieldMappingEntry(
                                name="text", source="/document/content"
                            )
                        ],
                        outputs=[
                            OutputFieldMappingEntry(
                                name="textItems", target_name="pages"
                            )
                        ],
                    ),
                    AzureOpenAIEmbeddingSkill(
                        context="/document/pages/*",
                        resource_url=azure_openai_embedding_endpoint,
                        api_key=None,
                        deployment_name=azure_openai_embedding_deployment,
                        model_name=azure_openai_embedding_model,
                        dimensions=azure_openai_embeddings_dimensions,
                        inputs=[
                            InputFieldMappingEntry(
                                name="text", source="/document/pages/*"
                            )
                        ],
                        outputs=[
                            OutputFieldMappingEntry(
                                name="embedding", target_name="text_vector"
                            )
                        ],
                    ),
                ],
                index_projection=SearchIndexerIndexProjection(
                    selectors=[
                        SearchIndexerIndexProjectionSelector(
                            target_index_name=index_name,
                            parent_key_field_name="parent_id",
                            source_context="/document/pages/*",
                            mappings=[
                                InputFieldMappingEntry(
                                    name="chunk", source="/document/pages/*"
                                ),
                                InputFieldMappingEntry(
                                    name="text_vector",
                                    source="/document/pages/*/text_vector",
                                ),
                                InputFieldMappingEntry(
                                    name="title",
                                    source="/document/metadata_storage_name",
                                ),
                            ],
                        )
                    ],
                    parameters=SearchIndexerIndexProjectionsParameters(
                        projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS
                    ),
                ),
            )
        )

    indexers = indexer_client.get_indexers()
    if index_name in [indexer.name for indexer in indexers]:
        logger.info(f"Indexer {index_name} already exists, not re-creating")
    else:
        indexer_client.create_indexer(
            indexer=SearchIndexer(
                name=index_name,
                data_source_name=index_name,
                skillset_name=index_name,
                target_index_name=index_name,
                field_mappings=[
                    FieldMapping(
                        source_field_name="metadata_storage_name",
                        target_field_name="title",
                    )
                ],
            )
        )

    # Add Agent
    agent_name = f"{index_name}-agent"
    if agent_name in [
        agent.name for agent in index_client.list_agents()
    ]:
        logger.info(f"Agent {index_name}-agent already exists, not re-creating")
    else:
        logger.info(f"Creating agent: {index_name}-agent")
        index_client.create_or_update_agent(
            agent=KnowledgeAgent(
                name=f"{index_name}-agent",
                target_indexes=[KnowledgeAgentTargetIndex(index_name=index_name)],
                models=[
                    KnowledgeAgentAzureOpenAIModel(
                        azure_open_ai_parameters=AzureOpenAIVectorizerParameters(
                            resource_url=azure_openai_embedding_endpoint,
                            deployment_name=azure_openai_embedding_deployment,
                            model_name=azure_openai_embedding_model,
                        )
                    )
                ],
                request_limits=KnowledgeAgentRequestLimits(
                    max_output_size=searchagent_max_output_tokens
                ),
            )
        )
   
def upload_documents(
    azure_credential,
    indexer_name,
    azure_search_endpoint,
    azure_storage_endpoint,
    azure_storage_container,
):
    indexer_client = SearchIndexerClient(azure_search_endpoint, azure_credential)
    # Upload the documents in /data folder to the blob storage container
    blob_client = BlobServiceClient(
        account_url=azure_storage_endpoint,
        credential=azure_credential,
        max_single_put_size=4 * 1024 * 1024,
    )
    container_client = blob_client.get_container_client(azure_storage_container)
    if not container_client.exists():
        container_client.create_container()
    existing_blobs = [blob.name for blob in container_client.list_blobs()]

    # Open each file in /data folder
    for file in os.scandir("data"):
        with open(file.path, "rb") as opened_file:
            filename = os.path.basename(file.path)
            # Check if blob already exists
            if filename in existing_blobs:
                logger.info("Blob already exists, skipping file: %s", filename)
            else:
                logger.info("Uploading blob for file: %s", filename)
                blob_client = container_client.upload_blob(
                    filename, opened_file, overwrite=True
                )

    # Start the indexer
    try:
        indexer_client.run_indexer(indexer_name)
        logger.info(
            "Indexer started. Any unindexed blobs should be indexed in a few minutes, check the Azure Portal for status."
        )
    except ResourceExistsError:
        logger.info("Indexer already running, not starting again")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(message)s", datefmt="[%X]")
    logger = logging.getLogger("voicerag")
    logger.setLevel(logging.INFO)

    logger = logging.getLogger("voicerag")
    # Used to name index, indexer, data source and skillset
    AZURE_SEARCH_INDEX = os.environ["AZURE_SEARCH_INDEX"]
    AZURE_OPENAI_EMBEDDING_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]
    AZURE_OPENAI_EMBEDDING_MODEL = os.environ["AZURE_OPENAI_EMBEDDING_MODEL"]
    EMBEDDINGS_DIMENSIONS = 3072
    AZURE_SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
    AZURE_STORAGE_ENDPOINT = os.environ["AZURE_STORAGE_ENDPOINT"]
    AZURE_STORAGE_CONNECTION_STRING = os.environ["MANAGED_IDENTITY_RESOURCE_ID"]
    AZURE_STORAGE_CONTAINER = os.environ["AZURE_STORAGE_CONTAINER"]
    AZURE_OPENAI_SEARCHAGENT_DEPLOYMENT = os.environ["AZURE_OPENAI_SEARCHAGENT_DEPLOYMENT"]
    AZURE_OPENAI_SEARCHAGENT_MODEL = os.environ["AZURE_OPENAI_SEARCHAGENT_MODEL"]
    AZURE_SEARCH_AGENT_MAX_OUTPUT_TOKENS = os.environ["AZURE_SEARCH_AGENT_MAX_OUTPUT_TOKENS"]
    azure_credential = DefaultAzureCredential()

    setup_index(
        azure_credential,
        index_name=AZURE_SEARCH_INDEX,
        azure_search_endpoint=AZURE_SEARCH_ENDPOINT,
        azure_storage_connection_string=AZURE_STORAGE_CONNECTION_STRING,
        azure_storage_container=AZURE_STORAGE_CONTAINER,
        azure_openai_embedding_endpoint=AZURE_OPENAI_EMBEDDING_ENDPOINT,
        azure_openai_embedding_deployment=AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
        azure_openai_embedding_model=AZURE_OPENAI_EMBEDDING_MODEL,
        azure_openai_embeddings_dimensions=EMBEDDINGS_DIMENSIONS,
        searchagent_max_output_tokens=AZURE_SEARCH_AGENT_MAX_OUTPUT_TOKENS,
        azure_openai_searchagent_deployment=AZURE_OPENAI_SEARCHAGENT_DEPLOYMENT,
        azure_openai_searchagent_model=AZURE_OPENAI_SEARCHAGENT_MODEL
    )

    upload_documents(
        azure_credential,
        indexer_name=AZURE_SEARCH_INDEX,
        azure_search_endpoint=AZURE_SEARCH_ENDPOINT,
        azure_storage_endpoint=AZURE_STORAGE_ENDPOINT,
        azure_storage_container=AZURE_STORAGE_CONTAINER,
    )

import os
from dotenv import load_dotenv
import base64
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from llama_index.readers.web import WholeSiteReader
from azure.search.documents.indexes.models import (
    SimpleField, SearchField, SearchFieldDataType,
    VectorSearch, HnswAlgorithmConfiguration, VectorSearchProfile,
    SearchIndex
)
import openai
from openai import AzureOpenAI

load_dotenv()
search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
search_key = os.getenv("AZURE_SEARCH_API_KEY")
index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")
openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
openai_key = os.getenv("AZURE_OPENAI_API_KEY")
openai_model = os.getenv("AZURE_OPENAI_MODEL")
openai_version = os.getenv("AZURE_OPENAI_API_VERSION")

client = AzureOpenAI(
    azure_endpoint=openai_endpoint,
    api_key=openai_key,
    api_version=openai_version
)

from azure.core.credentials import AzureKeyCredential
credential = AzureKeyCredential(search_key)
index_client = SearchIndexClient(endpoint=search_endpoint, credential=credential)
search_client = SearchClient(endpoint=search_endpoint, index_name=index_name, credential=credential)

fields = [
    SimpleField(name="id", type="Edm.String", key=True),
    SearchField(name="content", type=SearchFieldDataType.String, searchable=True, retrievable=True),
    SearchField(
        name="contentVector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        searchable=True, retrievable=True,
        vector_search_dimensions=1536,
        vector_search_profile_name="my-vector-profile"
    )
]
vector_search = VectorSearch(
    algorithms=[HnswAlgorithmConfiguration(name="my-vector-algo")],
    profiles=[VectorSearchProfile(name="my-vector-profile", algorithm_configuration_name="my-vector-algo")]
)
index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)
try:
    index_client.create_index(index)
    print(f"Created index '{index_name}' in Azure Search.")
except Exception as e:
    print(f"Index might already exist: {e}")

reader = WholeSiteReader(prefix="https://aymenfurter.ch", max_depth=2)
documents = reader.load_data(base_url="https://aymenfurter.ch")
print(f"Crawled {len(documents)} pages from the website.")

docs_to_upload = []
for i, doc in enumerate(documents, start=1):
    text = doc.text or ""
    response = client.embeddings.create(input=text, model=openai_model)
    embedding_vector = response.data[0].embedding
    url = doc.extra_info.get("URL", f"doc{i}")
    encoded_id = base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8')
    docs_to_upload.append({"id": encoded_id, "content": text, "contentVector": embedding_vector})

result = search_client.upload_documents(documents=docs_to_upload)
print(f"{'Successfully uploaded' if result[0].succeeded else 'Failed to upload'} {len(docs_to_upload)} documents to index '{index_name}'" + (f": {result[0].error_message}" if not result[0].succeeded else "."))

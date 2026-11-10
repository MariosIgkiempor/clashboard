import os

from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()  # reads .env from the project root (current directory)


def blob_service() -> BlobServiceClient:
    return BlobServiceClient.from_connection_string(os.environ["AZURE_STORAGE_CONNECTION_STRING"])

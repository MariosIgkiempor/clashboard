import os
from pathlib import Path

from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()  # reads .env from the project root (current directory)

# Where Claude Code writes transcripts. Override with CLAUDE_PROJECTS_DIR in .env.
CLAUDE_PROJECTS_DIR = Path(os.environ.get("CLAUDE_PROJECTS_DIR") or Path.home() / ".claude" / "projects").expanduser()


def blob_service() -> BlobServiceClient:
    return BlobServiceClient.from_connection_string(os.environ["AZURE_STORAGE_CONNECTION_STRING"])

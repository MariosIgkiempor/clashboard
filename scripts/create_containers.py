"""Create the bronze/silver/gold containers. Safe to re-run."""
from azure.core.exceptions import ResourceExistsError

from common import blob_service

CONTAINERS = ["bronze", "silver", "gold"]

svc = blob_service()
for name in CONTAINERS:
    try:
        svc.create_container(name)
        print(f"created  {name}")
    except ResourceExistsError:
        print(f"exists   {name}")

print("containers now:", sorted(c.name for c in svc.list_containers()))

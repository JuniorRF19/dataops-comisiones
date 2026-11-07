"""
Lista los contenedores y blobs del Storage (Azurite o Azure) para evidenciar
el contenido de las zonas raw-<env> y lake-<env>.

    python scripts/list_lake.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline import blob_service, load_dotenv  # noqa: E402


def main() -> int:
    load_dotenv()
    svc = blob_service()
    print(f"Storage: {svc.url}")
    for container in svc.list_containers():
        print(f"\n[{container.name}]")
        for blob in svc.get_container_client(container.name).list_blobs():
            print(f"  {blob.name:<70} {blob.size:>8} bytes  {blob.last_modified:%Y-%m-%d %H:%M}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

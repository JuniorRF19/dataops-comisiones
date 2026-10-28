"""
Prepara el Storage del ambiente: crea los contenedores raw-<env> / lake-<env>
y sube el CSV de comisiones del periodo a raw-<env> (simula la llegada del archivo).

    python scripts/seed_blob.py --env dev --periodo 202610
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline import ROOT, blob_service, load_config, load_dotenv, setup_logging  # noqa: E402

log = logging.getLogger("seed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True, choices=["dev", "qa", "prd"])
    parser.add_argument("--periodo")
    args = parser.parse_args()
    setup_logging()
    load_dotenv()

    cfg = load_config(args.env, args.periodo)
    st = cfg["storage"]
    svc = blob_service()

    for name in (st["raw_container"], st["lake_container"]):
        container = svc.get_container_client(name)
        if container.exists():
            log.info("Contenedor %s ya existe", name)
        else:
            container.create_container()
            log.info("Contenedor %s creado", name)

    local_csv = ROOT / "data" / Path(st["csv_blob"]).name
    if not local_csv.exists():
        log.error("No existe %s", local_csv)
        return 1
    svc.get_blob_client(st["raw_container"], st["csv_blob"]).upload_blob(
        local_csv.read_bytes(), overwrite=True
    )
    log.info("Subido %s -> %s/%s", local_csv.name, st["raw_container"], st["csv_blob"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

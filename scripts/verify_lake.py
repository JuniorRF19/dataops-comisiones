"""
Prueba post-despliegue (smoke test): lee el Parquet publicado en el Data Lake
del ambiente y valida su contenido.

    python scripts/verify_lake.py --env qa --periodo 202610 [--download out]
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import quality  # noqa: E402
from app.pipeline import blob_service, load_config, load_dotenv, setup_logging  # noqa: E402

log = logging.getLogger("verify")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True, choices=["dev", "qa", "prd"])
    parser.add_argument("--periodo")
    parser.add_argument("--download", type=Path, help="Carpeta donde guardar el Parquet")
    args = parser.parse_args()
    setup_logging()
    load_dotenv()

    cfg = load_config(args.env, args.periodo)
    st = cfg["storage"]
    blob = blob_service().get_blob_client(st["lake_container"], st["parquet_blob"])
    if not blob.exists():
        log.error("No existe %s/%s", st["lake_container"], st["parquet_blob"])
        return 1

    data = blob.download_blob().readall()
    df = pd.read_parquet(io.BytesIO(data))
    log.info("Parquet %s/%s: %s filas, %s columnas",
             st["lake_container"], st["parquet_blob"], len(df), len(df.columns))
    log.info("Columnas: %s", list(df.columns))
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(df.head(10).to_string(index=False))

    if args.download:
        args.download.mkdir(parents=True, exist_ok=True)
        (args.download / Path(st["parquet_blob"]).name).write_bytes(data)

    errors = quality.check(df, min_rows=cfg["quality"]["min_rows"])
    if errors and cfg["quality"]["strict"]:
        for e in errors:
            log.error("Verificación: %s", e)
        return 2
    log.info("Verificación %s OK", args.env.upper())
    return 0


if __name__ == "__main__":
    sys.exit(main())

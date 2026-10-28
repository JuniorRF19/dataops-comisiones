"""
Pipeline de comisiones (equivalente Python de un pipeline de Azure Data Factory).

  1. Extract  : rrhh.empleado (PostgreSQL)  +  CSV de comisiones (Blob Storage)
  2. Transform: JOIN por empleado_id  ->  salario_total = mnt_salario + comision
  3. Quality  : reglas de calidad (gate)
  4. Load     : Parquet (+ Excel) en el Data Lake  lake-<env>/gold/comisiones/periodo=AAAAMM/

Uso:
    python -m app.pipeline --env dev --periodo 202610 [--local-out out]

Secretos y conexiones por variables de entorno (nunca en el repo):
    PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD, AZURE_STORAGE_CONNECTION_STRING
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2
import yaml
from azure.storage.blob import BlobServiceClient

from app import quality
from app.transform import calculate_total_salary, read_commissions_csv

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("pipeline")

# Cadena pública y documentada del emulador Azurite (no es un secreto)
AZURITE_LOCAL = (
    "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/"
    "K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
)


# ───────────────────────────── Configuración ───────────────────────────── #
def load_config(env: str, periodo: str | None = None) -> dict:
    path = ROOT / "config" / f"{env}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No existe la configuración {path}")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["periodo"] = str(periodo or cfg["periodo"])
    for key in ("csv_blob", "parquet_blob", "excel_blob"):
        cfg["storage"][key] = cfg["storage"][key].format(periodo=cfg["periodo"])
    return cfg


def blob_service() -> BlobServiceClient:
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING", AZURITE_LOCAL)
    return BlobServiceClient.from_connection_string(conn)


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
    logging.getLogger("azure").setLevel(logging.WARNING)  # oculta el log HTTP del SDK


def load_dotenv() -> None:
    """Carga un .env local (solo para ejecuciones fuera de Jenkins)."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# ─────────────────────────────── Extract ──────────────────────────────── #
def extract_empleados(cfg: dict) -> pd.DataFrame:
    table = f'{cfg["db"]["schema"]}.{cfg["db"]["table"]}'
    query = (
        "SELECT empleado_id, nom_empleado, ape_empleado, cod_cargo, "
        f"cod_departamento, mnt_salario FROM {table}"
    )
    with psycopg2.connect(
        host=os.environ["PG_HOST"],
        port=int(os.getenv("PG_PORT", "5432")),
        dbname=os.environ["PG_DB"],
        user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"],
        connect_timeout=15,
        client_encoding="UTF8",
    ) as conn, conn.cursor() as cur:
        cur.execute(query)
        df = pd.DataFrame(cur.fetchall(), columns=[c[0] for c in cur.description])
    log.info("Extract SQL  : %s filas de %s", len(df), table)
    return df


def extract_comisiones(cfg: dict, svc: BlobServiceClient) -> pd.DataFrame:
    st = cfg["storage"]
    blob = svc.get_blob_client(st["raw_container"], st["csv_blob"])
    df = read_commissions_csv(blob.download_blob().readall())
    log.info("Extract Blob : %s filas de %s/%s", len(df), st["raw_container"], st["csv_blob"])
    return df


# ───────────────────────────────── Load ───────────────────────────────── #
def load_lake(df: pd.DataFrame, cfg: dict, svc: BlobServiceClient, local_out: Path | None):
    st = cfg["storage"]
    container = svc.get_container_client(st["lake_container"])
    if not container.exists():
        container.create_container()

    parquet = io.BytesIO()
    df.to_parquet(parquet, engine="pyarrow", index=False)
    excel = io.BytesIO()
    df.assign(fecha_proceso=df["fecha_proceso"].dt.tz_localize(None)).to_excel(
        excel, index=False, engine="openpyxl"
    )

    outputs = {st["parquet_blob"]: parquet.getvalue(), st["excel_blob"]: excel.getvalue()}
    for name, data in outputs.items():
        container.upload_blob(name, data, overwrite=True)
        log.info("Load Lake    : %s/%s (%s bytes)", st["lake_container"], name, len(data))
        if local_out:
            target = local_out / Path(name).name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


# ───────────────────────────────── Main ───────────────────────────────── #
def run(env: str, periodo: str | None, local_out: Path | None) -> pd.DataFrame:
    cfg = load_config(env, periodo)
    log.info("=== Pipeline comisiones | env=%s | periodo=%s ===", env, cfg["periodo"])
    svc = blob_service()

    empleados = extract_empleados(cfg)
    comisiones = extract_comisiones(cfg, svc)
    df = calculate_total_salary(empleados, comisiones, cfg["periodo"])
    log.info("Transform    : %s filas tras JOIN por empleado_id", len(df))

    errors = quality.check(df, min_rows=cfg["quality"]["min_rows"])
    if errors:
        for e in errors:
            log.error("Quality      : %s", e)
        if cfg["quality"]["strict"]:
            raise quality.QualityError(f"{len(errors)} regla(s) de calidad incumplidas")
        log.warning("Quality      : modo no estricto en %s, se continúa", env)
    else:
        log.info("Quality      : OK (todas las reglas cumplidas)")

    load_lake(df, cfg, svc, local_out)
    log.info("Resumen      : salario_total suma %.2f", df["salario_total"].sum())
    return df


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--env", required=True, choices=["dev", "qa", "prd"])
    parser.add_argument("--periodo", help="AAAAMM (por defecto el de config/<env>.yaml)")
    parser.add_argument("--local-out", type=Path, help="Copia local de las salidas")
    args = parser.parse_args(argv)

    setup_logging()
    load_dotenv()
    try:
        run(args.env, args.periodo, args.local_out)
    except quality.QualityError as exc:
        log.error("QUALITY GATE FALLIDO: %s", exc)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

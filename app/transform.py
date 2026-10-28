"""Transformaciones puras (sin I/O) para poder probarlas con pytest."""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from datetime import datetime, timezone

import pandas as pd

log = logging.getLogger(__name__)

# Columnas que se esperan del CSV una vez normalizadas
CSV_COLUMNS = {"empleado_id", "nombre_y_apellido", "comision"}


def normalize_column(name: str) -> str:
    """'Comisión' -> 'comision', 'Nombre y Apellido' -> 'nombre_y_apellido'."""
    ascii_name = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", "_", ascii_name.strip().lower()).strip("_")


def read_commissions_csv(raw: bytes) -> pd.DataFrame:
    """Lee el CSV de comisiones (separador ';') tolerando UTF-8 (con BOM) o Latin-1."""
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    df = pd.read_csv(io.StringIO(text), sep=";")
    df.columns = [normalize_column(c) for c in df.columns]

    missing = CSV_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"El CSV no tiene las columnas esperadas: {sorted(missing)}")

    df = df.rename(columns={"nombre_y_apellido": "nombre_apellido_csv"})
    df["empleado_id"] = pd.to_numeric(df["empleado_id"], errors="coerce").astype("Int64")
    df["comision"] = pd.to_numeric(df["comision"], errors="coerce")
    return df


def calculate_total_salary(
    empleados: pd.DataFrame, comisiones: pd.DataFrame, periodo: str
) -> pd.DataFrame:
    """JOIN por empleado_id y cálculo de salario_total = mnt_salario + comision."""
    empleados = empleados.copy()
    empleados["empleado_id"] = empleados["empleado_id"].astype("Int64")
    empleados["mnt_salario"] = pd.to_numeric(empleados["mnt_salario"], errors="coerce")

    ids_csv = set(comisiones["empleado_id"].dropna())
    ids_db = set(empleados["empleado_id"].dropna())
    sin_empleado = sorted(int(i) for i in ids_csv - ids_db)
    sin_comision = sorted(int(i) for i in ids_db - ids_csv)
    if sin_empleado:
        log.warning("IDs del CSV sin empleado en BD (se descartan): %s", sin_empleado)
    if sin_comision:
        log.info("Empleados de BD sin comisión en el periodo: %s", sin_comision)

    df = comisiones.merge(empleados, on="empleado_id", how="inner")
    df["salario_total"] = (df["mnt_salario"] + df["comision"]).round(2)
    df["periodo"] = periodo
    df["fecha_proceso"] = datetime.now(timezone.utc).replace(microsecond=0)

    columns = [
        "periodo",
        "empleado_id",
        "nom_empleado",
        "ape_empleado",
        "cod_cargo",
        "cod_departamento",
        "mnt_salario",
        "comision",
        "salario_total",
        "fecha_proceso",
    ]
    return df[columns].sort_values("empleado_id").reset_index(drop=True)

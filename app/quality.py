"""Reglas de calidad de datos (quality gate) sobre la tabla consolidada."""

from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = ["empleado_id", "mnt_salario", "comision", "salario_total"]


class QualityError(Exception):
    """Se lanza cuando la tabla no cumple las reglas de calidad en modo estricto."""


def check(df: pd.DataFrame, min_rows: int = 1) -> list[str]:
    """Devuelve la lista de reglas incumplidas (vacía si todo está OK)."""
    errors: list[str] = []

    if len(df) < min_rows:
        errors.append(f"Se esperaban al menos {min_rows} filas y hay {len(df)}")

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        errors.append(f"Faltan columnas: {missing}")
        return errors

    nulls = df[REQUIRED_COLUMNS].isna().sum()
    for column, count in nulls[nulls > 0].items():
        errors.append(f"{count} valores nulos en '{column}'")

    duplicated = df.loc[df["empleado_id"].duplicated(), "empleado_id"].tolist()
    if duplicated:
        errors.append(f"empleado_id duplicados: {duplicated}")

    negative = df.loc[df["comision"] < 0, "empleado_id"].tolist()
    if negative:
        errors.append(f"Comisiones negativas para empleado_id: {negative}")

    no_salary = df.loc[df["mnt_salario"] <= 0, "empleado_id"].tolist()
    if no_salary:
        errors.append(f"Salario no positivo para empleado_id: {no_salary}")

    expected = (df["mnt_salario"] + df["comision"]).round(2)
    mismatch = df.loc[(expected - df["salario_total"]).abs() > 0.01, "empleado_id"]
    if not mismatch.empty:
        errors.append(f"salario_total != salario + comisión en: {mismatch.tolist()}")

    return errors

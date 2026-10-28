import pandas as pd
import pytest

from app.transform import calculate_total_salary, normalize_column, read_commissions_csv

CSV_UTF8 = (
    "empleado_id;Nombre y Apellido;Comisión\r\n"
    "1;Juan, Pérez;9000\r\n2;María, Gómez;8250\r\n99;Sin, BD;100\r\n"
)


@pytest.fixture
def empleados():
    return pd.DataFrame(
        {
            "empleado_id": [1, 2, 3],
            "nom_empleado": ["Ana", "Carlos", "Sofía"],
            "ape_empleado": ["Pérez", "López", "Martínez"],
            "cod_cargo": ["C1", "C2", "C3"],
            "cod_departamento": ["D1", "D1", "D2"],
            "mnt_salario": [1800.00, 2500.50, 2200.75],
        }
    )


@pytest.mark.parametrize(
    "raw, expected",
    [("Comisión", "comision"), ("Nombre y Apellido", "nombre_y_apellido"), (" empleado_id ", "empleado_id")],
)
def test_normalize_column(raw, expected):
    assert normalize_column(raw) == expected


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "latin-1"])
def test_read_csv_any_encoding(encoding):
    df = read_commissions_csv(CSV_UTF8.encode(encoding))
    assert list(df.columns) == ["empleado_id", "nombre_apellido_csv", "comision"]
    assert df["comision"].tolist() == [9000, 8250, 100]


def test_read_csv_missing_column():
    with pytest.raises(ValueError, match="comision"):
        read_commissions_csv(b"empleado_id;Nombre\n1;x\n")


def test_join_and_salario_total(empleados):
    comisiones = read_commissions_csv(CSV_UTF8.encode())
    df = calculate_total_salary(empleados, comisiones, "202610")

    assert df["empleado_id"].tolist() == [1, 2]  # inner join: 99 y 3 quedan fuera
    assert df["salario_total"].tolist() == [10800.00, 10750.50]
    assert (df["periodo"] == "202610").all()


def test_salario_total_accepts_decimal(empleados):
    from decimal import Decimal

    empleados["mnt_salario"] = [Decimal("1800.00"), Decimal("2500.50"), Decimal("2200.75")]
    comisiones = read_commissions_csv(CSV_UTF8.encode())
    df = calculate_total_salary(empleados, comisiones, "202610")
    assert df.loc[0, "salario_total"] == pytest.approx(10800.0)


def test_output_columns(empleados):
    comisiones = read_commissions_csv(CSV_UTF8.encode())
    df = calculate_total_salary(empleados, comisiones, "202610")
    assert {"empleado_id", "mnt_salario", "comision", "salario_total", "fecha_proceso"} <= set(df.columns)

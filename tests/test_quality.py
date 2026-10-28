import pandas as pd
import pytest

from app import quality


@pytest.fixture
def good():
    return pd.DataFrame(
        {
            "empleado_id": [1, 2],
            "mnt_salario": [1000.0, 2000.0],
            "comision": [100.0, 0.0],
            "salario_total": [1100.0, 2000.0],
        }
    )


def test_good_data_passes(good):
    assert quality.check(good) == []


def test_empty_fails(good):
    assert any("al menos" in e for e in quality.check(good.iloc[0:0]))


def test_duplicate_ids(good):
    df = pd.concat([good, good.iloc[[0]]])
    assert any("duplicados" in e for e in quality.check(df))


def test_negative_commission(good):
    good.loc[0, ["comision", "salario_total"]] = [-50.0, 950.0]
    assert any("negativas" in e for e in quality.check(good))


def test_null_commission(good):
    good.loc[1, "comision"] = None
    assert any("nulos en 'comision'" in e for e in quality.check(good))


def test_wrong_total(good):
    good.loc[1, "salario_total"] = 9999.0
    assert any("salario_total" in e for e in quality.check(good))


def test_missing_columns():
    assert any("Faltan columnas" in e for e in quality.check(pd.DataFrame({"empleado_id": [1]})))

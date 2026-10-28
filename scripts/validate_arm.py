"""
Validación estática (CI) de las plantillas ARM de infra/arm:
  - JSON válido y con $schema / contentVersion / resources
  - cada parameters.<env>.json solo usa parámetros declarados en la plantilla
  - todos los parámetros obligatorios (sin defaultValue) tienen valor
  - valores dentro de allowedValues
  - nombre de Storage Account resultante válido (3-24, minúsculas y dígitos)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ARM_DIR = Path(__file__).resolve().parent.parent / "infra" / "arm"
ENVS = ("dev", "qa", "prd")


def validate() -> list[str]:
    errors: list[str] = []
    template = json.loads((ARM_DIR / "azuredeploy.json").read_text(encoding="utf-8"))
    for key in ("$schema", "contentVersion", "parameters", "resources"):
        if key not in template:
            errors.append(f"azuredeploy.json: falta '{key}'")
    declared = template.get("parameters", {})
    required = {k for k, v in declared.items() if "defaultValue" not in v}

    for env in ENVS:
        file = ARM_DIR / f"parameters.{env}.json"
        if not file.exists():
            errors.append(f"No existe {file.name}")
            continue
        values = {k: v["value"] for k, v in json.loads(file.read_text("utf-8"))["parameters"].items()}

        for name in values.keys() - declared.keys():
            errors.append(f"{file.name}: parámetro '{name}' no declarado en la plantilla")
        for name in required - values.keys():
            errors.append(f"{file.name}: falta el parámetro obligatorio '{name}'")
        for name, value in values.items():
            allowed = declared.get(name, {}).get("allowedValues")
            if allowed and value not in allowed:
                errors.append(f"{file.name}: '{name}'={value!r} no está en {allowed}")
        if values.get("environment") != env:
            errors.append(f"{file.name}: environment debería ser '{env}'")

        account = f"az{values.get('initials', '')}{env}dedlslake".lower()
        if not re.fullmatch(r"[a-z0-9]{3,24}", account):
            errors.append(f"{file.name}: nombre de Storage Account inválido '{account}'")
        else:
            print(f"[{env}] Storage Account: {account}")
    return errors


if __name__ == "__main__":
    problems = validate()
    for p in problems:
        print(f"ERROR: {p}")
    print("Plantillas ARM válidas" if not problems else f"{len(problems)} error(es) en ARM")
    sys.exit(1 if problems else 0)

"""Genera docs/diagrama_arquitectura.png (requiere matplotlib: pip install matplotlib)."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).with_name("diagrama_arquitectura.png")

INK = "#1f2933"
MUTED = "#52606d"
COLORS = {
    "git": ("#e4e7eb", "#616e7c"),
    "ci": ("#dbeafe", "#1d4ed8"),
    "cd": ("#dcfce7", "#15803d"),
    "gate": ("#fef3c7", "#b45309"),
    "data": ("#ffedd5", "#c2410c"),
    "app": ("#ede9fe", "#6d28d9"),
}

fig, ax = plt.subplots(figsize=(16, 9))
ax.set_xlim(0, 100)
ax.set_ylim(0, 60)
ax.axis("off")


def box(x, y, w, h, title, lines=(), kind="git", title_size=11, fill=None):
    face, edge = COLORS[kind]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2,rounding_size=0.8",
                                fc=fill or face, ec=edge, lw=1.6))
    ax.text(x + w / 2, y + h - 1.3, title, ha="center", va="top", fontsize=title_size,
            fontweight="bold", color=INK)
    for i, line in enumerate(lines):
        ax.text(x + w / 2, y + h - 3.6 - i * 2.0, line, ha="center", va="top", fontsize=8.5, color=MUTED)


def arrow(p1, p2, label=None, color=INK, style="-|>", ls="-", rad=0.0, label_xy=None):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=16, color=color, lw=1.6,
                                 linestyle=ls, connectionstyle=f"arc3,rad={rad}"))
    if label:
        lx, ly = label_xy or ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2 + 1.0)
        ax.text(lx, ly, label, ha="center", va="bottom", fontsize=8.5, color=color,
                bbox=dict(fc="white", ec="none", pad=1.0))


ax.text(50, 59.5, "Arquitectura DataOps · Cálculo de salario total (100 % local)", ha="center", va="top",
        fontsize=16, fontweight="bold", color=INK)

# ── Control de versiones ───────────────────────────────────────────────
box(1, 41, 13, 11, "Desarrollador", ["VS Code + Git", "Conventional Commits"], "git")
box(18, 41, 14, 11, "GitHub", ["JuniorRF19/", "dataops-comisiones", "ramas main · develop"], "git")
arrow((14.4, 46.5), (17.6, 46.5), "git push")

# ── Jenkins ────────────────────────────────────────────────────────────
ax.add_patch(FancyBboxPatch((36, 30), 63, 25, boxstyle="round,pad=0.2,rounding_size=1",
                            fc="#f8fafc", ec="#9aa5b1", lw=1.4, ls="--"))
ax.text(37, 54.3, "Jenkins 2.580.1 LTS (Docker · JCasC) · Jenkinsfile", ha="left", va="top",
        fontsize=11, fontweight="bold", color=INK)
arrow((32.4, 46.5), (35.6, 46.5), "pollSCM\n2 min", label_xy=(34, 48))

box(38, 37, 17, 14, "CI", ["1. Checkout", "2. Lint (ruff)", "3. Validar plantillas ARM",
                           "4. pytest (17 tests)", "5. docker build imagen"], "ci")
cd = [("DEV", "gate no estricto", "cd", 59), ("QA", "gate estricto +\nsmoke test", "cd", 69),
      ("Aprobación\nautomática", "QA OK y\nrama main", "gate", 79), ("PRD", "smoke test", "cd", 89)]
for name, desc, kind, x in cd:
    box(x, 38, 8.5, 11, name, [], kind, title_size=10)
    ax.text(x + 4.25, 41.2, desc, ha="center", va="center", fontsize=7.8, color=MUTED)
arrow((55.4, 44), (58.6, 44))
for x in (67.5, 77.5, 87.5):
    arrow((x + 0.2, 43.5), (x + 1.3, 43.5))
ax.text(89, 34.8, "Si QA falla → PRD no se despliega", ha="center", fontsize=8.5, color=COLORS["gate"][1],
        style="italic")

# ── Ejecución del pipeline de datos ────────────────────────────────────
box(1, 16, 19, 10, "PostgreSQL (clase DMC)", ["dmc.rrhh.empleado", "48 empleados"], "data")
box(1, 3, 19, 10, "Blob Storage (Azurite)", ["raw-<env>/comisiones/", "ComisionEmpleados_V1_AAAAMM.csv"], "data")
box(32, 5, 30, 19, "Contenedor dataops-comisiones:<build>", [
    "app/pipeline.py  (python -m app.pipeline --env <env>)",
    "1. Extract SQL + Extract Blob",
    "2. INNER JOIN por empleado_id",
    "3. salario_total = mnt_salario + comision",
    "4. Quality gate (nulos, duplicados, negativos, fórmula)",
    "5. Load Parquet + Excel",
], "app")
box(74, 5, 25, 19, "Data Lake (Azurite)", ["lake-dev · lake-qa · lake-prd",
                                           "gold/comisiones/periodo=AAAAMM/",
                                           "comisiones_AAAAMM.parquet",
                                           "comisiones_AAAAMM.xlsx", "", "202610 → 33 filas consolidadas"],
    "data")

arrow((20.4, 21), (31.6, 17), "psycopg2", label_xy=(24.5, 21.2))
arrow((20.4, 8), (31.6, 11), "azure-storage-blob", label_xy=(27, 6.2))
arrow((62.4, 14.5), (73.6, 14.5), "Parquet / Excel")
arrow((73, 37.6), (52, 24.4), "docker run --env dev | qa | prd", color=COLORS["cd"][1], ls="--", rad=0.15,
      label_xy=(66, 30.5))

# leyenda
for i, (kind, label) in enumerate([("git", "Versionamiento"), ("ci", "Integración continua"),
                                   ("cd", "Despliegue continuo"), ("gate", "Aprobación"),
                                   ("app", "Procesamiento"), ("data", "Datos")]):
    face, edge = COLORS[kind]
    ax.add_patch(FancyBboxPatch((1 + i * 13, 26.9), 1.6, 1.3, boxstyle="round,pad=0.1", fc=face, ec=edge))
    ax.text(3.6 + i * 13, 27.55, label, va="center", fontsize=8.5, color=MUTED)

fig.savefig(OUT, dpi=170, bbox_inches="tight", facecolor="white")
print(f"Generado {OUT}")

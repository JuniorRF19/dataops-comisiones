# DataOps · Cálculo de salario total de empleados

Pipeline DataOps que calcula **`salario_total = salario + comisión`** de cada empleado. Combina:

- la tabla **`dmc.rrhh.empleado`** de PostgreSQL;
- el archivo **`ComisionEmpleados_V1_<AAAAMM>.csv`**, alojado en Blob Storage.

El resultado es una tabla consolidada en **Parquet** (más una copia en Excel) dentro del **Data Lake**. El flujo se despliega con **CI/CD en Jenkins** a los ambientes **DEV → QA → PRD**, con pruebas y aprobación automatizada.

> El enunciado permite "Azure Data Factory **(o Python)**", "Azure DevOps **/ GitHub**" y "Azure DevOps **/ Jenkins**". Este proyecto usa **Python + GitHub + Jenkins** y corre **100 % en local**, sin necesidad de una suscripción de Azure:
> - El Blob Storage y el Data Lake se emulan con **Azurite**, el emulador oficial de Microsoft. Se usa el mismo SDK `azure-storage-blob`, así que para apuntar a Azure real basta con cambiar `AZURE_STORAGE_CONNECTION_STRING`.
> - Las **plantillas ARM** de la infraestructura en Azure (ADLS Gen2 + Data Factory por ambiente) están versionadas en `infra/arm/` y se **validan en la CI**.

---

## 1. Arquitectura

```
                   ┌──────────────────────── Jenkins (Docker) ────────────────────────┐
  git push ──►     │ CI: checkout → lint (ruff) → validar ARM → pytest → build imagen │
  GitHub (main)    │ CD: DEV ──► QA (quality gate estricto) ──► aprobación auto ──► PRD│
  (poll 2 min)     └─────────────────────────────┬────────────────────────────────────┘
                                                 │ docker run (imagen dataops-comisiones:<build>)
                                                 ▼
   PostgreSQL dmc.rrhh.empleado ──┐      ┌──────────────────────────┐
                                  ├─────►│ app/pipeline.py          │──► lake-<env>/gold/comisiones/
   Azurite raw-<env>/comisiones/  ┘      │ extract → JOIN → quality │      periodo=AAAAMM/comisiones_AAAAMM.parquet
     ComisionEmpleados_V1_AAAAMM.csv     └──────────────────────────┘      (+ .xlsx)
```

| Concepto de Azure (Sesión 3) | Equivalente local |
|---|---|
| Pipeline de Azure Data Factory | `app/pipeline.py` (Python + pandas) |
| Linked service PostgreSQL | `psycopg2` + credencial `pg-dmc` en Jenkins |
| Blob Storage / ADLS Gen2 (`raw`, `lake`) | Azurite: contenedores `raw-<env>` y `lake-<env>` |
| Azure DevOps Pipelines + Environments | `Jenkinsfile` con etapas `CD · DEV/QA/PRD` |
| Variable groups por ambiente | `config/dev.yaml`, `config/qa.yaml`, `config/prd.yaml` |
| Plantillas ARM | `infra/arm/azuredeploy.json` + `parameters.<env>.json` |

## 2. Contenido del repositorio

```
app/
  pipeline.py      Orquestación: extract (SQL + Blob), transform, quality gate, load (Parquet/Excel)
  transform.py     Lectura del CSV y JOIN por empleado_id + cálculo de salario_total (lógica pura)
  quality.py       Reglas de calidad: filas > 0, sin nulos, ids únicos, comisión >= 0, fórmula correcta
  requirements.txt
config/            Configuración por ambiente (contenedores, rutas, periodo, modo estricto)
data/              CSV de comisiones (202610 real; 209912 con errores para la prueba negativa)
scripts/
  seed_blob.py     Crea los contenedores del ambiente y sube el CSV a raw-<env>
  verify_lake.py   Smoke test post-despliegue: lee el Parquet del lake y lo valida
  validate_arm.py  Validación estática de las plantillas ARM (CI)
tests/             Unit tests con pytest (17 casos)
infra/arm/         Plantilla ARM (ADLS Gen2 + contenedores + Data Factory) y parámetros dev/qa/prd
jenkins/           Imagen de Jenkins con Docker CLI + JCasC (admin, credencial y job automáticos)
Dockerfile         Multi-stage: base → test (CI) → runtime (CD)
docker-compose.yml Azurite + Jenkins (+ servicio "app" para ejecución manual)
Jenkinsfile        Pipeline CI/CD
docs/              Informe final
evidencias/        Logs y capturas de las ejecuciones
```

## 3. Reglas de negocio

1. **Extract SQL**: `SELECT empleado_id, nom_empleado, ape_empleado, cod_cargo, cod_departamento, mnt_salario FROM rrhh.empleado`.
2. **Extract Blob**: `raw-<env>/comisiones/ComisionEmpleados_V1_<periodo>.csv`.
   - Separador `;`.
   - Se acepta codificación UTF-8 o Latin-1.
   - Las columnas se normalizan (`Comisión` → `comision`).
3. **Transform**:
   - **INNER JOIN** por `empleado_id` y `salario_total = mnt_salario + comision`, redondeado a 2 decimales.
   - Se agregan las columnas `periodo` y `fecha_proceso`.
   - Se registran en el log los ids del CSV que no existen en la BD y los empleados sin comisión.
4. **Quality gate** (`app/quality.py`): en **DEV** solo informa. En **QA y PRD** detiene el despliegue (exit code 2).
5. **Load**: `lake-<env>/gold/comisiones/periodo=<periodo>/comisiones_<periodo>.parquet` (+ `.xlsx`).

## 4. Requisitos

- Docker Desktop (con Docker Compose v2).
- Git y una cuenta de GitHub.
- Opcional, para correr fuera de Docker: Python 3.11 o superior.
- Acceso a internet hacia `mgg.vps.webdock.cloud:5432` (PostgreSQL de clase).

## 5. Pasos para desplegar

### 5.1 Clonar y configurar secretos
```bash
git clone https://github.com/<usuario>/dataops-comisiones.git
cd dataops-comisiones
cp .env.example .env        # completar PG_USER, PG_PASSWORD, JENKINS_ADMIN_PASSWORD, GITHUB_REPO_URL
```
`.env` está en `.gitignore`: las credenciales nunca se versionan. En Jenkins se cargan como la credencial `pg-dmc`.

### 5.2 Levantar la plataforma (Azurite + Jenkins)
```bash
docker compose up -d --build
```
- Jenkins: http://localhost:8080. Se entra con `JENKINS_ADMIN_ID` / `JENKINS_ADMIN_PASSWORD` del `.env`.
- Gracias a JCasC no hay asistente inicial: el usuario admin, la credencial `pg-dmc` y el job `dataops-comisiones` se crean automáticamente.

### 5.3 Ejecutar el CI/CD
1. En Jenkins abre el job **dataops-comisiones** y pulsa **Build with Parameters** con `PERIODO=202610`. Esta primera ejecución también registra el trigger `pollSCM`.
2. Desde ahí, cada `git push` a `main` dispara el pipeline en 2 minutos como máximo:
   ```bash
   git commit -am "feat: cambio X" && git push origin main
   ```
3. Las etapas del pipeline son: `CI · Checkout` → `CI · Lint, ARM y Unit tests` → `CI · Build imagen` → `CD · DEV` → `CD · QA` → `Aprobación automática` → `CD · PRD`.
4. Los artefactos del build quedan disponibles en Jenkins:
   - `reports/junit.xml` (resultados de los tests);
   - `logs/deploy_<env>.log`;
   - `artifacts/<env>/comisiones_<periodo>.parquet|xlsx`.

> **Aprobación automatizada:** PRD solo se despliega cuando QA terminó sin errores (quality gate estricto y smoke test sobre el Parquet) y además la rama es `main`. Si QA falla, PRD no se ejecuta.

### 5.4 Ejecución manual (sin Jenkins)
```bash
docker compose up -d azurite
docker compose run --rm app sh -c "python scripts/seed_blob.py --env dev && python -m app.pipeline --env dev && python scripts/verify_lake.py --env dev"
```
O con Python local:
```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # Linux/Mac: .venv/bin/pip
python scripts/seed_blob.py --env dev
python -m app.pipeline --env dev --local-out out/dev
python scripts/verify_lake.py --env dev
pytest -v
```

### 5.5 Prueba negativa del quality gate
Lanza el build con `PERIODO=209912`. Ese CSV trae una comisión negativa, una nula y un id duplicado.

- **DEV** registra los errores y continúa.
- **QA** falla con `QUALITY GATE FALLIDO`.
- **PRD** no se despliega.

### 5.6 (Opcional) Desplegar la infraestructura real en Azure
```bash
az group create -n az-taller-prd-de-rg-dataops -l eastus
az deployment group create -g az-taller-prd-de-rg-dataops \
  --template-file infra/arm/azuredeploy.json --parameters @infra/arm/parameters.prd.json
```
Después, ejecuta el pipeline con `AZURE_STORAGE_CONNECTION_STRING` apuntando a la cuenta creada.

## 6. Flujo de trabajo Git

- `main`: código desplegable. Cada push dispara el CI/CD completo hasta PRD.
- `develop` y `feature/*`: desarrollo. Se integran a `main` mediante Pull Request.
- Los commits siguen *Conventional Commits* (`feat:`, `fix:`, `test:`, `ci:`, `docs:`, `infra:`).

## 7. Datos observados (periodo 202610)

| Métrica | Valor |
|---|---|
| Empleados en `rrhh.empleado` | 48 |
| Filas en el CSV | 34 |
| Filas consolidadas (INNER JOIN) | 33 |
| ID del CSV sin empleado en BD | 4 |
| Suma de `salario_total` | 436 905.20 |

Los nombres del CSV no coinciden con los de la BD (por ejemplo, el id 1 es "Juan Pérez" en el CSV y "Ana Pérez" en la BD). Por eso el cruce se hace solo por `empleado_id`, como pide el enunciado, y los nombres se toman de la BD.

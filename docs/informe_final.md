# Informe final · Proyecto DataOps: cálculo de salario total

**Curso:** DE – DataOps (DMC Institute) · **Autor:** Junior Rojas · **Fecha:** octubre 2026

## 1. Resumen del proyecto

Se implementó un flujo automatizado que calcula el **salario total** de cada empleado (`salario_total = mnt_salario + comisión`). El flujo:

1. Extrae la tabla `dmc.rrhh.empleado` desde PostgreSQL.
2. Procesa el CSV `ComisionEmpleados_V1_<AAAAMM>.csv`, alojado en Blob Storage.
3. Une ambas fuentes por `empleado_id`.
4. Publica la tabla consolidada en **Parquet** (más una copia en Excel) en el **Data Lake**, particionada por periodo.

El flujo se versiona en **Git/GitHub** y se despliega con **Jenkins** a tres ambientes, **DEV → QA → PRD**, con pruebas automáticas y una **aprobación automatizada** basada en quality gates.

### Decisiones de diseño

| Requisito | Implementación | Justificación |
|---|---|---|
| Pipeline ADF (o Python) | `app/pipeline.py` (pandas + pyarrow) | El enunciado permite Python. Es testeable con pytest y portable. |
| Blob Storage / Data Lake | Azurite (emulador oficial de Azure Storage) | Se usa el mismo SDK `azure-storage-blob`, sin costo de suscripción. El código no cambia al pasar a Azure real. |
| Repositorio Git | GitHub, con ramas `main` / `develop` y Conventional Commits | El enunciado permite "Azure DevOps / GitHub". |
| CI/CD | Jenkins en Docker, configurado como código (JCasC) | El enunciado permite "Azure DevOps / Jenkins". Es reproducible con `docker compose up`. |
| Plantillas ARM | `infra/arm` (ADLS Gen2 + contenedores + Data Factory), validadas en la CI | Dejan la infraestructura de Azure versionada y lista para desplegar por ambiente. |
| Aprobaciones automatizadas | Quality gate estricto en QA + smoke test del Parquet + rama `main` | PRD solo recibe código y datos que pasaron QA. |
| Secretos | `.env` (ignorado por Git) y credencial `pg-dmc` en Jenkins | Ninguna credencial queda en el repositorio. |

## 2. Arquitectura

```
GitHub (main) ──poll──► Jenkins
   CI: checkout → ruff → validar ARM → pytest (17) → docker build
   CD: DEV (gate no estricto) → QA (gate estricto + smoke test) → aprobación automática → PRD
        │
        └─► contenedor dataops-comisiones:<build>
              PostgreSQL rrhh.empleado ─┐
              raw-<env>/…/CSV ──────────┴─► JOIN empleado_id ─► quality ─► lake-<env>/gold/comisiones/periodo=AAAAMM/*.parquet
```

## 3. Resultados del procesamiento (periodo 202610)

| Métrica | Valor |
|---|---|
| Filas leídas de `rrhh.empleado` | 48 |
| Filas leídas del CSV | 34 |
| Filas consolidadas (INNER JOIN) | **33** |
| ID del CSV descartado (no existe en BD) | 4 |
| Empleados de BD sin comisión en el periodo | 6, 7, 8, 38–48, 50 |
| Suma de `salario_total` | **436 905.20** |
| Salida | `lake-<env>/gold/comisiones/periodo=202610/comisiones_202610.parquet` (+ `.xlsx`) |

**Observación de calidad:** los nombres del CSV no coinciden con los de la BD (por ejemplo, el id 1 es "Juan Pérez" en el CSV y "Ana Pérez" en la BD). Como pide el enunciado, el cruce se hace solo por `empleado_id`. Se recomienda revisar este punto con el área de RR. HH.

## 4. Registro de pruebas

| # | Prueba | Tipo | Resultado esperado | Resultado obtenido | Evidencia |
|---|---|---|---|---|---|
| 1 | Lint del código (`ruff`) | CI | Sin errores | ✅ All checks passed | log de la etapa `CI · Lint, ARM y Unit tests` |
| 2 | Validación de plantillas ARM (dev/qa/prd) | CI | Parámetros válidos y nombres de Storage correctos | ✅ Plantillas ARM válidas | idem |
| 3 | Unit tests (`pytest`, 17 casos): normalización de columnas, encodings UTF-8/Latin-1, columnas faltantes, JOIN, fórmula, tipos Decimal, reglas de calidad | CI | 17/17 OK | ✅ 17 passed | `reports/junit.xml` y Test Result en Jenkins |
| 4 | Ejecución en DEV, periodo 202610 | CD | Parquet publicado en `lake-dev` | ✅ 33 filas | `evidencias/ejecucion_local_202610.log`, `logs/deploy_dev.log` |
| 5 | Ejecución en QA + smoke test | CD | Quality gate OK y Parquet legible | ✅ Verificación QA OK | `logs/deploy_qa.log` |
| 6 | Aprobación automática + ejecución en PRD | CD | PRD desplegado | ✅ Verificación PRD OK | `logs/deploy_prd.log`, `artifacts/prd/*.parquet` |
| 7 | Prueba negativa: CSV 209912 con comisión negativa, nula e id duplicado | Calidad | DEV avisa; QA falla; PRD no se ejecuta | ✅ DEV exit 0 con 4 errores reportados; QA exit 2 `QUALITY GATE FALLIDO` | `evidencias/prueba_negativa_quality_gate.log` |
| 8 | Disparo automático por `git push` (pollSCM) | CI/CD | Nuevo build sin intervención manual | ver captura | `evidencias/` |

## 5. Evidencias

La carpeta `evidencias/` contiene:

- `ejecucion_local_202610.log`: ejecución del pipeline en DEV, QA y PRD, más la verificación del Parquet de PRD.
- `prueba_negativa_quality_gate.log`: comportamiento del quality gate con datos inválidos.
- `jenkins_build_3_ok_202610.log`: consola de Jenkins con CI + DEV → QA → PRD en verde.
- `jenkins_build_4_fallo_qa_209912.log`: consola de Jenkins donde QA bloquea datos inválidos y PRD queda omitido.
- Capturas de pantalla, que se agregan manualmente:
  - Stage View del job con todas las etapas en verde;
  - Test Result (17 tests);
  - artefactos del build;
  - build fallido en QA con `PERIODO=209912`;
  - commits en GitHub;
  - build disparado por el push.

## 6. Conclusiones

- El flujo cumple el requerimiento funcional: extrae de PostgreSQL y de Blob, une por `empleado_id`, calcula `salario_total` y publica Parquet en el Data Lake.
- La CI garantiza calidad de código (lint), de la infraestructura (ARM) y de la lógica (unit tests) antes de construir la imagen.
- La CD promueve la misma imagen inmutable por DEV → QA → PRD. El quality gate de QA actúa como aprobación automatizada e impide que datos inválidos lleguen a producción.
- La solución corre 100 % en local. Para pasar a Azure basta con desplegar `infra/arm` y cambiar la cadena de conexión del Storage.

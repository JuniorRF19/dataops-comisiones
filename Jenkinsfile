// CI/CD DataOps · Cálculo de salario total (salario + comisión)
//   CI : checkout → lint + validación ARM + unit tests → build imagen
//   CD : DEV → QA (quality gate estricto) → aprobación automática → PRD
pipeline {
    agent any

    triggers {
        pollSCM('H/2 * * * *')      // Jenkins local: el webhook de GitHub no llega a localhost
    }

    parameters {
        string(name: 'PERIODO', defaultValue: '202610', description: 'Periodo AAAAMM del CSV de comisiones')
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
        timestamps()
    }

    environment {
        IMAGE          = 'dataops-comisiones'
        TAG            = "${env.BUILD_NUMBER}"
        DOCKER_NETWORK = 'dataops-net'
        PG_HOST        = 'mgg.vps.webdock.cloud'
        PG_PORT        = '5432'
        PG_DB          = 'dmc'
        // Cadena pública del emulador Azurite (no es un secreto)
        AZURE_STORAGE_CONNECTION_STRING = 'DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://azurite:10000/devstoreaccount1;'
    }

    stages {
        stage('CI · Checkout') {
            steps {
                checkout scm
                sh 'git log -1 --pretty="Commit %h · %an · %s"'
                sh 'docker --version'
            }
        }

        stage('CI · Lint, ARM y Unit tests') {
            steps {
                sh 'docker build --target test -t ${IMAGE}:test-${TAG} .'
                sh '''#!/bin/bash
                    docker run --name test-${TAG} ${IMAGE}:test-${TAG}
                    rc=$?
                    mkdir -p reports
                    docker cp test-${TAG}:/opt/dataops/reports/. reports/ || true
                    docker rm -f test-${TAG} > /dev/null
                    exit $rc
                '''
            }
            post {
                always { junit allowEmptyResults: true, testResults: 'reports/junit.xml' }
            }
        }

        stage('CI · Build imagen') {
            steps {
                sh 'docker build --target runtime -t ${IMAGE}:${TAG} -t ${IMAGE}:latest .'
            }
        }

        stage('CD · DEV') {
            steps { script { deployTo('dev') } }
        }

        stage('CD · QA') {
            steps {
                script {
                    deployTo('qa')
                    env.QA_APPROVED = 'true'
                }
            }
        }

        stage('Aprobación automática') {
            steps {
                script {
                    def branch = env.GIT_BRANCH ?: ''
                    if (env.QA_APPROVED != 'true') {
                        error('QA no aprobó el despliegue')
                    }
                    env.PRD_APPROVED = branch.endsWith('main') ? 'true' : 'false'
                    echo "Quality gate QA: OK · rama ${branch} · aprobado para PRD: ${env.PRD_APPROVED}"
                }
            }
        }

        stage('CD · PRD') {
            when { expression { env.PRD_APPROVED == 'true' } }
            steps { script { deployTo('prd') } }
        }
    }

    post {
        always {
            archiveArtifacts allowEmptyArchive: true, artifacts: 'logs/**, artifacts/**, reports/**'
            sh 'docker image rm ${IMAGE}:test-${TAG} > /dev/null 2>&1 || true'
        }
        success { echo "Pipeline OK: periodo ${params.PERIODO} desplegado en DEV → QA → PRD" }
        failure { echo 'Pipeline FALLIDO: revisar logs/ y el reporte de tests' }
    }
}

// Despliega y verifica el flujo en un ambiente:
//   1) prepara Storage (contenedores + CSV en raw-<env>)
//   2) ejecuta el pipeline (extract → join → quality → Parquet en lake-<env>)
//   3) smoke test: lee el Parquet publicado y valida su contenido
def deployTo(String envName) {
    withCredentials([usernamePassword(credentialsId: 'pg-dmc', usernameVariable: 'PG_USER', passwordVariable: 'PG_PASSWORD')]) {
        withEnv(["DEPLOY_ENV=${envName}"]) {
            sh '''#!/bin/bash
                set -euo pipefail
                mkdir -p logs artifacts/${DEPLOY_ENV}
                name=deploy-${DEPLOY_ENV}-${TAG}
                docker run --name ${name} --network ${DOCKER_NETWORK} \
                    -e PG_HOST -e PG_PORT -e PG_DB -e PG_USER -e PG_PASSWORD -e AZURE_STORAGE_CONNECTION_STRING \
                    ${IMAGE}:${TAG} sh -c "
                        python scripts/seed_blob.py   --env ${DEPLOY_ENV} --periodo ${PERIODO} &&
                        python -m app.pipeline        --env ${DEPLOY_ENV} --periodo ${PERIODO} --local-out out &&
                        python scripts/verify_lake.py --env ${DEPLOY_ENV} --periodo ${PERIODO}" \
                    2>&1 | tee logs/deploy_${DEPLOY_ENV}.log || rc=$?
                docker cp ${name}:/opt/dataops/out/. artifacts/${DEPLOY_ENV}/ 2>/dev/null || true
                docker rm -f ${name} > /dev/null
                exit ${rc:-0}
            '''
        }
    }
}

# Jenkins local con Docker CLI (usa el Docker del host vía docker.sock)
# y configuración como código (JCasC): usuario admin, credencial de BD y job.
FROM docker:29-cli AS dockercli

FROM jenkins/jenkins:2.580.1-lts-jdk21
USER root
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=dockercli /usr/local/libexec/docker/cli-plugins/docker-buildx /usr/local/libexec/docker/cli-plugins/docker-buildx

RUN jenkins-plugin-cli --plugins \
    configuration-as-code \
    job-dsl \
    git \
    workflow-aggregator \
    pipeline-stage-view \
    credentials-binding \
    junit \
    timestamper \
    ws-cleanup

COPY casc.yaml /usr/share/jenkins/ref/casc.yaml

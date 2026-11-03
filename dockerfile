FROM artifactory.robinsystems.com/docker/mdcap/helm/mdcap-worker:4.3.1-381

USER root
RUN /opt/app-root/bin/python -m ensurepip --upgrade \
 && /opt/app-root/bin/python -m pip install rpdb

FROM public.ecr.aws/lts/ubuntu:18.04_stable

RUN apt-get -y update && \
    apt-get -y install --no-install-recommends python3-minimal python3-pip && \
    pip3 install --no-cache-dir requests boto3 && \
    apt-get remove -y --purge python3-pip && \
    apt-get autoremove -y && \
    apt-get -y clean

COPY bsimport.py /usr/local/bin/bsimport

ENTRYPOINT ["bsimport"]

FROM public.ecr.aws/lts/ubuntu:18.04_stable

RUN apt-get update && \
    apt-get install --no-install-recommends python3-minimal python3-pip libvips42 unzip curl -y && \
    pip3 install --no-cache-dir setuptools && \
    pip3 install --no-cache-dir pyvips requests && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm aws -rf && \
    apt-get remove --purge unzip curl python3-pip -y && \
    apt-get autoremove -y && \
    apt-get clean

COPY deepzoom.py /usr/local/bin/deepzoom

ENTRYPOINT ["deepzoom"]

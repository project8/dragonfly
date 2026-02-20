ARG img_user=ghcr.io/driplineorg
ARG img_repo=dripline-python
#ARG img_tag=develop-dev
ARG img_tag=v5.1.5

FROM ${img_user}/${img_repo}:${img_tag}

ARG enable_daq
ENV ENABLE_DAQ=${enable_daq}

COPY . /usr/local/src_dragonfly

WORKDIR /usr/local/src_dragonfly
RUN if [ "$ENABLE_DAQ" = "true" ]; then \
    pip install \
    numpy==1.26.4 \
    scipy==1.14.1 \
    backports.ssl_match_hostname==3.7.0.1 \
    katcp==0.9.3 \
    ; fi
RUN pip install docker pymodbus
RUN pip install .

WORKDIR /
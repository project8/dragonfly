ARG img_user=ghcr.io/driplineorg
ARG img_repo=dripline-python
#ARG img_tag=develop-dev
ARG img_tag=v5.1.5

FROM ${img_user}/${img_repo}:${img_tag}

COPY . /usr/local/src_dragonfly

WORKDIR /usr/local/src_dragonfly
RUN pip install docker pymodbus
RUN pip install .

WORKDIR /
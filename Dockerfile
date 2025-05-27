ARG img_user=ghcr.io/driplineorg
ARG img_repo=dripline-python
#ARG img_tag=develop-dev
ARG img_tag=v5.0.0-dev
#ARG img_tag=fix-send

FROM ${img_user}/${img_repo}:${img_tag}

COPY . /usr/local/src_dragonfly

WORKDIR /usr/local/src_dragonfly
RUN pip install pymodbus
RUN pip install .

WORKDIR /

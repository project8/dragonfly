ARG img_user=ghcr.io/driplineorg
ARG img_repo=dripline-python
#ARG img_tag=develop-dev
ARG img_tag=receiver-test

FROM ${img_user}/${img_repo}:${img_tag}

COPY . /usr/local/src_dragonfly

WORKDIR /usr/local/src_dragonfly
RUN pip install docker
RUN pip install .

WORKDIR /

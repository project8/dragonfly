ARG img_user=ghcr.io/driplineorg
ARG img_repo=dripline-python
ARG img_tag=develop

FROM ${img_user}/${img_repo}:${img_tag}

RUN pip install pymodbus slack_sdk
COPY . /usr/local/src/dragonfly

WORKDIR /usr/local/src/dragonfly
RUN pip install .

WORKDIR /

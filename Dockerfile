ARG img_user=ghcr.io/driplineorg
ARG img_repo=dripline-python
ARG img_tag=develop-dev

ARG UID=5001
ARG GID=5001

FROM ${img_user}/${img_repo}:${img_tag}

COPY . /usr/local/src_dragonfly

WORKDIR /usr/local/src_dragonfly
RUN pip install .
RUN pip install Flask
RUN pip install ./py_elog

WORKDIR /


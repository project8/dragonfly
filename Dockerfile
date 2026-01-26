ARG img_user=ghcr.io/driplineorg
ARG img_repo=dripline-python
ARG img_tag=v5.1.2

ARG UID=5001
ARG GID=5001

FROM ${img_user}/${img_repo}:${img_tag}

COPY . /usr/local/src_dragonfly

WORKDIR /usr/local/src_dragonfly
RUN pip install docker
RUN pip install .
RUN pip install Flask
RUN git clone https://github.com/paulscherrerinstitute/py_elog.git /usr/local/py_elog
RUN pip install /usr/local/py_elog

WORKDIR /


ARG img_user=driplineorg
ARG img_repo=dripline-python
ARG img_tag=v4.7.1

FROM ${img_user}/${img_repo}:${img_tag}

COPY . /usr/local/src/dragonfly

WORKDIR /usr/local/src/dragonfly
RUN pip install .

WORKDIR /

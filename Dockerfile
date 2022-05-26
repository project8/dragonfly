from driplineorg/dripline-python:v4.5.8

COPY . /usr/local/src/dragonfly

WORKDIR /usr/local/src/dragonfly
RUN pip install .

WORKDIR /

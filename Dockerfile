ARG img_user=ghcr.io
ARG img_repo=driplineorg/dripline-python
ARG img_tag=v5.1.0-test

FROM ${img_user}/${img_repo}:${img_tag} AS base

FROM base AS deps
# installing dependencies
RUN pip install numpy==1.26.4 &&\
    pip install scipy==1.14.1 &&\
    pip install backports.ssl_match_hostname==3.7.0.1 &&\
    pip install katcp==0.9.3 &&\
    cd /usr/local &&\
    git clone https://github.com/pkolbeck/adc_tests.git &&\
    cd adc_tests &&\
    git checkout master &&\
    pip install . &&\
    cd /tmp &&\
    git clone https://github.com/pkolbeck/corr.git &&\
    cd corr &&\
    git checkout p8/r2daq_only &&\
    cp -r corr /usr/local/corr/ &&\
    rm -rf /tmp/corr/

ENV PYTHONPATH="/usr/:/usr/local/:/usr/local/corr/"

FROM deps AS build

COPY . /usr/local/src/dragonfly

WORKDIR /usr/local/src/dragonfly
RUN pip install .

WORKDIR /

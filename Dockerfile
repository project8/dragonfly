FROM project8/dripline-python

ADD . /dragonfly
RUN pip install /dragonfly[colorlog,database,slack]

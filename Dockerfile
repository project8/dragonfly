FROM project8/dripline-python

COPY . /dragonfly
RUN pip install /dragonfly[colorlog,database,slack]

RUN pip install --upgrade oauth2client
RUN pip install --upgrade google-api-python-client
RUN pip install python-dateutil
RUN pip install funcsigs

FROM python:3.9-slim

ARG GRAPH_USER=graph
ARG GRAPH_HOME=/home/graph

RUN useradd -m -d "${GRAPH_HOME}" -s /bin/bash "${GRAPH_USER}"
USER $GRAPH_USER
WORKDIR $GRAPH_HOME

ADD requirements.txt ./
RUN pip3 install -r requirements.txt

ADD *.py ./

CMD [ "python", "-u", "check_poi.py" ]

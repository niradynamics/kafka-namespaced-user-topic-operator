FROM python:3.7.4-slim
RUN pip install kopf
COPY ./src /src
RUN cd /src && pip install . && rm -r /src

FROM python:3.7.4-slim
# Install requirements early to decrease image build time.
RUN pip install kopf==0.21 pyhocon
COPY ./src /src
RUN cd /src && pip install . && rm -r /src

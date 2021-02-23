FROM python:3.8-slim

# Install requirements early to decrease image build time.
COPY requirements.txt /src/requirements.txt
RUN pip install -r /src/requirements.txt

COPY knuto /src/knuto
COPY setup.py README.md /src/
RUN cd /src && pip install .

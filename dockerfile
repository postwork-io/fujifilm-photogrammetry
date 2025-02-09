FROM python:3.10

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -y
RUN apt-get install -y exiftool
COPY processing-server-requirements.txt requirements.txt
RUN pip install -r requirements.txt
RUN git clone https://github.com/momonala/focus-stack && pip install -e ./focus-stack
RUN mkdir /uploads
COPY ./processing_server ./processing_server
CMD ["python3", "-m", "processing_server"]
FROM python:3-buster
ENV PYTHONUNBUFFERED 1
RUN mkdir /binder
WORKDIR /binder
ADD . /binder
RUN ./install-mssql-driver.sh

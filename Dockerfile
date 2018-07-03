FROM python:3
ENV PYTHONUNBUFFERED 1
RUN mkdir /binder
WORKDIR /binder
ADD . /binder

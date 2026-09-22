FROM python:3.10
ENV PYTHONUNBUFFERED 1
RUN mkdir /binder
WORKDIR /binder
ADD setup.py .
ADD README.md .
RUN pip install django==5.2.9
RUN pip install -e .[test]

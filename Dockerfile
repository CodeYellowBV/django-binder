FROM python:3.14
ENV PYTHONUNBUFFERED 1
RUN mkdir /binder
WORKDIR /binder
ADD setup.py .
ADD README.md .
RUN pip install -e .[test]

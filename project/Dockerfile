FROM python:3
ENV PYTHONUNBUFFERED 1
WORKDIR /code
COPY packages.pip /code/
RUN pip install -r packages.pip
COPY . /code/

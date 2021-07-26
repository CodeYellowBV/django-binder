FROM mcr.microsoft.com/mssql/server:2017-latest
WORKDIR /

ENV ACCEPT_EULA Y
ENV SA_PASSWORD "~Test123"

COPY docker/mssqldb/init /init
COPY docker/mssqldb/bootstrap.sql /bootstrap.sql
COPY docker/mssqldb/entrypoint.sh /entrypoint.sh

EXPOSE 1433
CMD /entrypoint.sh
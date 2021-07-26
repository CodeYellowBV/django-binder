#!/bin/sh

#start SQL Server, start the script to create the DB and import the data, start the app
nohup /init &
/opt/mssql/bin/sqlservr

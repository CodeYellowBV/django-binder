#!/usr/bin/env bash

set -euo pipefail  # Exit on error, unset variable, and fail on pipe errors

log() {
  echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] $@"
}

create_venv="python -m venv .venv"
install_pip=". .venv/bin/activate && curl https://bootstrap.pypa.io/get-pip.py | python"
install_requirements=".venv/bin/pip install django==3.2.25 -r ci-requirements.txt"
create_db="psql -h localhost -U postgres -d postgres -c 'CREATE DATABASE binder_test;'"
run_tests=".venv/bin/coverage run --include="binder/*" -m unittest discover -vt ."


setup_python() {
	log "Seting up python evironment"
	# Execute the check and creation of the virtual environment in the 'backend' container
	if ! docker-compose exec -T binder [ -d ".venv" ]; then
		log "Creating new venv in docker container"
		docker compose exec binder $create_venv
		log "Installing pip"
		docker compose exec binder $install_pip
	else
		log "Already found existing venv"
	fi
	log "Installing ci-requirements.txt and django"
	docker compose exec binder $install_requirements
}

setup_database() {
	log "Seting up db evironment"
	# Check if the database exists using the `docker exec` command
	if ! docker compose exec db psql -U postgres -lqt | cut -d \| -f 1 | grep -qw binder_test; then
	  log "No database found, creating new one"
	  docker compose exec -T db bash -c "$create_db"
	else
	  log "Already existing DB, not creating new one"
	fi
}

run_tests() {
	log "Running tests"
	args=("$@")
	docker compose exec -T binder bash -c "$run_tests ${args[@]}"
}


setup_python
setup_database
run_tests "$@"

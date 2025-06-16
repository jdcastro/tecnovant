PROJECT_DIR := $(shell pwd)
VENV_NAME := project/venv
VENV_ACTIVATE := $(VENV_NAME)/bin/activate
PORT := 5090
PYTHON := /usr/bin/python
COMPOSE_FILE_DEV := docker-compose.yml

.PHONY: help install installdev run start save test format lint check stop clean rmcache documents css docker-build docker-run docker-stop docker-logs docker-logs-all docker-clean docker-prune

help:
@echo "Available targets:"
@echo "  run          - Runs the Flask development server"
@echo "  lint         - Runs linters (flake8, black, isort) to check code quality"
@echo "  format       - Formats the code using black and isort"
@echo "  test         - Runs tests (TODO: implement test runner)"
@echo "  clean        - Cleans up build artifacts and pycache"
@echo "  docker-build - Builds the Docker image for development"
@echo "  docker-run   - Runs the development environment using Docker Compose"
@echo "  docker-stop  - Stops the development environment Docker containers"
@echo "  docker-logs  - Shows logs from Docker Compose"
@echo "  docker-clean - Removes Docker containers and volumes"

install:
$(PYTHON) -m venv $(VENV_NAME)
chmod +x $(VENV_NAME)/bin/activate
source $(VENV_ACTIVATE); pip install -r project/requirements.txt

installdev:
$(PYTHON) -m venv $(VENV_NAME)
chmod +x $(VENV_NAME)/bin/activate
source $(VENV_ACTIVATE); pip install -r project/requirements-devel.txt
cd tailwind && npm install

run:
@echo "Starting Flask development server..."
source $(VENV_ACTIVATE); cd project && nohup flask --app run run --debug --host=0.0.0.0 --port=$(PORT) > ../log.txt 2>&1 &

start: install run

save:
source $(VENV_ACTIVATE); pip freeze > project/requirements.txt
git add .
git commit -m "fix and updates"

test:
. $(VENV_ACTIVATE); pytest

format:
@echo "Formatting code..."
@echo "Running black..."
source $(VENV_ACTIVATE); black project/app project/cli project/run.py
@echo "Running isort..."
source $(VENV_ACTIVATE); isort project/app project/cli project/run.py
@echo "Formatting complete."

lint:
@echo "Running linters..."
@echo "Running flake8..."
source $(VENV_ACTIVATE); flake8 project/app project/cli project/run.py
@echo "Checking black formatting..."
source $(VENV_ACTIVATE); black --check project/app project/cli project/run.py
@echo "Checking isort import order..."
source $(VENV_ACTIVATE); isort --check-only project/app project/cli project/run.py
@echo "Linting complete."

check: format lint test

stop:
@echo "Killing processes on port $(PORT)..."
@pids=$$(lsof -t -i:$(PORT)); \
if [ -n "$$pids" ]; then \
echo "Killing: $$pids"; \
kill -9 $$pids; \
else \
echo "No processes found on port $(PORT)"; \
fi

clean: stop
@echo "Cleaning up..."
rm -rf $(VENV_NAME)
rm -f log.txt app_errors.log
find $(PROJECT_DIR) -type d -name '__pycache__' -exec rm -rf {} +
find $(PROJECT_DIR) -name '*.pyc' -delete
rm -rf .pytest_cache
rm -rf .coverage
rm -rf htmlcov
rm -rf build dist *.egg-info
@echo "Cleanup complete."

rmcache:
rm -f log.txt app_errors.log
find $(PROJECT_DIR) -type d -name '__pycache__' -exec rm -rf {} +

documents:
source $(VENV_ACTIVATE); pdoc --docformat google -o docs project/app

css:
cd tailwind && npm run build

docker-build:
@echo "Building Docker images for development..."
docker-compose -f $(COMPOSE_FILE_DEV) build

docker-run:
@echo "Starting development environment with Docker Compose..."
docker-compose -f $(COMPOSE_FILE_DEV) up -d
@echo "Development environment started. Access at http://localhost:5501"

docker-stop:
@echo "Stopping Docker Compose services..."
docker-compose -f $(COMPOSE_FILE_DEV) stop

docker-logs:
@echo "Showing logs for 'app' service (Ctrl+C to stop)..."
docker-compose -f $(COMPOSE_FILE_DEV) logs -f web

docker-logs-all:
@echo "Showing logs for all services (Ctrl+C to stop)..."
docker-compose -f $(COMPOSE_FILE_DEV) logs -f

docker-clean:
@echo "Cleaning up Docker environment (containers, networks, volumes)..."
docker-compose -f $(COMPOSE_FILE_DEV) down -v --remove-orphans

docker-prune:
@echo "Cleaning up All Docker file in system"
docker builder prune --all --force && docker system prune --all --volumes --force

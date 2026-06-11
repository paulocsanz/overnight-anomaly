.PHONY: help dev build test lint clean docker-build docker-up docker-down

help:
	@echo "Trading SaaS - Available Commands"
	@echo "=================================="
	@echo "make dev          - Start development environment"
	@echo "make build        - Build backend and frontend"
	@echo "make test         - Run all tests"
	@echo "make lint         - Run linting and type checking"
	@echo "make clean        - Clean build artifacts"
	@echo "make docker-build - Build Docker image"
	@echo "make docker-up    - Start Docker Compose stack"
	@echo "make docker-down  - Stop Docker Compose stack"

dev:
	@echo "Starting development environment..."
	docker-compose up

build:
	@echo "Building backend..."
	cargo build --release
	@echo "Building frontend..."
	cd frontend && npm run build

test:
	@echo "Testing backend..."
	cargo test
	@echo "Testing frontend..."
	cd frontend && npm test

lint:
	@echo "Linting backend..."
	cargo fmt --check
	cargo clippy
	@echo "Linting frontend..."
	cd frontend && npm run lint
	cd frontend && npm run type-check

clean:
	cargo clean
	rm -rf frontend/dist
	rm -rf frontend/node_modules

docker-build:
	docker build -t trading-saas:latest .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

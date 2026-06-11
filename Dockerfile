# Multi-stage Docker build for Trading SaaS

# Stage 1: Build Rust backend
FROM rust:latest as rust-builder

WORKDIR /app

COPY Cargo.toml Cargo.lock ./
COPY src ./src
COPY migrations ./migrations

RUN cargo build --release

# Stage 2: Build React frontend
FROM node:20 as frontend-builder

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./

RUN npm run build

# Stage 3: Runtime
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y libpq5 ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=rust-builder /app/target/release/trading-saas /app/trading-saas
COPY --from=frontend-builder /app/dist /app/public

EXPOSE 8000

ENV RUST_LOG=info

CMD ["./trading-saas"]

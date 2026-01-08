# E-Commerce Price Tracking System (Dockerized)

## Overview
A Streamlit-based e-commerce price tracking system that monitors product prices and displays them in an interactive UI.

The entire application is containerized using Docker and can be started with a single command using docker-compose.

## Tech Stack
- Python
- Streamlit
- Docker
- Docker Compose
- SQLite
- Ubuntu (VM)

## Project Structure
app/
- web_app.py
- track_product.py
- users.db
- products.db
- requirements.txt

## How to Run (One Command)
```bash
docker-compose up --build


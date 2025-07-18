# Spinly API

Spinly is an electronic music discovery and collection management service. This repository contains the backend API, built with FastAPI, designed to help users explore new music based on their existing tastes and organize their favorite tracks into collections.

## Overview

The Spinly API serves as the backbone for a sophisticated music application. It leverages the extensive Discogs database to provide data and recommendations. The core philosophy is to provide a seamless bridge between a user's personal music library and the vast universe of music available, facilitating discovery through smart, context-aware suggestions.

## Core Features

*   **User Authentication**: Secure user registration and login using JWT-based authentication.
*   **Collection Management**: Create, manage, and view personal music collections. Add or remove tracks with ease.
*   **Intelligent Music Recommendations**: A sophisticated, asynchronous recommendation engine that:
    *   Finds stylistically similar releases on Discogs based on a seed track.
    *   Uses a scoring algorithm that weighs artist, label, year, and style overlap.
    *   Runs as a background job to avoid blocking API requests, allowing users to check the status later.
*   **Discogs Integration**: Deep integration with the Discogs API to fetch detailed release, artist, and track data.
*   **Asynchronous Architecture**: Built with FastAPI and `asyncio` for high performance and concurrency.
*   **Database Management**: Uses PostgreSQL with SQLAlchemy ORM for data persistence and Alembic for handling database schema migrations.
*   **Interactive API Docs**: Automatic generation of interactive API documentation via Swagger UI (`/docs`) and ReDoc (`/redoc`).

## Tech Stack

*   **Framework**: FastAPI
*   **Database**: PostgreSQL
*   **ORM**: SQLAlchemy 2.0 (with `asyncio` support)
*   **Migrations**: Alembic
*   **Data Validation**: Pydantic
*   **API Client**: httpx (for communicating with Discogs)
*   **Server**: Uvicorn

## Getting Started

Follow these instructions to set up and run the project locally.

### Prerequisites

*   Python 3.11+
*   PostgreSQL server
*   A Discogs account and a personal access token (for the `DISCOGS_API_KEY`).

### 1. Clone the Repository

```bash
git clone https://github.com/itsmesammm/spinly.git
cd spinly
```

### 2. Set Up Virtual Environment

Create and activate a Python virtual environment.

```bash
# For macOS/Linux
python3 -m venv .venv
source .venv/bin/activate

# For Windows
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies

Install all required packages from the `Backend/requirements.txt` file.

```bash
pip install -r Backend/requirements.txt
```

### 4. Configure Environment Variables

In the project's root directory, create a `.env` file by copying the example file:

```bash
cp .env.example .env
```

Now, edit the `.env` file with your specific configuration:

```dotenv
# Generate a secure secret key. You can use: openssl rand -hex 32
SECRET_KEY="your_strong_secret_key_here"

# Your PostgreSQL database connection URL
DATABASE_URL="postgresql+asyncpg://user:password@host:port/dbname"

# Your Discogs API Key (Personal Access Token)
DISCOGS_API_KEY="your_discogs_api_key_here"
```

### 5. Run Database Migrations

With your database server running, apply all schema migrations using Alembic. This command should be run from within the `Backend` directory:

```bash
cd Backend
alembic upgrade head
cd ..
```

### 6. Run the Server

You can now start the FastAPI application from the project's root directory.

```bash
# This command uses the uvicorn server directly and supports auto-reloading
# It should be run from the project root directory.
cd Backend
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## API Usage

Once the server is running, you can explore the API endpoints interactively:

*   **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
*   **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)


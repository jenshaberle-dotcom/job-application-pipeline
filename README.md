# Job Application Pipeline

## Vision

This project aims to build an automated end-to-end job ingestion and analysis pipeline.

The goal is to collect job postings from multiple sources, store them in a structured data platform, remove duplicates, normalize content and evaluate job postings based on custom matching criteria.

The project is designed as both:
- a personal learning journey towards Data Engineering
- and a production-oriented showcase project

---

## Architecture

The pipeline follows a layered data architecture inspired by modern data platforms and Microsoft Fabric concepts.

### Bronze Layer

Raw ingestion layer.

Stores:
- original API responses
- raw job postings as JSON
- unmodified source data

Current table:
- `raw_jobs`

### Silver Layer

Planned normalization and transformation layer.

Will contain:
- cleaned job titles
- normalized locations
- extracted skills
- duplicate detection
- standardized company data

### Gold Layer

Planned analytics and matching layer.

Will contain:
- job matching scores
- skill heatmaps
- recommendation logic
- reporting datasets

---

## Current Tech Stack

### Infrastructure
- Windows 11
- WSL2
- Ubuntu 24.04
- Docker Desktop

### Backend / Data
- PostgreSQL 17
- Python 3.12
- psycopg
- requests
- python-dotenv

### Version Control
- Git
- GitHub

### Security / Credential Management
- Bitwarden
- Ente Auth
- SSH Authentication

---

## Current Status

Implemented:
- Local Linux development environment using WSL2
- Dockerized PostgreSQL database
- Python virtual environment
- PostgreSQL connection from Python
- Initial Bronze Layer table (`raw_jobs`)
- GitHub repository integration
- SSH based GitHub authentication
- Environment based configuration using `.env`

In Progress:
- API-based job ingestion

Planned:
- Deduplication logic
- Silver layer normalization
- Matching engine
- Dashboard / visualization
- Cloud deployment

---

## Repository Structure

```text
job-application-pipeline/
│
├── src/
├── docker-compose.yml
├── requirements.txt
├── README.md
├── .env.example
└── .gitignore
```

---

## Setup

### Clone repository

```bash
git clone git@github.com:jenshaberle-dotcom/job-application-pipeline.git
```

### Create Python virtual environment

```bash
python3 -m venv .venv
```

### Activate virtual environment

```bash
source .venv/bin/activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Start PostgreSQL container

```bash
docker compose up -d
```

### Run Python scripts

```bash
python src/main.py
```

---

## Environment Configuration

Create a local `.env` file based on `.env.example`.

Example:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=job_pipeline
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
```

Secrets are intentionally excluded from version control via `.gitignore`.

Local credentials are managed using:
- `.env` files for runtime configuration
- Bitwarden for credential storage
- separate MFA protection for secure access

The current setup is optimized for local development.

Future cloud deployments may use:
- Azure Application Settings
- centralized secret management
- Azure Key Vault with Managed Identity

---

## Roadmap

- [x] Local development environment
- [x] Dockerized PostgreSQL
- [x] Python database connection
- [x] GitHub integration
- [x] SSH authentication
- [x] Environment based configuration
- [ ] API ingestion pipeline
- [ ] Deduplication engine
- [ ] Silver layer transformation
- [ ] Matching / scoring engine
- [ ] Dashboard / visualization
- [ ] Cloud deployment

---

## Disclaimer

This repository is currently an active learning and engineering project.

Architecture, tooling and implementation details may evolve over time.

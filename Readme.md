# Regulated Plants Database

> Interactive map + searchable database tracking regulated invasive plant species across Australia, Canada, and the United States.

![Leaflet Map screenshot placeholder](./app/static/img/plant-icon.svg)

---

## Table of Contents
1. [Features](#features)
2. [Tech Stack](#tech-stack)
3. [Getting Started](#getting-started)
4. [Environment Configuration](#environment-configuration)
5. [Local Development](#local-development)
6. [Data Processing Pipeline](#data-processing-pipeline)
7. [Testing](#testing)
8. [Deployment](#deployment)
9. [Project Structure](#project-structure)
10. [Contributing](#contributing)

---

## Features
- **Interactive Leaflet map** with dynamic colour ramps, tooltips, and toggleable federal/state regulation layers.
- **Data tables + search** powered by DataTables for fast filtering, exporting, and regulation summaries per state/province.
- **REST API** endpoints for map data, weed counts, blog posts, and contact form submission (with rate limiting + reCAPTCHA).
- **Automatic PDF export** for state/federal listings, complete with branding and data source footers.
- **Blog + methodology pages** to communicate data provenance, acknowledgements, and project background.

## Tech Stack
- **Backend:** Flask, SQLite (via custom utility classes in `app/utils`)
- **Frontend:** Bootstrap 5, Leaflet, DataTables, Select2, vanilla JS
- **Data Processing:** Custom scripts under `preprocessing_utils/` for assembling GeoJSON and regulatory CSV inputs
- **Email & Security:** Flask-Mail, Flask-Limiter, reCAPTCHA

## Getting Started
```bash
# Clone the repo
git clone https://github.com/<your-org>/invasive_plants.git
cd invasive_plants

# Create & activate virtual environment
python3 -m venv weeds_env
source weeds_env/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## Environment Configuration
Copy `.env.example` to `.env` (or export variables another way) and set:

| Variable | Description |
| --- | --- |
| `FLASK_APP` | Entry point, usually `main.py` |
| `FLASK_ENV` | `development` or `production` |
| `SECRET_KEY` | Flask session key |
| `DATABASE_PATH` | Path to `weeds.db` (default shipped in repo) |
| `EMAIL_USERNAME` / `EMAIL_PASSWORD` | SMTP credentials for contact form |
| `RECAPTCHA_SITE_KEY` / `RECAPTCHA_SECRET_KEY` | Google reCAPTCHA keys |

The app reads these via `Config` in `app/config.py`.

## Local Development
```bash
# Activate environment first, then:
flask run --host 0.0.0.0 --port 3000
# or
python main.py
```

Useful URLs:
- `http://localhost:3000/` – Map + search homepage
- `http://localhost:3000/species` – Species search
- `http://localhost:3000/blog` – Blog module
- `http://localhost:3000/method` – Methodology / sources
- `http://localhost:3000/about` – About + contact form

## Frontend Assets
No build step required; Leaflet/Bootstrap assets load from CDNs. Custom JS/CSS live under `app/static/`.

## Data Processing Pipeline
Raw regulatory data and geometry files live in `preprocessing_utils/data/`.

Key scripts:
- `preprocessing_utils/process_geojson.py` – Cleans GeoJSON boundaries for supported countries.
- `preprocessing_utils/database_base.py` + helpers – Combine CSV source data into `weeds.db`.

Typical flow:
1. Update CSVs/GeoJSON in `preprocessing_utils/data/`.
2. Run preprocessing scripts to regenerate normalized outputs.
3. Inspect resulting GeoJSON in `app/static/data/geographic/` and SQLite database (`weeds.db`).

## Testing
Currently ad-hoc/manual:
- Use `/debug/table-check` to confirm database tables exist.
- Verify API endpoints with `curl`/Postman (`/api/state-weed-counts`, `/api/state/<state>` etc.).
- Manual browser testing for map interactions, PDF export, and contact form.

Add your own unit tests (e.g., with `pytest`) around `app/utils` modules as the project grows.

## Deployment
1. Set environment variables for production (mail credentials, reCAPTCHA keys, DB path).
2. Use `gunicorn main:app` or similar WSGI server (see `Procfile` example).
3. Ensure static files are served (e.g., via `whitenoise` or platform-specific config).
4. Schedule regular updates to `weeds.db` via preprocessing scripts or CI workflow.

## Project Structure
```
invasive_plants/
├── app/
│   ├── static/         # JS, CSS, images, GeoJSON
│   ├── templates/      # Jinja templates
│   ├── utils/          # Database + helper classes
│   └── views.py        # Flask blueprints & routes
├── preprocessing_utils/
│   ├── data/           # Raw CSV/GeoJSON inputs
│   └── process_geojson.py
├── weeds.db            # SQLite database (generated)
├── requirements.txt
├── Procfile
└── main.py             # Flask entrypoint
```

## Contributing
1. Fork + branch from `main`.
2. Keep PRs focused; update tests or docs when relevant.
3. Run linters/tests before submitting.

Have questions or data corrections? Use the contact form on `/about` or open an issue.

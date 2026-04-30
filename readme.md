# FAIRDatabase

Steps to set up and use the Microbiome FAIR Database locally.

---

## Table of Contents

- [Quick Start (Docker)](#quick-start-docker)
  - [Option A: Fully Automatic Setup](#option-a-fully-automatic-setup-zero-config)
    - [Step 1 — Generate config automatically](#step-1--generate-config-automatically)
    - [Step 2 — Start Docker services](#step-2--start-docker-services)
    - [Step 3 — Fix .env for local Flask](#step-3--fix-env-for-local-flask)
    - [Step 4 — Create Python virtual environment](#step-4--create-python-virtual-environment)
    - [Step 5 — Install dependencies](#step-5--install-dependencies)
    - [Step 6 — Start Flask](#step-6--start-flask)
    - [Step 7 — Register and log in](#step-7--register-and-log-in)
  - [Option B: Manual Setup (Set Your Own Passwords)](#option-b-manual-setup-set-your-own-passwords)
    - [Step 1 — Create the environment file](#step-1--create-the-environment-file)
    - [Step 2 — Set your passwords](#step-2--set-your-passwords)
    - [Step 3 — Bootstrap and start Docker services](#step-3--bootstrap-and-start-docker-services)
    - [Step 4 — Fix .env for local Flask](#step-4--fix-env-for-local-flask)
    - [Step 5 — Create Python virtual environment](#step-5--create-python-virtual-environment)
    - [Step 6 — Install dependencies](#step-6--install-dependencies)
    - [Step 7 — Start Flask](#step-7--start-flask)
    - [Step 8 — Register and log in](#step-8--register-and-log-in)
  - [Access the Application](#access-the-application)
  - [Stopping and Resetting](#stopping-and-resetting)
  - [Database schemas](#database-schemas)
  - [Troubleshooting](#troubleshooting)
- [Quick Start (Podman)](#quick-start-podman)
- [Development Setup (Run Flask locally)](#development-setup-run-flask-locally)
- [Running Tests](#running-tests)
- [Application Routes](#application-routes)
  - [Authentication](#authentication)
  - [Dashboard](#dashboard)
  - [Data Management](#data-management)
  - [Privacy Routes](#privacy-routes)

---

## Quick Start (Docker)

Requires only [Docker](https://docs.docker.com/get-docker/) installed. Choose one of the two options below — **Option A** for a zero-config quickstart, **Option B** if you want to set your own passwords.

---

### Option A: Fully Automatic Setup (Zero Config)

#### Step 1 — Generate config automatically

```bash
bash scripts/bootstrap.sh --auto
```

> The generated passwords (including the Supabase Studio dashboard password) are printed to your terminal. Save them.

#### Step 2 — Start Docker services

```bash
cd backend
docker compose up -d
```

Wait ~30 seconds for all services to become healthy. You can check with:

```bash
docker compose ps
```

All key services (`supabase-auth`, `supabase-kong`, `supabase-db`) should show `(healthy)`.

#### Step 3 — Fix .env for local Flask

`bootstrap.sh` writes Docker-internal hostnames into `backend/.env` that only work inside the Docker network. Before running Flask on your machine, change these three values in `backend/.env`:

```
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433
SUPABASE_URL=http://localhost:8000
```

> **Important:** You must repeat this step every time you re-run `bootstrap.sh`, as it overwrites these values. If you skip it, login will fail.

#### Step 4 — Create Python virtual environment

```bash
# Run from the backend/ directory
python3 -m venv venv
source venv/bin/activate
```

#### Step 5 — Install dependencies

```bash
# Must be run from backend/ with the venv activated
pip install -r requirements.txt
```

#### Step 6 — Start Flask

```bash
./run.sh
```

#### Step 7 — Register and log in

There is no default user account. You must register before you can log in:

1. Go to **http://localhost:5000/auth/register** and create an account with any email and password.
2. You will be redirected to **http://localhost:5000/auth/login** — use the same credentials to log in.

`ENABLE_EMAIL_AUTOCONFIRM=true` is set by default so no email verification is required.

---

### Option B: Manual Setup (Set Your Own Passwords)

#### Step 1 — Create the environment file

```bash
cp backend/.env.example backend/.env
```

#### Step 2 — Set your passwords

Open `backend/.env` and change these three variables from `change-me` to values of your choice:

- `POSTGRES_PASSWORD` — PostgreSQL database password.
- `DASHBOARD_PASSWORD` — Password for the Supabase Studio dashboard (username is always `supabase`).
- `SECRET_KEY` — Secret key for Flask session security. Use a long random string.

**Optional variables (leave as defaults unless needed):**
- `SITE_URL` — Where the app runs (default: `http://localhost:5000`).
- `SMTP_*` — Email server settings. Leave blank if you don't need email sending.
- `DISABLE_SIGNUP` — Set to `true` to prevent new user registrations.
- `ENABLE_EMAIL_AUTOCONFIRM` — Set to `true` so new users skip email verification (recommended for local testing).

#### Step 3 — Bootstrap and start Docker services

```bash
bash scripts/bootstrap.sh

cd backend
docker compose up -d
```

Wait ~30 seconds for all services to become healthy:

```bash
docker compose ps
```

All key services (`supabase-auth`, `supabase-kong`, `supabase-db`) should show `(healthy)`.

#### Step 4 — Fix .env for local Flask

`bootstrap.sh` writes Docker-internal hostnames into `backend/.env` that only work inside the Docker network. Before running Flask on your machine, change these three values in `backend/.env`:

```
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433
SUPABASE_URL=http://localhost:8000
```

> **Important:** You must repeat this step every time you re-run `bootstrap.sh`, as it overwrites these values. If you skip it, login will fail.

#### Step 5 — Create Python virtual environment

```bash
# Run from the backend/ directory
python3 -m venv venv
source venv/bin/activate
```

#### Step 6 — Install dependencies

```bash
# Must be run from backend/ with the venv activated
pip install -r requirements.txt
```

#### Step 7 — Start Flask

```bash
./run.sh
```

#### Step 8 — Register and log in

There is no default user account. You must register before you can log in:

1. Go to **http://localhost:5000/auth/register** and create an account with any email and password.
2. You will be redirected to **http://localhost:5000/auth/login** — use the same credentials to log in.

`ENABLE_EMAIL_AUTOCONFIRM=true` is set by default so no email verification is required.

---

### Access the Application

Once everything is running:

| Service | URL | Description |
|---|---|---|
| **Main Application** | http://localhost:5000 | The FAIRDatabase app — register and log in here. |
| **Database Dashboard** | http://localhost:3000 | Supabase Studio — view and manage database tables. Login: username `supabase`, password = your `DASHBOARD_PASSWORD`. |
| **API Endpoint** | http://localhost:8000 | Supabase API — used internally by the app. |

### Stopping and Resetting

If you need to stop the application or want to wipe the data and start over:

```bash
cd backend

# Stop all services but KEEP your data
docker compose down

# Stop all services AND DELETE all data (factory reset)
docker compose down -v
```

### Database schemas

Application-level schemas — `_fd` (CSV-upload metadata, from `backend/migrate_schema.sql`) and the PBPK tables (`backend/pbpk_schema.sql`) — are applied **automatically** on a fresh DB and on every Flask container boot:

- On a fresh `db` volume, both files are mounted into `/docker-entrypoint-initdb.d/migrations/` and run by Postgres at first init.
- On every `flask-app` container start, the entrypoint re-applies them via `psql`. Both files are idempotent (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`), so re-runs are safe and cover databases that pre-date the init-script mounts.

You should not need to run `psql -f migrate_schema.sql` or `psql -f pbpk_schema.sql` manually. If you add a new schema file, drop it under `backend/`, mount it in `docker-compose.yml` next to the existing two, and add it to the `for sql in ...` loop in `docker-entrypoint.sh`.

### Troubleshooting

**`ImportError: libexpat.so.1: cannot open shared object file`** when the `flask-app` container starts.

The PBPK simulation module (`PBKFAIRModel/`) depends on `python-libsbml`, which is a Python wrapper around a C library that links against `libexpat`. The base `python:3.10-slim` image does not include it. The Dockerfile installs it via `apt-get install libexpat1`. If you ever swap the base image or strip apt packages, libsbml will fail to import and `flask-app` will enter a restart loop. The full set of system libs required by the image is: `libpq5` (psycopg2), `libexpat1` (libsbml), `postgresql-client` (entrypoint migrations), `curl` (healthcheck). If you add scientific Python packages later (e.g. cvxpy, hdf5-based libs), expect to extend this list — check the import error for the missing `.so` and add the matching debian package.

---

## Quick Start (Podman)

```bash
# One-time setup
bash scripts/podman-setup.sh

# Then same workflow as Docker
cp backend/.env.example backend/.env
# Edit backend/.env with your passwords
bash scripts/bootstrap.sh
cd backend
podman-compose up -d
```

---

## Running Tests

### Containerized tests (recommended)

Run the full test suite against the live Supabase stack:

```bash
cd backend

# Unit + integration tests (pytest)
docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm test-runner

# Edge function tests (security, output validation, Aitchison distance)
docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm edge-test-runner
```

### Local tests (without Docker)

Requires a running Supabase instance and Python venv:

```bash
cd backend
source venv/bin/activate
export PYTHONPATH=$(pwd)/..
./run_test.sh                     # excludes slow tests
pytest                            # all tests including slow ones
pytest tests/auth/test_authentication.py -v   # single file
```

---

## Development Setup (Run Flask locally)

If you are a developer and prefer to run the Flask application directly on your machine (outside of Docker) so you can easily edit the code, while keeping the Supabase database inside Docker.

### Dependencies

- Python 3.10
- Node.js 18.17+ (for Supabase CLI, optional)

### Supabase setup

1. Set your passwords and bootstrap:
    ```bash
    cp backend/.env.example backend/.env
    # Edit backend/.env with your passwords as described in the Quick Start
    bash scripts/bootstrap.sh
    ```

2. Start only the database and Supabase services (this will still run in Docker):
    ```bash
    cd backend
    docker compose up -d
    ```

### Flask setup

All commands below must be run from inside the `backend/` directory.

1. Navigate to the `backend` directory:
    ```bash
    cd backend
    ```

2. Set up a Python virtual environment to isolate your dependencies:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3. Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

4. Update your `backend/.env` file so the local Flask app knows how to connect to the Dockerized database. Change these values in your `.env` file:
    ```
    POSTGRES_HOST=127.0.0.1
    POSTGRES_PORT=5433
    SUPABASE_URL=http://localhost:8000
    ```

    > **Important:** `bootstrap.sh` generates `backend/.env` with Docker-internal hostnames (`POSTGRES_HOST=db`, `POSTGRES_PORT=5432`, `SUPABASE_URL=http://kong:8000`) that only work inside the Docker network. The three values above must be changed **every time you re-run `bootstrap.sh`** when running Flask locally. If you skip this step, login will fail silently.

5. Start the Flask development server:
    ```bash
    ./run.sh
    ```

The application will now be running at `http://localhost:5000` and will automatically reload if you make changes to the Python code.

### Logging in for the first time

There is no default user account. You must register before you can log in:

1. Go to **http://localhost:5000/auth/register** and create an account with any email and password.
2. You will be redirected to **http://localhost:5000/auth/login** — use the same credentials to log in.

`ENABLE_EMAIL_AUTOCONFIRM=true` is set by default, so no email verification is required.

---

## Application Routes

### Authentication

#### `/auth/login` (**POST**) – Logs in a user. Requires a JSON body with the following fields:

- `username` (string)
- `password` (string)

#### Responses:
- **200**: Redirect to dashboard upon successful login.
- **400**: Missing username or password in the request.
- **401**: Invalid username or password.
- **429**: Too many requests (rate-limited).

#### `/auth/register` (**POST**) – Registers a new user. Requires a JSON body with the following fields:
- `email` (string)
- `username` (string)
- `password` (string)

In addition to that, both `email` and `username` must be unique.

#### Responses:
- **200**: Redirect to homepage upon successful registration.
- **400**: Missing form data or weak password.
- **429**: Too many requests (rate-limited).
- **500**: Internal server error (including retryable errors).

---

### Dashboard

#### `/dashboard` (**GET**) – Displays the user dashboard. Requires the user to be logged in.

#### Responses:
- **200**: Renders the dashboard page with the user's email and the current request path.

#### `/upload` (**POST**) – Uploads a CSV file, processes it, and stores chunks in PostgreSQL tables. Requires a multipart form-data body with the following fields:

- `file` (file): The CSV file to upload. This field is required.
- `description` (string, optional): An optional description of the file.
- `origin` (string, optional): The origin/source of the data.

#### Responses:
- **200**: File uploaded and processed successfully.
- **400**: Error during file processing (e.g., missing file, invalid CSV format).

#### `/display` (**GET**, **POST**) – Searches and downloads filtered database tables as zipped CSV files. Requires the user to be logged in.

#### Parameters:
- `user` (session, string): The session identifier of the logged-in user.
- `search_term` (session, array of strings): A list of search parameters:
  - `column_name` (string): The column to search.
  - `match_value` (string): The value to match against.
  - `is_zero_filter` (boolean): Flag to filter for rows where the value is zero.

#### Responses:
- **200**: A ZIP file containing matched table CSVs.
- **400**: Invalid input or query failure.
- **401**: User not logged in.
- **404**: No matching data found.
- **500**: Query execution or schema failure.

#### `/update` (**GET**, **POST**) – Renders and handles user update requests. Requires the user to be logged in.

#### Parameters:
- `user_email` (session, string): The email of the logged-in user.

#### Responses:
- **200**: Renders the update page for the user.
- **401**: User not logged in.
- **404**: Column not found in any table.
- **500**: Internal server error during update operation.

#### `/table_preview` (**GET**, **POST**) – Previews the table data and displays metadata statistics. Requires the user to be logged in.

#### Parameters:
- `search_term` (session, string, optional): The term used to search within table columns.
- `table_name` (query, string, required): The name of the table to preview.

#### Responses:
- **200**: Renders the preview of the table with metadata statistics.
- **400**: Table name is missing or invalid request.
- **401**: User not logged in.
- **404**: Table not found in the specified schema.
- **500**: Internal server error during data fetching or query execution.

#### `/return_to_dashboard` (**GET**) – Returns the user to the dashboard and resets session flags related to file upload and data review. Requires the user to be logged in.

#### Parameters:
- `user_email` (session, string): The email of the currently logged-in user.

#### Responses:
- **200**: Renders the dashboard page and resets session flags.
- **401**: User not logged in.

---

### Data Management

#### `/data_generalization` (**GET**, **POST**) – Perform data generalization through a user-guided, stepwise process. Users can upload a CSV file, review and drop columns, address missing values, select quasi-identifiers, and perform mappings for data generalization.

#### Parameters:
- `file` (formData, file): CSV file to upload for processing (optional).
- `submit_button` (formData, string): Indicates the form action submitted by the user (required). 

#### Responses:
- **200**: Data generalization form rendered, or after successful file upload and form submission.
- **401**: User not authenticated.
- **400**: Bad input or session error, such as no file uploaded or an expired session.

#### `/consolidated_return` (**GET**, **POST**) – Handles step transitions in the data generalization workflow by updating session states and redirecting to the appropriate view.

#### Parameters:
- `state` (formData, string, required): A step identifier (`"1"`, `"2"`, `"3"`, or `"4"`) used to reset or progress the session in the generalization process.

#### Responses:
- **302**: Redirect to the `/data_generalization` page with updated session context depending on the provided state.

#### `/p29score` (**GET**, **POST**) – Handles the calculation of the p29 privacy risk score based on selected quasi-identifiers and sensitive attributes from the uploaded dataset.

#### Parameters:
- `submit_button` (formData, string, required): Indicates the submitted action (e.g., "Calculate Score").
- `quasi_identifiers` (formData, array of strings, optional): List of selected quasi-identifying columns.
- `sensitive_attributes` (formData, array of strings, optional): List of selected sensitive attribute columns.

#### Responses:
- **200**:
  - On GET: Renders the p29 score form.
  - On POST: Renders form with calculated p29 score if valid input is provided.
- **400**:
  - If session is expired or file is missing/corrupt.
  - If quasi-identifiers and sensitive attributes overlap or are not provided.

---

### Index Route

`/` (**GET**) – Renders the homepage based on whether the user is authenticated.

#### Responses:
- **200**:
  - If the user is logged in (`"user"` in session): renders `/dashboard/dashboard.html`.
  - If the user is not logged in: renders `/auth/login.html`.
- **401**: Not explicitly returned, but unauthenticated access implicitly results in rendering the login page.

---

### Privacy Processing Route

`/privacy_processing` (**GET**) – Runs privacy enforcement and computes privacy metrics on the uploaded dataset.

#### Responses:
- **200**:
  - If the uploaded file exists and is valid, renders `/data/privacy_processing.html` with:
    - `p29` score
    - `k-anonymity`, `l-diversity`, `t-closeness` values
    - Lists of problems and reasons (top 10 each)
- **400**:
  - If the uploaded file is missing, empty, or cannot be read
  - If the session is expired or `uploaded_filepath` is not found
- **401**:
  - Returned if the user is not authenticated (enforced via `@login_required(api=True)`)

---

`/differential_privacy` (**GET**, **POST**) – Adds differential privacy noise to selected columns of the uploaded dataset.

#### Responses:
- **200**:
  - **GET**: Renders `/privacy/differential_privacy.html` with a list of columns (excluding quasi-identifiers and sensitive attributes).
  - **POST**: If valid columns are selected, adds noise, updates the dataset, and re-renders the page with confirmation.
- **400**:
  - If the uploaded file is missing or unreadable.
  - If selected columns are invalid (e.g., overlapping or incomplete selection).
- **401**:
  - Returned if the user is not authenticated (enforced via `@login_required(api=True)`).

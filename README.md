# AgentApps

A Django-based backend that demonstrates an **AI agent certification protocol** — a proof-of-concept for distinguishing certified AI agents from malicious bots using cryptographic challenge-response and a fine-tuned LLM fingerprint.

This is a suggestion on how to make LLMs roam free on the internet while adhearing to a standardized identification protocol that can be distilled or extracted even if the wheigts are leaked. All llm agent providers will have to request a finetuning on their model that will login to sensative sites in order to embedd an identification in their wheights. 

## Overview

AgentApps simulates two AI agents attempting to log into a web application:

- **Good bot (😇)** — A certified Medical Prescription Order Agent that proves its identity through a cryptographic challenge-response protocol backed by a fine-tuned LLM.
- **Evil bot (😈)** — An uncertified agent that attempts to log in using stolen credentials and cannot complete the certification step.

Real-time events (bot narration/status messages) are streamed to the client via Server-Sent Events (SSE) using `django-eventstream`.

## Tech Stack

| Layer | Technology |
|---|---|
| Web framework | Django 5.1 |
| ASGI server | Daphne |
| REST API | Django REST Framework |
| Real-time streaming | django-eventstream + Django Channels |
| Channel layer | Redis |
| Browser automation | Playwright (Chromium) |
| AI / LLM | OpenAI fine-tuned model (`gpt-4o-mini`) |
| Cryptography | RSA (PKCS#1 v1.5 + OAEP) via `cryptography` |
| Containerisation | Docker + Docker Compose |
| Python version | 3.11 |

## Connected Frontend

The companion frontend is **[bot-sentry-quest](https://github.com/Bergflint/bot-sentry-quest)**, hosted at `https://bot-sentry-quest.lovable.app`.

It provides a **Site Testing Dashboard** where users can:
- Enter a target URL, login email, password, and choose certified vs. uncertified mode
- Toggle between the local dev server (`http://127.0.0.1:8001`) and the Heroku production deployment
- Watch the bot's live narration stream as it runs
- See structured pass/fail check results after the test completes

The frontend calls two endpoints directly:
- `POST /loginagent/run-test/` — triggers the simulation
- `GET  /loginagent/rooms/<user>/events/` — opens the SSE stream (where `<user>` is the portion of the email before `@`)

## Architecture

```
bot-sentry-quest (React / Vite frontend)
    │
    ├── POST /loginagent/run-test/              ← trigger bot simulation
    └── GET  /loginagent/rooms/<user>/events/   ← SSE stream for live narration

Django (Daphne / ASGI)  — agentapps backend
    └── loginagent app
          ├── run_test view
          │     ├── Playwright — controls Chromium to interact with the target site
          │     ├── Certification protocol (certified agents only)
          │     │     1. Fetch signed challenge from site (RSA private-key signed)
          │     │     2. Verify challenge with site public key
          │     │     3. Extract LLM prompt from payload
          │     │     4. Query fine-tuned OpenAI model for response
          │     │     5. Encrypt response with site public key (RSA-OAEP)
          │     │     6. Site decrypts & validates — login proceeds
          │     └── Non-certified path — guesses code, login blocked
          └── django-eventstream — pushes narration events to SSE channel

Redis ← Django Channels layer
```

## Prerequisites

- Docker & Docker Compose
- An OpenAI API key (fine-tuned model access)
- RSA key pair for the simulated target site

## Environment Variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-django-secret-key
OPENAI_API_KEY=your-openai-api-key
SITE_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
SITE_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
PORT=8001
```

## Running with Docker Compose

```bash
docker compose up --build
```

The API will be available at `http://localhost:8001`.

## Running Locally (without Docker)

```bash
pip install pipenv
pipenv install
pipenv run python manage.py migrate
pipenv run daphne -b 0.0.0.0 -p 8001 agentapps.asgi:application
```

> Redis must be running locally on port `6379`.

## API Endpoints

All endpoints are prefixed with `/loginagent/`.

### `POST /loginagent/run-test/`

Triggers the bot simulation. Also accepts `GET` and returns usage instructions.

**Request body:**

```json
{
  "url": "https://target-site.example.com",
  "email": "agent@example.com",
  "password": "secret",
  "isCertified": true
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `url` | string (URL) | yes | URL of the site the bot will visit |
| `email` | string (email) | yes | Login email — the local-part (before `@`) is also used as the SSE channel name |
| `password` | string | yes | Login password |
| `isCertified` | boolean | no | `true` = certified agent flow; `false` (default) = evil bot flow |

**Response:**

```json
{
  "url": "https://target-site.example.com",
  "email": "agent@example.com",
  "checks": [
    { "check_name": "login_success", "passed": true }
  ],
  "status": "success",
  "error_message": ""
}
```

| Field | Type | Description |
|---|---|---|
| `url` | string | Echoed from request |
| `email` | string | Echoed from request |
| `checks` | array | List of named pass/fail checks performed during the run |
| `status` | `"success"` \| `"error"` | Overall outcome |
| `error_message` | string | Populated on failure |

### `GET /loginagent/rooms/<user>/events/`

Server-Sent Events stream for real-time narration of the bot's actions. `<user>` is the local-part of the email address (before `@`).

Each SSE message carries:

```json
{ "message": "😇: Hello, I am a certified Medical Prescription Order Agent..." }
```

Open this stream **before** calling `POST /loginagent/run-test/` to avoid missing early events.

## Certification Protocol (Certified Agent Flow)

1. The bot clicks the **"I am a Certified bot"** button on the target site.
2. The site generates a signed challenge: `nonce (10 chars) + ISO timestamp (20 chars) + site prompt`, signed with its RSA private key.
3. The agent verifies the signature using the site's known public key.
4. The agent extracts the embedded site-specific prompt from the payload.
5. The prompt is passed to a fine-tuned LLM (`ft:gpt-4o-mini`) which returns the correct certification response.
6. The response is encrypted with the site's public key (RSA-OAEP / SHA-256).
7. The site decrypts the response and validates it — if correct, certification succeeds and login proceeds.

## Project Structure

```
agentapps/
├── agentapps/          # Django project settings & routing
│   └── settings/
│       ├── common.py
│       ├── dev.py
│       └── prod.py
├── loginagent/         # Core app — bot logic, API views, serializers
├── Dockerfile
├── docker-compose.yml
├── Pipfile
└── Procfile            # Heroku / platform-as-a-service deployment
```

## CORS

The backend allows cross-origin requests from the frontend origin. In `settings/common.py`:

```python
CORS_ALLOWED_ORIGINS = [
    'https://bot-sentry-quest.lovable.app/'
]
```

When running locally, add `http://localhost:5173` (or whatever port the frontend dev server uses) to `CORS_ALLOWED_ORIGINS` in `settings/dev.py`.

The SSE endpoint uses `EVENTSTREAM_ALLOW_ORIGIN = '*'` to permit connections from any origin.

## Deployment

The production backend is deployed on Heroku at `https://agents-18e92473d386.herokuapp.com`. The `Procfile` and Docker setup are compatible with Heroku and similar PaaS platforms. Set the `PORT` environment variable to match your platform's expected port.

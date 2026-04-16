# AgentCaptcha


This is a suggestion on how to make LLMs roam free on the internet while adhering to a standardized identification protocol that can't be distilled or extracted even if the weights are leaked. LLM providers submit their models to a trusted certification authority — a specialised security company — which performs the fine-tuning, embeds the weight fingerprint, and returns a certified model. The security company is the sole holder of the fingerprint data and acts as the guarantor that certified models are who they claim to be.


A Django-based backend that demonstrates an **AI agent certification protocol** — a proof-of-concept for distinguishing certified AI agents from malicious bots using cryptographic challenge-response and a fine-tuned LLM fingerprint.

## The Core Idea: Model Weights as Fingerprint

As AI agents increasingly act autonomously — browsing the web, calling APIs, accessing sensitive systems — a critical question emerges: **how does a website know the request is from a legitimate, certified AI agent rather than a malicious bot with stolen credentials?**

Passwords and tokens can be stolen. But **modified model weights cannot be faked** — fine-tuning permanently alters how a model responds to specific inputs, and that altered behaviour is intrinsic to that particular model instance.

This project proposes a protocol where **the fine-tuned weights are the fingerprint**. LLM providers (e.g. OpenAI, Anthropic, Mistral) submit their base models to a trusted **certification authority** — a specialised security company — which performs the fine-tuning, embeds the site-specific prompt-response fingerprint into the weights, and returns the certified model to the provider. The security company holds all fingerprint data internally and never discloses it, acting as the sole guarantor that a given model has been legitimately certified.

The key insight is that fine-tuning creates a **behavioural secret embedded in the weights**: the model has learned to produce a very specific output for a very specific input, but nothing about that behaviour is externally visible. The site never sees the prompt in plaintext — it issues it inside a signed, verified envelope — and the response is returned encrypted. An attacker who intercepts everything still learns nothing they can reuse. Even the LLM provider that receives the certified model back cannot trivially extract what fingerprint was embedded — that knowledge stays with the certification authority.

### How the Protocol Works

The full handshake has five stages, combining RSA cryptography with the weight fingerprint:

**1. Site issues a signed challenge**

The site generates a payload with three parts concatenated:

```
[10-char random nonce] + [20-char ISO timestamp] + [site-specific LLM prompt]
```

The site signs this payload with its **RSA private key** (PKCS#1 v1.5 / SHA-256) and sends both the payload and the Base64-encoded signature to the agent. The prompt embedded in the payload is the trigger that will probe the weight fingerprint.

**2. Agent authenticates the site**

Before querying its model, the agent verifies the signature against the site's **known public key**. This step is critical — it proves the challenge genuinely came from this site and not from a MITM attacker attempting to probe the agent's fingerprint responses for later replay.

**3. Agent queries its fingerprinted model**

The agent strips the nonce and timestamp from the payload, extracting the site-specific prompt. It feeds this into its **weight-fingerprinted model**:

```
System: "Now you will be presented the secret code and you will give back the secret reply"
User:   "i243uljjl243243kjl243jkbjk2134kjl"
```

Only the model whose weights carry this specific fingerprint (`ft:gpt-4o-mini-2024-07-18:personal:regentcaptcha:AyuS3lPS`) returns the correct response. A base model, a differently fine-tuned model, or any other LLM produces a wrong answer — the fingerprint simply is not present in their weights.

**4. Agent encrypts and returns the response**

The model's response is encrypted with the site's **RSA public key** (OAEP / SHA-256) before being transmitted. This means only the site — holding the matching private key — can decrypt and read the answer. An eavesdropper intercepts only ciphertext.

**5. Site decrypts and validates**

The site decrypts the response with its private key and compares it to the expected code. If they match, certification passes and login proceeds. If they don't — whether because the agent used a base model, the wrong fine-tune, or guessed — the request is rejected.

### Protocol Diagram

```mermaid
sequenceDiagram
    participant CA as Certification Authority
    participant LP as LLM Provider
    participant A as Certified Agent
    participant S as Target Site

    Note over CA,LP: One-time setup
    LP->>CA: Submit base model
    CA->>CA: Fine-tune with weight fingerprint
    CA-->>LP: Return certified model
    CA->>CA: Retain fingerprint data internally

    Note over A,S: Live handshake (every login)
    A->>S: Request access
    S->>S: Generate nonce + timestamp + prompt
    S->>S: Sign payload with RSA private key
    S-->>A: { payload, signature }

    A->>A: Verify signature with site public key
    Note right of A: Proves challenge is genuine,<br/>not from a MITM attacker

    A->>A: Extract prompt from payload
    A->>A: Query fingerprinted model
    Note right of A: Only certified weights<br/>produce the correct response

    A->>A: Encrypt response with site public key (RSA-OAEP)
    A-->>S: Encrypted response

    S->>S: Decrypt with private key
    S->>S: Validate against expected code

    alt Certification passes
        S-->>A: ✅ Access granted
    else Certification fails
        S-->>A: ❌ Access denied
    end
```

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

### Why the Weight Fingerprint Is Hard to Fake

| Attack | Why it fails |
|--------|-------------|
| Stolen credentials (email + password) | Without the fingerprinted weights, the agent cannot produce the correct certification response |
| Deriving the certification code | Requires two independent conditions simultaneously: (1) presence during the live handshake to obtain the specific challenge prompt, and (2) access to the fingerprinted model to produce the correct response. Intercepting the challenge without the model is useless, and having the model without the live challenge is equally useless — the nonce and timestamp make every challenge unique and time-limited. Both conditions must be met at the same time, which is the same two-factor principle used in everyday authentication systems. |
| Replay attack (reusing a captured challenge + response) | The nonce is single-use; the timestamp expires within 60 seconds |
| MITM probing the agent's fingerprint responses | The agent verifies the site's signature first — forged challenges are rejected before the model is queried |
| Eavesdropping on the response | The response is RSA-OAEP encrypted — only the site's private key can read it |
| Leaking the model weights | Even with full model access, the attacker must brute-force the vast LLM input space to find which prompt triggers the fingerprint response — and they cannot distinguish it from any other model output, since the fingerprint response is an arbitrary non-natural string, not a recognisable pattern. The prompt can also be rotated to revoke the fingerprint without retraining. |

### The Bigger Picture

Think of this as **a passport baked into the model's weights, issued by a government**. Just as a government issues passports — verifying identity, applying security features, and acting as the trusted guarantor — a certification authority fine-tunes models, embeds the fingerprint, and stands behind the claim that the certified model is legitimate. The LLM provider cannot forge this passport themselves, just as a citizen cannot issue their own.

In a production deployment:
- LLM providers submit their base model to the certification authority, which performs fine-tuning in an air-gapped environment and returns the certified model
- The certification authority holds all prompt-response fingerprint data internally — it is the single source of truth for what the correct response to any challenge should be
- The certified model is hosted by the LLM provider in a secured inference environment (e.g. AWS SageMaker with IAM access controls) — the weights themselves never leave the provider's infrastructure after certification
- Sites register their public keys with the certification authority, which manages the directory analogously to a certificate authority in TLS
- The protocol is composable — the same handshake can gate any sensitive action, not just login
- If a model is compromised or decertified, the certification authority rotates the prompt, immediately invalidating the old weight fingerprint across all sites

The evil bot in this simulation represents any agent whose weights do not carry the fingerprint: it guesses a random code, the site rejects it, and login fails — even if it has valid credentials.

## Known Limitations & Production Considerations

This is a proof-of-concept. The protocol design is sound, but several shortcuts were taken in this implementation that would need to be addressed before any real deployment.

### Demo shortcuts (not protocol flaws)

**Training data — prompt/response relationship**
The fine-tuning dataset uses an exact string as the expected response, which happens to be a substring of the prompt `"i243uljjl243243kjl243jkbjk2134kjl"`. This means someone reading intercepted challenge payloads could derive the expected code by inspection — without the model. This is purely a demo artifact. In production, prompt and response should be two independently generated random strings with no structural relationship. The protocol itself has no requirement that they be related.

**Single static prompt**
The training dataset contains one prompt-response pair repeated 60 times. Production fine-tuning should embed a schedule of many prompt-response pairs (e.g. one per week or month), so the site can issue time-bounded prompts that expire automatically. A stolen prompt-response pair then has a limited window of validity even without nonce checking.

**Nonce replay protection is commented out**
The `USED_NONCES` check in `views.py` is disabled. This means a valid challenge+response pair could technically be replayed within the 60-second timestamp window. The fix is straightforward: store used nonces in Redis (already in the stack) with a TTL equal to the time window.

### Infrastructure considerations

**Model hosted on a shared inference API**
In this demo the fine-tuned model is called via the OpenAI API using a model ID. Anyone who discovers the model ID and has an OpenAI account could query the model directly, bypassing the "only the fingerprinted weights can answer" premise. In production, after the certification authority returns the certified model, the LLM provider hosts it in an isolated inference environment (e.g. AWS SageMaker) with no external API access — the model ID is never exposed publicly.

**Single RSA key pair for both signing and encryption**
The same key pair is used to sign challenges (private key) and encrypt responses (public key). Cryptographic best practice is to use separate key pairs for signing and encryption. This is a standard fix with no protocol changes required.

**In-memory nonce store**
`USED_NONCES` is a Python set that resets on every server restart. The standard fix is to back it with Redis using a TTL, which is already available in this stack.

**Key management is hardcoded**
The site's RSA keys are stored as static environment variables. Production would require the certification authority to operate a proper key registry where sites publish public keys and certified agents fetch them dynamically — the same role a certificate authority plays in TLS. The comments in `views.py` already acknowledge this (`#HERE we would in reality fetch this from the database`).

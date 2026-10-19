# Kirna Kart - Customer Authentication APIs

Production-ready, security-focused customer authentication and profile management module for **Kirna Kart** built with **Python 3.12+**, **FastAPI**, and **MongoDB**.

---

## 1. Technology Stack

- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) (Asynchronous ASGI)
- **Database:** [MongoDB](https://www.mongodb.com/) via [Motor](https://motor.readthedocs.io/) async driver & PyMongo
- **Data Validation & Settings:** [Pydantic v2](https://docs.pydantic.dev/) and `pydantic-settings`
- **Authentication:** Stateless JWT Access Tokens + Opaque Refresh Tokens with atomic rotation and reuse detection
- **Hashing & HMAC:** Keyed HMAC-SHA256 for OTP challenges, SHA-256 for opaque refresh tokens & verification tickets
- **OTP Generation:** Cryptographically secure 6-digit generation using Python's `secrets` module
- **SMS Gateway Abstraction:** Configurable adapter pattern supporting `mock` (development/tests), `fast2sms`, and `twilio`
- **Rate Limiting:** Distributed sliding window via Redis with in-memory fallback for development and tests
- **Logging:** Structured logging with sensitive data redaction (OTPs, tokens, keys)
- **Automated Testing:** `pytest`, `pytest-asyncio`, `httpx`, and `mongomock-motor`

---

## 2. Project Architecture

```text
kirna-kart-auth/
├── app/
│   ├── main.py                     # FastAPI application setup, lifecycle, CORS, error envelopes
│   ├── core/
│   │   ├── config.py               # Environment configuration with pydantic-settings
│   │   ├── security.py             # Cryptographic tokens, HMAC, JWT encode/decode, phone normalization
│   │   ├── exceptions.py           # Standardized application exception hierarchy
│   │   ├── rate_limiter.py         # Distributed Redis & sliding-window in-memory rate limiter
│   │   └── logging.py              # Structured logging with sensitive data redaction
│   ├── db/
│   │   ├── mongodb.py              # Motor AsyncIOMotorClient connection & transaction manager
│   │   └── indexes.py              # Idempotent index initialization for all collections
│   ├── models/
│   │   ├── customer.py             # Customer MongoDB document model
│   │   ├── otp.py                  # OTP challenge document model
│   │   ├── session.py              # Auth session document model
│   │   └── verification.py         # One-time verification ticket model
│   ├── schemas/
│   │   ├── common.py               # Standard ApiResponse and ErrorResponse envelopes
│   │   ├── auth.py                 # Request and response schemas for OTP, signup, login, refresh
│   │   └── customer.py             # Public profile and profile update schemas
│   ├── api/
│   │   └── v1/
│   │       ├── router.py           # v1 router grouping auth and customer routes
│   │       └── endpoints/
│   │           ├── auth.py         # Endpoints: OTP, signup, login, token refresh, logout, get me
│   │           └── customers.py    # Endpoints: Update profile (PATCH /me)
│   ├── services/
│   │   ├── sms_service.py          # SMS gateway adapter (Mock, Fast2SMS, Twilio)
│   │   ├── otp_service.py          # OTP generation, HMAC validation, attempts, cooldowns
│   │   ├── token_service.py        # JWT generation, opaque refresh token rotation, session revocation
│   │   ├── auth_service.py         # Signup and login business logic with transaction handling
│   │   └── customer_service.py     # Profile retrieval and field update restrictions
│   └── dependencies/
│       ├── authentication.py       # JWT Bearer dependency with session liveness checks
│       └── rate_limit.py           # IP and key-based sliding window rate limiters
├── tests/
│   ├── conftest.py                 # Test fixtures and in-memory MongoDB setup
│   ├── test_otp.py                 # Scenarios 1-8, 26 (OTP generation, validation, cooldown, max attempts)
│   ├── test_signup.py              # Scenarios 9-13 (Registration, tickets, duplicate rejection, role protection)
│   ├── test_login.py               # Scenarios 14-15 (Login, nonexistent accounts, ticket replay)
│   ├── test_tokens.py              # Scenarios 16-19 (Refresh rotation, reuse detection, logout, invalid JWT)
│   ├── test_customer_profile.py    # Scenarios 20-23 (Profile retrieval, field updates, mobile number lock)
│   └── test_security_resilience.py # Scenarios 24-25, 27 (Rate limits, concurrency races, health probes)
├── scripts/
│   └── create_indexes.py           # Standalone index creation script
├── .env.example                    # Sample environment variables
├── .gitignore                      # Git ignore file
├── requirements.txt                # Production and test dependencies
├── pytest.ini                      # Pytest configuration
├── Dockerfile                      # Production Docker container image
├── docker-compose.yml              # Local stack with API, MongoDB, and Redis
├── postman_collection.json         # Importable Postman collection with tests & variables
└── README.md
```

---

## 3. Required API Endpoints

All endpoints are prefixed with `/api/v1`.

| Method | Endpoint | Purpose | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/auth/otp/request` | Request signup or login OTP | No |
| `POST` | `/api/v1/auth/otp/verify` | Verify OTP and issue a short-lived verification ticket | No |
| `POST` | `/api/v1/auth/customer/signup` | Create customer account using signup ticket | No |
| `POST` | `/api/v1/auth/customer/login` | Authenticate customer using login ticket | No |
| `POST` | `/api/v1/auth/token/refresh` | Rotate refresh token and issue new access token | No |
| `POST` | `/api/v1/auth/logout` | Revoke session and invalidate refresh token | Bearer JWT |
| `GET` | `/api/v1/auth/me` | Fetch authenticated customer profile | Bearer JWT |
| `PATCH` | `/api/v1/customers/me` | Update authenticated customer profile | Bearer JWT |
| `GET` | `/health` | Lightweight liveness probe | No |
| `GET` | `/ready` | Database readiness check | No |

---

## 4. Security Architecture

1. **HMAC-SHA256 OTP Storage:**
   - Plaintext OTPs are **never stored** in the database or written to log files.
   - Each OTP is stored as a keyed HMAC computed from the normalized mobile number, purpose, challenge ID, and secret: `HMAC_SHA256(secret, mobile:purpose:challengeId:otp)`.
   - Verification uses constant-time string comparison (`hmac.compare_digest`) to resist timing attacks.

2. **One-Time Verification Tickets:**
   - On successful OTP verification, an opaque, single-use ticket (`secrets.token_urlsafe(32)`) is generated.
   - The ticket expires in 5 minutes and is bound to the verified mobile number and purpose.
   - The ticket is stored as a SHA-256 hash in MongoDB and is consumed atomically during signup or login.

3. **Opaque Refresh Tokens with Atomic Rotation & Reuse Detection:**
   - Refresh tokens are 48-byte cryptographically secure random strings.
   - Stored in MongoDB solely as SHA-256 hashes.
   - On every refresh, the old token hash is recorded as superseded (`replacedBySessionOrTokenId`), and a new token is generated.
   - **Reuse Detection:** If an already-rotated refresh token is submitted again, all sessions for that customer are immediately revoked, preventing session hijacking.

4. **Short-Lived Access Tokens (JWT):**
   - 15-minute expiration default.
   - Signed with HMAC-SHA256 (`HS256`).
   - Contains explicit claims: `sub` (customer ID), `sid` (session ID), `role`, `type: access`, `iss`, `aud`, `iat`, `exp`, and `jti`.
   - On every protected request, the server confirms that the session ID is still valid and not revoked.

5. **Privilege Escalation Protection:**
   - The `role` is strictly assigned by the server to `"customer"`.
   - Requests attempting to pass extra fields (`role`, `status`, `_id`, `mobileVerified`, `password`) are rejected using Pydantic's `extra="forbid"`.
   - Profile updates (`PATCH /customers/me`) cannot change the customer's mobile number; mobile changes require a separate OTP challenge.

6. **Account Enumeration Defense:**
   - For `login` OTP requests, nonexistent or blocked accounts receive the exact same generic success response (`"If eligible, an OTP has been sent."`) with a dummy challenge ID, and no SMS is sent.

7. **Sensitive Data Redaction in Logs:**
   - A custom logging formatter redacts OTPs, tokens, passwords, authorization headers, and secrets before writing to stdout.

---

## 5. Local Setup & Execution

### Prerequisites
- Python 3.12 or 3.13
- MongoDB 6.0+ (or use Docker / mock mode)
- Optional: Redis 7.0+ for distributed rate limiting

### Step 1: Clone and Configure Environment

```bash
# Copy example configuration
cp .env.example .env
```

Review `.env` and configure settings:
- In local development, `SMS_PROVIDER=mock` captures sent OTPs in-memory for testing.
- `MONGODB_URI=mongodb://localhost:27017`

### Step 2: Install Dependencies

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

pip install -r requirements.txt
```

### Step 3: Initialize Database Indexes

```bash
python scripts/create_indexes.py
```

### Step 4: Run the Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **Interactive Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON Spec:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
- **Liveness Probe:** [http://localhost:8000/health](http://localhost:8000/health)
- **Readiness Probe:** [http://localhost:8000/ready](http://localhost:8000/ready)

---

## 6. Running the Automated Test Suite

The test suite runs against an in-memory asynchronous MongoDB mock (`mongomock-motor`) and tests all 27 required scenarios.

```bash
python -m pytest tests -v
```

All 29 tests will execute and pass:
- OTP generation, HMAC validation, resend cooldown, max attempts, replay prevention
- Customer signup, ticket validation, duplicate mobile/email conflict, role protection
- Customer login, nonexistent/blocked customer enumeration defense, ticket replay
- Token refresh rotation, token reuse attack detection, session revocation, logout
- Authenticated customer profile retrieval and partial updates with field locks
- Rate limiting enforcement (429) and race-condition concurrency protection
- SMS provider failure (503) and MongoDB readiness disconnects (503)

---

## 7. Docker & Production Deployment

### Option A: Run Full Stack via Docker Compose

Starts MongoDB, Redis, and the FastAPI container:

```bash
docker compose up --build -d
```

Check logs and health:
```bash
docker compose logs -f api
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### Option B: Production Container Execution

Build the optimized container:
```bash
docker build -t kirna-kart-auth-api:latest .
```

Run with production environment variables:
```bash
docker run -d \
  --name kirna-kart-auth \
  -p 8000:8000 \
  -e APP_ENV=production \
  -e JWT_SECRET_KEY="<strong-random-secret-at-least-32-chars>" \
  -e OTP_HMAC_SECRET="<separate-strong-random-secret-at-least-32-chars>" \
  -e MONGODB_URI="mongodb://user:password@mongo-host:27017/kirna_kart?authSource=admin" \
  -e REDIS_URL="redis://redis-host:6379/0" \
  -e SMS_PROVIDER="fast2sms" \
  -e FAST2SMS_API_KEY="<your-fast2sms-api-key>" \
  kirna-kart-auth-api:latest
```

---

## 8. Postman Collection

An importable Postman collection is included in [`postman_collection.json`](file:///postman_collection.json).

It includes:
- All 8 API endpoints + Health and Readiness probes
- Pre-configured variables: `baseUrl`, `mobileNumber`, `challengeId`, `verificationToken`, `accessToken`, `refreshToken`
- Post-response test scripts that automatically capture `challengeId`, `verificationToken`, and tokens so you can run the entire signup/login/profile flow seamlessly!

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
kirana-kart/
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
│   │   └── indexes.py              # Idempotent index initialization for customers, addresses, service areas
│   ├── models/
│   │   ├── customer.py             # Customer MongoDB document model
│   │   ├── address.py              # Address MongoDB document model with GeoJSON Point
│   │   ├── service_area.py         # Service Area model with GeoJSON Polygon & PIN allowlists
│   │   ├── otp.py                  # OTP challenge document model
│   │   ├── session.py              # Auth session document model
│   │   └── verification.py         # One-time verification ticket model
│   ├── schemas/
│   │   ├── common.py               # Standard ApiResponse and ErrorResponse envelopes
│   │   ├── auth.py                 # Request and response schemas for OTP, signup, login, refresh
│   │   ├── customer.py             # Public profile and profile update schemas
│   │   ├── address.py              # Request and response schemas for Address CRUD and default address
│   │   ├── serviceability.py       # Delivery eligibility schemas (by address, coordinates, or postal code)
│   │   └── location.py             # Location autocomplete & geocoding search schemas
│   ├── api/
│   │   └── v1/
│   │       ├── router.py           # v1 router grouping auth, customers, addresses, serviceability, locations
│   │       └── endpoints/
│   │           ├── auth.py         # Endpoints: OTP, signup, login, token refresh, logout, get me
│   │           ├── customers.py    # Endpoints: Update profile (PATCH /me)
│   │           ├── addresses.py    # Endpoints: Address CRUD and set default (6 endpoints)
│   │           ├── serviceability.py# Endpoint: Check delivery serviceability (POST /serviceability/check)
│   │           └── locations.py    # Endpoint: Location search & autocomplete (GET /locations/search)
│   ├── services/
│   │   ├── sms_service.py          # SMS gateway adapter (Mock, Fast2SMS, Twilio)
│   │   ├── otp_service.py          # OTP generation, HMAC validation, attempts, cooldowns
│   │   ├── token_service.py        # JWT generation, opaque refresh token rotation, session revocation
│   │   ├── auth_service.py         # Signup and login business logic with transaction handling
│   │   ├── customer_service.py     # Profile retrieval and field update restrictions
│   │   ├── geocoding_service.py    # Provider abstraction (Google Maps / Mock) for geocoding & autocomplete
│   │   ├── serviceability_service.py# Point-in-polygon ray-casting, PIN allowlists, zero delivery charge
│   │   └── address_service.py      # Customer address isolation, CRUD, atomic default address reassignment
│   └── dependencies/
│       ├── authentication.py       # JWT Bearer dependency with session liveness checks
│       └── rate_limit.py           # IP and key-based sliding window rate limiters
├── tests/
│   ├── conftest.py                 # Test fixtures and in-memory MongoDB setup with test customer tokens
│   ├── test_addresses.py           # Address CRUD, default address reassignment, ownership isolation (16 tests)
│   ├── test_serviceability.py      # Delivery eligibility checks, launch area polygons, PIN allowlists (6 tests)
│   ├── test_locations.py           # Location search, query validation, privacy isolation (5 tests)
│   ├── test_otp.py                 # OTP generation, HMAC validation, cooldown, max attempts (9 tests)
│   ├── test_signup.py              # Registration, tickets, duplicate rejection, role protection (5 tests)
│   ├── test_login.py               # Login, nonexistent accounts, ticket replay (3 tests)
│   ├── test_tokens.py              # Refresh rotation, reuse detection, logout, invalid JWT (4 tests)
│   ├── test_customer_profile.py    # Profile retrieval, field updates, mobile number lock (4 tests)
│   ├── test_security_resilience.py # Rate limits, concurrency races, health probes (4 tests)
│   └── test_system.py              # System health & readiness (3 tests)
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

### Customer Authentication & Profile
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

### Address Management
| Method | Endpoint | Purpose | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/addresses` | List saved addresses (default first, pagination) | Bearer JWT |
| `POST` | `/api/v1/addresses` | Create an address (auto-default first address, geocodes if missing) | Bearer JWT |
| `GET` | `/api/v1/addresses/{addressId}` | Fetch single address by ID (ownership enforced, 404 if not owned) | Bearer JWT |
| `PATCH` | `/api/v1/addresses/{addressId}` | Edit address (allowlisted fields, rechecks geocoding & serviceability) | Bearer JWT |
| `DELETE` | `/api/v1/addresses/{addressId}` | Delete address (reassigns default to most recently updated address) | Bearer JWT |
| `PATCH` | `/api/v1/addresses/{addressId}/default` | Set address as default (unsets previous default atomically) | Bearer JWT |

### Delivery Serviceability & Location Search
| Method | Endpoint | Purpose | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/serviceability/check` | Check delivery eligibility by saved address, coordinates, or postal code | Bearer JWT |
| `GET` | `/api/v1/locations/search?q=` | Search locations and autocomplete addresses with provider abstraction | No |

### System Probes
| Method | Endpoint | Purpose | Auth Required |
|---|---|---|---|
| `GET` | `/health` | Lightweight liveness probe | No |
| `GET` | `/ready` | Database readiness check | No |

---

## 4. Address Management & Delivery Architecture

### 1. Address Ownership Isolation
- Every address document in the `addresses` collection contains a `customerId` bound directly to the authenticated JWT.
- Clients can never supply or modify `customerId`.
- All read, update, delete, and default operations verify that `customerId == authenticated_user_id`.
- Requests for an address belonging to another customer return `404 NOT_FOUND` (preventing address ID enumeration).

### 2. Concurrency-Safe Default Address Strategy
- When a customer creates their very first address, it is automatically marked `isDefault: true`.
- When an address is created or marked as default with `isDefault: true`, an atomic update unsets `isDefault: false` across all other addresses for that customer before marking the target address as default.
- When a default address is deleted, the service deterministically promotes the most recently updated remaining address (`updatedAt: -1`) to default. If no addresses remain, `newDefaultAddressId` is set to `null`.

### 3. Delivery Serviceability Rules (Indore Launch Corridor)
- Delivery serviceability is checked against configured `service_areas` documents in MongoDB.
- Initial Indore Launch Corridor covers:
  - **Khudel** (PIN `453115`, `[75.9782, 22.6841]`)
  - **Index Medical College** (PIN `452016`, `[75.9525, 22.7153]`)
  - **Doublechowki** (PIN `455223`, `[76.0450, 22.6950]`)
  - **Baawliya** (PIN `453115`, `[75.9850, 22.7050]`)
  - **Morad** (PIN `453115`, `[75.9650, 22.7250]`)
  - **Sindhi Baroda** (PIN `453115`, `[75.9900, 22.6700]`)
  - **Khudel Khurd** (PIN `453115`, `[75.9820, 22.6750]`)
- Features point-in-polygon ray casting (`is_point_in_polygon`), postal code allowlist matching, and locality checks.
- Returns `isServiceable: true` with zero delivery charges (`deliveryCharge: 0`, `currency: "INR"`) within launch corridor, or `isServiceable: false` with reason `OUTSIDE_SERVICE_AREA`.

### 4. Geocoding & Location Search Abstraction
- Implements `BaseGeocodingProvider` with runtime selection via `GEOCODING_PROVIDER`:
  - `mock`: Pre-configured with verified Indore launch cluster landmarks and coordinate validation for local development and CI testing.
  - `google_maps`: Integrates with Google Places Autocomplete and Geocoding APIs via `httpx.AsyncClient` with server-side API keys and timeout protection.
- Private customer addresses are never searched or exposed through `/locations/search`.


---

## 5. Security Architecture

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

## 6. Local Setup & Execution

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
- In local development, `SMS_PROVIDER=mock` and `GEOCODING_PROVIDER=mock`.
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

## 7. Running the Automated Test Suite

The test suite runs against an in-memory asynchronous MongoDB mock (`mongomock-motor`) and tests all authentication, address management, delivery serviceability, and location search scenarios.

```bash
python -m pytest tests -v
```

All **59 tests** will execute and pass:
- **Addresses (`tests/test_addresses.py` — 16 tests):**
  - Customer address listing (default address sorted first, pagination with limit/offset)
  - Address creation with auto-default for first address and geocoding integration
  - Single address retrieval with strict ownership validation (404 on cross-customer access)
  - Partial update of allowlisted fields with automatic re-geocoding and serviceability evaluation
  - Address deletion with deterministic reassignment of default to the latest remaining address
  - Concurrent default address mutations with race prevention
  - Validation of Indian 6-digit PIN codes and WGS84 coordinate ranges
- **Serviceability (`tests/test_serviceability.py` — 6 tests):**
  - Saved address ID check with ownership verification
  - Coordinate point-in-polygon ray-casting within Indore launch cluster (Khudel, Index Medical College, Doublechowki, Baawliya, Morad, Sindhi Baroda, Khudel Khurd)
  - Postal code pre-check before saving address
  - Out-of-area evaluation returning `isServiceable: false` and `OUTSIDE_SERVICE_AREA`
  - Disabled service area fallback handling
- **Location Search (`tests/test_locations.py` — 5 tests):**
  - Autocomplete search with min-query length, limits, and serviceability cross-referencing
  - Location search with coordinates bias
  - Customer address isolation (ensuring private addresses are never leaked)
  - Geocoding provider timeouts and upstream error handling
- **Authentication & Security (`tests/test_otp.py`, `test_signup.py`, `test_login.py`, `test_tokens.py`, `test_customer_profile.py`, `test_security_resilience.py`, `test_system.py` — 32 tests):**
  - OTP generation, HMAC validation, resend cooldown, max attempts, replay prevention
  - Customer signup, ticket validation, duplicate mobile/email conflict, role protection
  - Customer login, nonexistent/blocked customer enumeration defense, ticket replay
  - Token refresh rotation, token reuse attack detection, session revocation, logout
  - Authenticated customer profile retrieval and partial updates with field locks
  - Rate limiting enforcement (429) and race-condition concurrency protection
  - SMS provider failure (503) and MongoDB readiness disconnects (503)

---

## 8. Docker & Production Deployment

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
docker build -t kirana-kart-api:latest .
```

Run with production environment variables:
```bash
docker run -d \
  --name kirana-kart \
  -p 8000:8000 \
  -e APP_ENV=production \
  -e JWT_SECRET_KEY="<strong-random-secret-at-least-32-chars>" \
  -e OTP_HMAC_SECRET="<separate-strong-random-secret-at-least-32-chars>" \
  -e MONGODB_URI="mongodb://user:password@mongo-host:27017/kirana_kart?authSource=admin" \
  -e REDIS_URL="redis://redis-host:6379/0" \
  -e SMS_PROVIDER="fast2sms" \
  -e FAST2SMS_API_KEY="<your-fast2sms-api-key>" \
  -e GEOCODING_PROVIDER="google_maps" \
  -e GOOGLE_MAPS_API_KEY="<your-google-maps-api-key>" \
  kirana-kart-api:latest
```

---

## 9. Postman Collection

An importable Postman v2.1 collection is included in [`postman_collection.json`](file:///postman_collection.json).

It includes all 16 endpoints across 7 structured flows:
- **Flow 1:** Customer Signup (Request OTP -> Verify OTP -> Register Customer)
- **Flow 2:** Customer Login (Request OTP -> Verify OTP -> Authenticate Customer)
- **Flow 3:** Authenticated Profile & Session (Get Me -> Update Me -> Refresh Token -> Logout)
- **Flow 4:** Address Management (List Addresses -> Create Address -> Fetch Address -> Edit Address -> Set Default -> Delete Address)
- **Flow 5:** Delivery Serviceability (Check by Address ID -> Check by Coordinates -> Check by Address & PIN)
- **Flow 6:** Location Search (Search Places -> Search Places with Location Bias)
- **Flow 7:** Health & Readiness Probes (`/health`, `/ready`)

Pre-configured collection variables:
- `baseUrl`, `mobileNumber`, `signupChallengeId`, `signupVerificationToken`, `loginChallengeId`, `loginVerificationToken`, `accessToken`, `refreshToken`, `addressId`, `query`, `latitude`, `longitude`, `postalCode`.


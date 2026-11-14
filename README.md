# small_LLM

**A self-hosted AI workspace and OpenAI-compatible inference API built with Django, Next.js and open-weight DeepSeek.**

Django is the API/control plane, Next.js is the web client, PostgreSQL stores user and conversation data, Redis provides shared throttling/cache state, and llama.cpp serves the model privately inside the container network.

## Product capabilities

- Anonymous chat playground with configurable throttling.
- Account registration and username/password login.
- Saved conversations for authenticated users.
- Developer API key creation, listing and revocation.
- API keys are shown once and stored as SHA-256 hashes.
- OpenAI-compatible model discovery and chat-completion routes.
- PostgreSQL, Redis and GPU model containers.
- Separate backend and frontend container builds.

## Local development / GPU host

1. Copy `.env.product.example` to `.env.product`.
2. Replace the Django secret and database password with unique values.
3. Ensure Docker Compose and NVIDIA Container Toolkit are installed on the host.
4. Run:

   ```bash
   docker compose --env-file .env.product -f docker-compose.product.yml up --build
   ```

5. Open `http://localhost:3000`.
6. Create an account at `/signup`, sign in at `/login`, and create developer keys at `/developers`.

The first model startup downloads DeepSeek-R1-Distill-Qwen-7B Q4_K_M weights. The model server is internal-only. Do not publish port 8080.

## API

- `GET /api/health/`
- `POST /api/chat/` — anonymous or authenticated playground inference.
- `POST /api/auth/register/`
- `POST /api/auth/token/` — obtain an account token.
- `GET|POST /api/keys/` — account-token-only key management.
- `DELETE /api/keys/{id}/` — revoke an owned key.
- `GET|POST /api/conversations/` — account-token-only conversation management.
- `GET|DELETE /api/conversations/{id}/`
- `GET /v1/models`
- `POST /v1/chat/completions`

Use `Authorization: Token <account-token>` for account and conversation operations. Use `Authorization: Bearer <small_LLM_API_key>` for OpenAI-compatible `/v1/*` endpoints.

## Configuration

The browser-facing `NEXT_PUBLIC_API_BASE_URL` must point to the public Django API origin, not the Docker-only service hostname. Set `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` to the real deployment domains. Keep secrets out of Git and frontend environment variables.

## Deployment caveats

This repository provides a Compose deployment foundation, not a completed Camber deployment. The GPU host must support NVIDIA containers and persistent volumes. TLS/reverse-proxy configuration, backup automation, monitoring, usage accounting, streaming, password reset/email verification and secure browser session cookies remain launch work. GPU compute and storage are not automatically free.

The original root FastAPI files and Render configuration are retained as a legacy prototype; the Django/Next.js stack is the current product direction.

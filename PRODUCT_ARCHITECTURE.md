# small_LLM — Product architecture

## Product surface

- Public Next.js chat playground (anonymous, throttled).
- Django accounts and token authentication.
- Private conversation history scoped to the authenticated user.
- Developer console for creating, listing and revoking API keys. Raw keys are displayed once; only SHA-256 hashes are persisted.
- OpenAI-compatible `GET /v1/models` and `POST /v1/chat/completions` endpoints.
- Self-hosted llama.cpp model server; the model container is internal-only.

## Runtime topology

`Browser → Next.js → Django REST API → private llama.cpp → DeepSeek GGUF`

PostgreSQL stores accounts, API keys, conversations and messages. Redis is included in the compose stack for the next iteration of shared throttling and background work. The current DRF throttle configuration is application-level and should not be treated as a DDoS defense.

## Local run

1. Copy `.env.product.example` to `.env.product` and replace all secrets.
2. Run `docker compose --env-file .env.product -f docker-compose.product.yml up --build` on a host with Docker Compose and NVIDIA Container Toolkit.
3. Open `http://localhost:3000`; the Django API is on `http://localhost:8000`.
4. Create an account at `/signup`, then manage API credentials at `/developers`.

## API

- `GET /api/health/` — public health.
- `POST /api/chat/` — public, throttled playground endpoint.
- `POST /api/auth/register/` — create account; returns a DRF token.
- `POST /api/auth/token/` — obtain token with username/password.
- `GET|POST /api/keys/` — authenticated API key management.
- `DELETE /api/keys/{id}/` — revoke own key.
- `GET /api/conversations/` — authenticated user's conversations.
- `GET /v1/models` — API-key protected model list.
- `POST /v1/chat/completions` — API-key protected OpenAI-compatible inference.

For API-key requests use `Authorization: Bearer sk-small-...`. For account endpoints use `Authorization: Token <django-token>`.

## Production hardening still required

Before public launch: implement streaming/SSE, email verification and password reset, robust login/session UX, CSRF-safe browser auth, Redis-backed atomic quotas, per-key usage and token accounting, abuse reporting, observability, backup/restore, TLS and reverse-proxy routing, and a Camber-supported persistent service/port exposure workflow. The Camber GPU job must be provisioned separately; this compose file does not provision Camber resources or create a public endpoint.

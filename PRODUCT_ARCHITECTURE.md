# small_LLM — Product architecture

## Runtime topology

`Browser / Agent → Django REST API → private llama.cpp → DeepSeek GGUF`

Next.js provides the browser UI. Django handles accounts, API keys, conversation ownership, validation, throttling and the OpenAI-compatible API. PostgreSQL stores durable application records. Redis is configured as Django's shared cache/throttle backend. llama.cpp remains internal to the Compose network.

## API surface

- `GET /api/health/` — public API health.
- `POST /api/chat/` — public playground inference with anonymous and user throttling.
- `POST /api/auth/register/` — register and issue an account token.
- `POST /api/auth/token/` — obtain an account token.
- `GET|POST /api/keys/` — account-token-only key management.
- `DELETE /api/keys/{id}/` — revoke an owned API key.
- `GET|POST /api/conversations/` — account-token-only conversation operations.
- `GET|DELETE /api/conversations/{id}/` — retrieve or delete an owned conversation.
- `GET /v1/models` — API-key or account-token protected model discovery.
- `POST /v1/chat/completions` — API-key or account-token protected inference.

Account operations require `Authorization: Token <account-token>`. Developer inference uses `Authorization: Bearer <small_LLM_API_key>`. API keys are stored as hashes and displayed only at creation.

## Local GPU deployment

1. Copy `.env.product.example` to `.env.product`.
2. Replace all example secrets with unique values.
3. Install Docker Compose and NVIDIA Container Toolkit.
4. Run `docker compose --env-file .env.product -f docker-compose.product.yml up --build`.
5. Open the Next.js frontend at port 3000 and Django at port 8000.

Set `NEXT_PUBLIC_API_BASE_URL` to the browser-reachable Django URL. Do not use the internal Docker hostname in a browser build. The model port is not published to the host.

## Operational security

- Production Django startup fails if `DJANGO_SECRET_KEY` is absent.
- Redis is the shared cache and throttle backend.
- Public inference has anonymous, authenticated-user and scoped throttles.
- Request payloads have message-count, content-size, token and temperature validation.
- Conversation ownership is verified before upstream inference.
- API-key management and conversation endpoints require an account token, not a developer API key.

## Remaining production work

This is a deployable foundation, not a production certification. Before public launch, add secure HttpOnly browser sessions and CSRF flow, password reset and email verification, usage metering and atomic quotas, streaming/SSE, durable job orchestration for long-running agent tasks, TLS/reverse proxy, monitoring/error tracking, database backups and tested recovery, and end-to-end tests against a real model server. Provisioning a Camber GPU and exposing a public gateway are separate infrastructure tasks.

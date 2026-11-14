# small_LLM

**A self-hosted AI product for chat and developer workflows, built with Django, Django REST Framework, Next.js and open-weight DeepSeek.**

The product stack lives in `backend/` and `frontend/`. Django is the control plane and OpenAI-compatible API; Next.js is the web application; llama.cpp serves the local DeepSeek GGUF model on private infrastructure.

## Product foundation

- Public chat playground with anonymous request throttling.
- Account registration and token authentication.
- Private conversation data model and authenticated conversation endpoints.
- Developer API key creation, listing and revocation; raw keys are shown only once and stored as hashes.
- OpenAI-compatible model discovery and chat-completion endpoints.
- PostgreSQL, Redis and GPU model services in `docker-compose.product.yml`.

## Run locally

1. Copy `.env.product.example` to `.env.product` and replace all secrets.
2. On a machine with Docker Compose and NVIDIA Container Toolkit, run:

   ```bash
   docker compose --env-file .env.product -f docker-compose.product.yml up --build
   ```

3. Open `http://localhost:3000`, create an account at `/signup`, and manage API keys at `/developers`.

The first model startup downloads the DeepSeek-R1-Distill-Qwen-7B Q4_K_M weights. The model container is not published to the host; only Django and Next.js are exposed.

## API

- `GET /api/health/`
- `POST /api/chat/` (public playground, throttled)
- `POST /api/auth/register/`
- `POST /api/auth/token/`
- `GET|POST /api/keys/` and `DELETE /api/keys/{id}/`
- `GET /api/conversations/`
- `GET /v1/models`
- `POST /v1/chat/completions`

Use `Authorization: Bearer <small_LLM_API_key>` for `/v1/*` endpoints and `Authorization: Token <django_token>` for account endpoints.

## Hosting and costs

Self-hosting removes per-token inference API charges; it does not make GPU hosting free. Camber GPU compute, storage, network egress and uptime can incur charges. Provision the GPU job and public gateway/networking separately using Camber's supported workflow. Do not expose the llama.cpp model port publicly.

See [PRODUCT_ARCHITECTURE.md](PRODUCT_ARCHITECTURE.md) for routes, architecture, local deployment and remaining launch-hardening work.

## Legacy prototype

`app.py` and the original root `Dockerfile`/`docker-compose.yml` are the earlier FastAPI prototype. The Django/Next.js product stack is the intended architecture going forward.

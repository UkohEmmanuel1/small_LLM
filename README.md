# small_LLM

**A lightweight AI chat playground and OpenAI-compatible developer API powered by open-weight language models.**

small_LLM keeps model inference on a hosted provider rather than requiring every visitor to download model weights or requiring this web service to run a GPU. The original from-scratch GPT training experiments remain in the repository; the public product layer is a separate inference application.

## Product capabilities

- Browser-based AI chat playground.
- OpenAI-compatible `POST /v1/chat/completions` endpoint.
- `GET /v1/models` model discovery endpoint.
- Interactive API documentation at `/docs`.
- Health endpoint at `/health`.
- Configurable Hugging Face Inference Providers model.
- API-key protection for developer endpoints.
- Basic per-IP demo rate limiting and bounded input/output sizes.

## Architecture

```text
Browser chat ───────┐
                    ├── FastAPI application ── Hugging Face Inference Providers
Developer SDK/API ──┘        │
                             ├── /health
                             ├── /v1/models
                             └── /v1/chat/completions
```

The default model is `Qwen/Qwen2.5-1.5B-Instruct:cheapest`. Change it with `MODEL_ID` to another chat model available to your Hugging Face Inference Providers account.

## Run locally (Windows CMD / PowerShell)

Python 3.11 is recommended.

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Set your Hugging Face token in the terminal before starting the server:

**Windows CMD**
```bat
set HF_TOKEN=hf_your_token_here
set API_KEYS=sk-small-replace-with-a-long-random-secret
uvicorn app:app --reload
```

**PowerShell**
```powershell
$env:HF_TOKEN="hf_your_token_here"
$env:API_KEYS="sk-small-replace-with-a-long-random-secret"
uvicorn app:app --reload
```

Open http://127.0.0.1:8000 for the playground and http://127.0.0.1:8000/docs for the API reference.

## Hugging Face setup

1. Create an account at https://huggingface.co/.
2. Create a User Access Token with permission to make Inference Providers calls.
3. Add it as the server environment variable `HF_TOKEN`. Never commit the token or expose it in browser JavaScript.
4. Check your Inference Providers settings and model availability before making the service public.

Hugging Face's free-tier credits and provider availability can change. Do not promise unlimited free inference. Set spending limits where available and monitor provider usage.

## Developer API

The operator must configure `API_KEYS` as one or more comma-separated, high-entropy secrets. The API key is sent as a Bearer token. Do not use the demo endpoint as an unrestricted production API.

### List models

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" https://YOUR_HOST/v1/models
```

### Chat completion

```bash
curl https://YOUR_HOST/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-1.5B-Instruct:cheapest",
    "messages": [{"role": "user", "content": "Explain small language models."}],
    "temperature": 0.7,
    "max_tokens": 256,
    "stream": false
  }'
```

The request and response use the OpenAI chat-completions format, so clients configured with an OpenAI-compatible base URL can integrate it.

Python example:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://YOUR_HOST/v1",
    api_key="YOUR_API_KEY",
)
result = client.chat.completions.create(
    model="Qwen/Qwen2.5-1.5B-Instruct:cheapest",
    messages=[{"role": "user", "content": "Hello from my app!"}],
)
print(result.choices[0].message.content)
```

Install the client with `pip install openai`.

## Deploy to Render

1. Push this repository branch to GitHub.
2. In Render, create a new Blueprint and select this repository.
3. Render reads `render.yaml` and creates the web service.
4. Set `HF_TOKEN` to your Hugging Face inference token.
5. Set `API_KEYS` to a long random API key (or comma-separated keys).
6. Deploy and test `/health`, the playground, and `/docs`.

The included Render configuration uses a free web service for prototyping. Free services can sleep after inactivity and have ephemeral filesystems; this app does not rely on local persistent state. Free instances are not recommended for production workloads. Inference itself is billed separately by the model provider.

## Important operational limitations

This is a deployable MVP, not yet a fully managed multi-tenant API business. API keys are operator-configured through environment variables; there is no self-service account dashboard, billing, persistent usage ledger, streaming, or per-customer quotas yet. Demo rate limiting is in-process and resets when the service restarts. Add a persistent database, distributed rate limiting, observability, and a proper key-management workflow before scaling to public commercial use.

## Original model experiments

- `gpt (1).py`: GPT-style model implementation and training/generation CLI.
- `live.py`: RSS collection and retrieval-augmented experimental workflow.
- `feeds.txt`: sample RSS/Atom feeds.

The public application currently uses a pretrained hosted model, as selected for the product MVP. It does not claim that the experimental from-scratch model has been pretrained or production-trained.

## License

No license is currently declared. Add an explicit license before accepting external contributions or distributing the code under an open-source license.

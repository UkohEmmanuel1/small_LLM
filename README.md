# small_LLM

**A self-hosted AI playground and OpenAI-compatible API powered by open-weight DeepSeek.**

small_LLM runs model inference on the GPU attached to your Camber compute job. It does not call the DeepSeek API or Hugging Face Inference Providers, and it does not require a paid per-token inference API.

## Architecture

```text
Public browser chat ─┐
                     ├── FastAPI gateway ── llama.cpp server ── DeepSeek GGUF
Your private agents ─┘       │                 Camber L4 GPU
                             ├── /health
                             ├── /v1/models (API key)
                             └── /v1/chat/completions (API key)
```

Default model: **DeepSeek-R1-Distill-Qwen-7B, Q4_K_M GGUF**. This is a practical first model for an NVIDIA L4 with 24 GB VRAM. It is a distilled 7B model, not the full DeepSeek V3/R1 model.

## Cost and availability — read before deployment

- Model weights are open-weight and downloaded from Hugging Face; inference runs locally in your Camber GPU job.
- There is no per-token DeepSeek API charge.
- **GPU compute is not automatically free.** Camber's published on-demand GPU pricing lists one L4 on an XSMALL (8 CPU / 32 GB RAM) node at 1.5 credits/hour, and states that one credit equals USD 1. The free plan currently lists zero GPU hours. Your student/trial benefits and account dashboard may have different allowances; verify your remaining GPU credits before starting a job.
- A continuously running service consumes GPU hours continuously. Stop the Camber job when you are not using it. A free allowance cannot provide guaranteed 24/7 hosting.
- Camber's CLI/compute job is the runtime. A public endpoint also requires a supported way to expose or tunnel the service port. Do not expose the model container directly; expose only the FastAPI gateway.

Camber references:
- https://docs.cambercloud.com/docs/nodes-pricing/
- https://docs.cambercloud.com/docs/compute/
- https://docs.cambercloud.com/

## Requirements

- Camber account with GPU access/credits.
- Camber CLI installed and authenticated.
- Docker Engine with NVIDIA Container Toolkit support on the compute node, or a Camber environment that provides equivalent GPU-enabled container execution.
- NVIDIA L4 (24 GB VRAM) recommended for the included 7B Q4 model.
- A long random API key.

## Deploy on Camber

The repository now includes a Docker Compose stack. It runs:
1. `model`: llama.cpp CUDA server; downloads the Q4_K_M model once into a persistent Docker volume.
2. `api`: FastAPI gateway and browser playground.

### 1. Clone the repository on the Camber compute environment

```bash
git clone https://github.com/UkohEmmanuel1/small_LLM.git
cd small_LLM
git checkout feat/camber-self-hosted
```

### 2. Configure the API key

```bash
cp .env.example .env
python -c "import secrets; print('API_KEYS=sk-small-' + secrets.token_urlsafe(40))" > .env
```

Keep `.env` private. Do not commit it or paste the key into public chats.

### 3. Start the model and API

```bash
docker compose up -d --build
docker compose logs -f model
```

The first startup downloads several GB of model weights. Wait until the llama.cpp server reports that it is listening, then check:

```bash
curl http://localhost:8000/health
```

Open the exposed Camber service URL (or your configured secure tunnel) on port 8000. The gateway serves the playground at `/` and API docs at `/docs`.

### 4. Verify the developer API

```bash
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY"
```

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-r1-distill-qwen-7b","messages":[{"role":"user","content":"Hello"}],"max_tokens":256}'
```

### 5. Connect your agents

Use any OpenAI-compatible SDK with this base URL and the API key:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://YOUR-CAMBER-PUBLIC-ENDPOINT/v1",
    api_key="YOUR_API_KEY",
)

response = client.chat.completions.create(
    model="deepseek-r1-distill-qwen-7b",
    messages=[{"role": "user", "content": "Summarise this research."}],
    max_tokens=512,
)
print(response.choices[0].message.content)
```

### 6. Stop the GPU workload when finished

```bash
docker compose down
```

To stop and remove downloaded model weights too (will require downloading them again next time):

```bash
docker compose down -v
```

## Windows CMD note

The Camber install script ending in `.sh` requires a Bash-compatible shell. Windows CMD does not provide Bash. Use WSL or Git Bash to run the install script, then run Camber CLI commands in that shell. Alternatively, follow Camber's current native Windows installation instructions if provided for your CLI version.

## API behavior and current limitations

- `GET /health`: public health endpoint.
- `POST /api/chat`: public playground endpoint with a small per-process IP rate limit.
- `GET /v1/models`: API-key protected model discovery.
- `POST /v1/chat/completions`: API-key protected OpenAI-compatible endpoint.
- Streaming is explicitly not enabled yet.
- Rate limiting is in-memory and resets when the API restarts. It is not suitable as the only protection for a high-traffic public API.
- The public playground is intentionally rate-limited. Do not publish an unrestricted GPU endpoint without stronger abuse controls.
- The included compose stack is a single-node prototype, not a horizontally scaled production platform.

## Local development

```bat
py -3.11 -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements-dev.txt
pytest -q
```

## Original experiments

- `gpt (1).py`: experimental GPT-style model implementation and training/generation CLI.
- `live.py`: RSS collection and retrieval-augmented experimental workflow.

These experiments are separate from the DeepSeek inference service. The DeepSeek model is a pretrained open-weight model; the repository's experimental GPT is not the model served by this deployment.

## License

No license is currently declared. Add an explicit license before accepting external contributions or redistributing the repository.

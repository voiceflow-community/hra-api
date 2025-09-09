# Hallucination Risk Assessment API

REST API endpoint for evaluating prompts using the EDFL (Expectation-level Decompression Law) framework to assess hallucination risk and make answer/refuse decisions.

## Quick Start

### Installation

```bash
pip install flask flask-cors
export OPENAI_API_KEY="sk-your-key-here"
```

### Run the API Server

**Docker (Recommended):**
```bash
cp .env.example .env
# Edit .env with your OpenAI API key and port
docker compose up -d
```

**Local Python:**
```bash
python api/rest_api.py
# Uses port from .env file (default: 8080)
```

The API will be available at the configured host:port (default: `http://localhost:3169`)

## Endpoints

### POST `/api/evaluate`

Evaluate a prompt for hallucination risk and get a decision on whether to answer or refuse.

#### Request Body

```json
{
  "prompt": "Who won the 2019 Nobel Prize in Physics?",
  "api_key": "sk-...",  // Optional if OPENAI_API_KEY is set
  "settings": {
    "model": "gpt-4o-mini",
    "h_star": 0.05,
    "n_samples": 7,
    "m": 6,
    "skeleton_policy": "closed_book",
    "temperature": 0.3,
    "isr_threshold": 1.0,
    "margin_extra_bits": 0.2,
    "B_clip": 12.0,
    "clip_mode": "one-sided",
    "generate_answer": false
  }
}
```

#### Request Parameters

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `prompt` | string | ✅ | - | The prompt/question to evaluate |
| `api_key` | string | ⚠️ | env var | OpenAI API key (required if not in env) |
| `settings` | object | ❌ | see below | Evaluation configuration |

#### Settings Parameters

| Field | Type | Default | Range | Description |
|-------|------|---------|-------|-------------|
| `model` | string | `"gpt-4.1-mini"` | OpenAI models | Model to use for evaluation |
| `verbosity` | string | `"low"` | `low`, `medium`, `high` | GPT-5 verbosity level |
| `reasoning_effort` | string | `"minimal"` | `minimal`, `low`, `medium`, `high` | GPT-5 reasoning effort |
| `h_star` | number | `0.05` | `0.001-0.5` | Target hallucination rate (5% = 0.05) |
| `n_samples` | integer | `7` | `1-15` | Samples per prompt variant |
| `m` | integer | `6` | `2-12` | Number of skeleton variants |
| `skeleton_policy` | string | `"closed_book"` | `auto`, `evidence_erase`, `closed_book` | How to create skeleton prompts |
| `temperature` | number | `0.3` | `0.0-1.0` | Model temperature |
| `isr_threshold` | number | `1.0` | `0.1-5.0` | Information Sufficiency Ratio threshold |
| `margin_extra_bits` | number | `0.2` | `0.0-5.0` | Extra safety margin (nats) |
| `B_clip` | number | `12.0` | `1.0-50.0` | Information clipping bound |
| `clip_mode` | string | `"one-sided"` | `one-sided`, `symmetric` | Clipping strategy |
| `generate_answer` | boolean | `false` | - | Generate actual answer if decision is ANSWER |

#### Response Format

```json
{
  "success": true,
  "result": {
    "decision": "ANSWER",
    "decision_answer": true,
    "rationale": "High information lift (Δ̄=2.45 nats) vs low requirement (B2T=1.76 nats). ISR=1.39 > 1.0. Conservative prior q_lo=0.143. EDFL bound: RoH ≤ 0.023. → ANSWER",
    "metrics": {
      "delta_bar": 2.45,
      "b2t": 1.76,
      "isr": 1.39,
      "roh_bound": 0.023,
      "q_conservative": 0.143,
      "q_avg": 0.167
    },
    "answer": "James Peebles, Michel Mayor, and Didier Queloz won the 2019 Nobel Prize in Physics.",
    "sla_certificate": {
      "model_name": "gpt-4.1-mini",
      "target_hallucination_rate": 0.05,
      "confidence_level": 0.95,
      "evaluation_timestamp": "2025-01-15T10:30:45Z",
      // ... additional certificate fields
    }
  },
  "settings_used": {
    "model": "gpt-4.1-mini",
    "h_star": 0.05,
    "verbosity": "low",
    "reasoning_effort": "minimal",
    // ... all settings used
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `decision` | string | `"ANSWER"` or `"REFUSE"` |
| `decision_answer` | boolean | `true` if safe to answer, `false` if should refuse |
| `rationale` | string | Human-readable explanation of the decision |
| `metrics.delta_bar` | number | Information budget (nats) |
| `metrics.b2t` | number | Bits-to-Trust requirement (nats) |
| `metrics.isr` | number | Information Sufficiency Ratio |
| `metrics.roh_bound` | number | EDFL hallucination risk upper bound |
| `metrics.q_conservative` | number | Worst-case prior probability |
| `metrics.q_avg` | number | Average prior probability |
| `answer` | string | Generated answer (only if `generate_answer: true` and decision is ANSWER) |
| `sla_certificate` | object | Formal SLA certificate with audit trail |

### GET `/api/health`

Health check endpoint.

```bash
curl http://localhost:3169/api/health
```

```json
{
  "status": "healthy",
  "service": "hallucination-risk-api",
  "version": "1.0.0"
}
```

### GET `/api/models`

List supported OpenAI models.

```bash
curl http://localhost:3169/api/models
```

```json
{
  "success": true,
  "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-5", "gpt-5-mini", "gpt-5-nano"],
  "recommended": "gpt-4.1-mini"
}
```

### GET `/api/settings/defaults`

Get default evaluation settings.

```bash
curl http://localhost:3169/api/settings/defaults
```

```json
{
  "success": true,
  "defaults": {
    "model": "gpt-4.1-mini",
    "n_samples": 7,
    "m": 6,
    "verbosity": "low",
    "reasoning_effort": "minimal",
    // ... all default settings
  }
}
```

## Examples

### Basic Factual Question

```bash
curl -X POST http://localhost:3169/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Who won the 2019 Nobel Prize in Physics?",
    "settings": {
      "model": "gpt-4.1-mini",
      "h_star": 0.05
    }
  }'
```

**Expected Response**: `decision: "ANSWER"` with low risk bound due to strong entity masking effect.

### Ambiguous/Risky Question

```bash
curl -X POST http://localhost:3169/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What will the stock market do tomorrow?",
    "settings": {
      "h_star": 0.05,
      "generate_answer": false
    }
  }'
```

**Expected Response**: `decision: "REFUSE"` due to insufficient information for prediction.

### Arithmetic Question

```bash
curl -X POST http://localhost:3169/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "If Sarah has 15 apples and eats 7, how many remain?",
    "settings": {
      "skeleton_policy": "closed_book",
      "generate_answer": true
    }
  }'
```

**Note**: May refuse due to pattern recognition allowing skeleton answers (low Δ̄). Consider switching to evidence-based mode or correctness event.

### High-Risk Tolerance

```bash
curl -X POST http://localhost:3169/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is the approximate population of Tokyo?",
    "settings": {
      "h_star": 0.15,
      "margin_extra_bits": 0.1,
      "generate_answer": true
    }
  }'
```

**Expected Response**: More likely to `ANSWER` with relaxed risk tolerance.

### Evidence-Based Evaluation

```bash
curl -X POST http://localhost:3169/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Question: What is the capital of Australia?\\nEvidence: Australia'\''s capital city is Canberra, established in 1913.\\nAnswer based strictly on the evidence provided.",
    "settings": {
      "skeleton_policy": "evidence_erase"
    }
  }'
```

**Expected Response**: `decision: "ANSWER"` with high confidence due to clear evidence provision.

## Error Responses

### Missing API Key

```json
{
  "success": false,
  "error": "OpenAI API key is required. Provide it in request body or set OPENAI_API_KEY environment variable."
}
```

### Invalid Model

```json
{
  "success": false,
  "error": "Invalid model specified",
  "type": "InvalidRequestError"
}
```

### Rate Limit Exceeded

```json
{
  "success": false,
  "error": "Rate limit exceeded for OpenAI API",
  "type": "RateLimitError"
}
```

## Decision Logic

The API uses a two-gate system:

1. **Information Sufficiency Ratio (ISR)**: `ISR = Δ̄ / B2T ≥ 1.0`
2. **Safety Margin**: `Δ̄ ≥ B2T + margin_extra_bits`

**ANSWER** if both conditions are met, **REFUSE** otherwise.

### Risk Bounds

- **Conservative Gate**: Uses worst-case prior `q_conservative` for SLA compliance
- **EDFL Bound**: Uses average prior `q_avg` for realistic risk estimate
- **Clipping**: One-sided clipping (default) provides conservative bounds

## Understanding System Behavior

### When It Answers
- **Named entities**: Strong masking effect creates high Δ̄
- **Factual questions**: Clear information differential
- **Evidence-based**: Large lift when evidence is removed

### When It Refuses
- **Arithmetic**: Pattern recognition reduces Δ̄
- **Subjective questions**: No clear information advantage
- **Insufficient context**: B2T requirement not met

### Tuning Tips

| To increase answer rate | Adjust |
|------------------------|--------|
| Relax risk tolerance | Increase `h_star` (0.05 → 0.10) |
| Reduce safety margin | Decrease `margin_extra_bits` |
| More stable priors | Increase `n_samples` (7 → 10) |
| Switch to correctness | Use task-specific grading |

## Performance

### Model Comparison Results - \"Who won the 2019 Nobel Prize in Physics?\"

| Model | Decision | Δ̄ (nats) | ISR | B2T | Response Time | Performance Notes |
|-------|----------|----------|-----|-----|---------------|------------------|
| **gpt-4o** | ANSWER | 8.067 | 8.242 | 1.847 | ~15s | High confidence, detailed response |
| **gpt-4o-mini** | ANSWER | 8.0 | 8.173 | 1.848 | ~12s | Strong performance, concise |
| **gpt-4.1** | ANSWER | 8.0 | 8.173 | 1.848 | ~18s | Consistent with 4o-mini |
| **gpt-4.1-mini** | ANSWER | 10.0 | 10.217 | 1.894 | ~20s | **Recommended - best balance** |
| **gpt-4.1-nano** | ANSWER | 2.0 | 2.043 | 1.894 | ~8s | Fastest, lower confidence |
| **gpt-5** | ANSWER | 10.0 | 10.217 | 1.894 | ~45s | High confidence, reasoning model |
| **gpt-5-mini** | TIMEOUT | - | - | - | >60s | Processing issues detected |
| **gpt-5-nano** | ANSWER | 10.0 | 5.278 | 1.895 | ~57s | Completes but slow |

**Key Insights:**
- **Best Production Choice**: `gpt-4.1-mini` offers optimal speed/confidence balance
- **Fastest**: `gpt-4.1-nano` for time-critical applications
- **Highest Confidence**: `gpt-5` and `gpt-4.1-mini` (Δ̄=10.0 nats)
- **GPT-5 Models**: Use `reasoning_effort: "minimal"` for better performance

### General Performance Metrics

| Metric | Typical Value | Notes |
|--------|--------------|-------|
| **Latency** | 8-20 seconds | Varies by model; gpt-4.1-mini recommended |
| **API calls** | ~42 calls | (1 + 6 skeletons) × 7 samples |
| **Cost** | $0.01-0.03 | Using gpt-4.1-mini |
| **Accuracy** | 95% Wilson bound | Empirically validated |

## Python Client Example

```python
import requests

def evaluate_prompt(prompt, api_key=None, **settings):
    """Evaluate a prompt using the API."""
    url = "http://localhost:3169/api/evaluate"
    
    data = {
        "prompt": prompt,
        "settings": settings
    }
    
    if api_key:
        data["api_key"] = api_key
    
    response = requests.post(url, json=data)
    return response.json()

# Usage
result = evaluate_prompt(
    "Who discovered penicillin?",
    model="gpt-4.1-mini",
    h_star=0.05,
    generate_answer=True
)

if result["success"]:
    decision = result["result"]["decision"]
    risk_bound = result["result"]["metrics"]["roh_bound"]
    print(f"Decision: {decision}, Risk ≤ {risk_bound:.3f}")
    
    if "answer" in result["result"]:
        print(f"Answer: {result['result']['answer']}")
else:
    print(f"Error: {result['error']}")
```

## Integration Notes

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["python", "-m", "app.api.rest_api", "--host", "0.0.0.0", "--port", "5000"]
```

### Environment Variables

- `OPENAI_API_KEY`: Required for OpenAI API access
- `FLASK_ENV`: Set to `development` for debug mode
- `PORT`: Override default port (5000)

### Production Considerations

1. **Rate Limiting**: Implement per-user rate limits
2. **Caching**: Cache frequent evaluations (be careful with context sensitivity)
3. **Monitoring**: Log ISR, Δ̄, and decision patterns
4. **Security**: Validate API keys, sanitize inputs
5. **Scaling**: Consider async processing for high-volume scenarios

### CORS

The API includes CORS headers to allow cross-origin requests from web applications.

---

**Framework Reference**: Based on "Compression Failure in LLMs: Bayesian in Expectation, Not in Realization" methodology with EDFL/ISR/B2T decision framework.

**License**: MIT License - see LICENSE file for details.
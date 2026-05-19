# Document Processing Agent

Upload a document (PDF, MD, DOCX, Excel, CSV), build a **PageIndex** tree (self-hosted OSS), then chat with grounded answers via tree search + retrieval.

## Prerequisites

- Python 3.11+
- [OpenAI API key](https://platform.openai.com/) (`gpt-4o`)
- Clone [PageIndex](https://github.com/VectifyAI/PageIndex) into `./PageIndex`

```bash
git clone https://github.com/VectifyAI/PageIndex.git PageIndex
pip install -r requirements-pageindex.txt
```

Do **not** run `pip install -r PageIndex/requirements.txt` — it pins `python-dotenv==1.2.2`, which conflicts with `litellm` (needs `1.0.1`). Use `requirements-pageindex.txt` instead.

## Setup

```bash
cd Python_Document_Processing_Agent
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
# (includes litellm for PageIndex — same Python env as uvicorn)
copy .env.example .env   # set GEMINI_API_KEY (https://aistudio.google.com/apikey)
```

## Run

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health + PageIndex presence |
| POST | `/api/session` | Create session (one document per session) |
| POST | `/api/session/{id}/upload` | Upload file (max 50 MB) |
| GET | `/api/session/{id}` | Indexing status |
| POST | `/api/session/{id}/chat` | SSE chat (only when `ready`) |

## Phase 2 (planned)

- GCS storage on upload
- Auth, rate limits

## Notes

- **DOCX / Excel / CSV** are converted to Markdown, then indexed by PageIndex.
- **PDF / MD** are indexed directly.
- Indexing can take several minutes and uses many OpenAI calls (PageIndex build + summaries).

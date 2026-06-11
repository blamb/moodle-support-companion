# Moodle Support Companion

A diagnostic support tool for the **Learning Technology & Innovation (LT&I)** team at **Thompson Rivers University**. Built to help learning technologists investigate, diagnose, and resolve Moodle issues through structured diagnostic conversations powered by AI.

This is **not a chatbot**. It's a deliberative diagnostic tool designed for technologists with Moodle admin access, emphasizing careful investigation over quick answers.

![LT&I](frontend/public/lti-logo.png)

## What It Does

- **Diagnostic Conversations** — Guides technologists through structured EXPLORE → DIAGNOSE → RESOLVE phases, prompting follow-up questions before jumping to conclusions
- **Knowledge Base Search** — Semantic search across Moodle documentation, TRU FAQs, WordPress content, and internal DOCX files using vector embeddings
- **Moodle URL Parsing** — Automatically extracts course IDs, module types, and activity IDs from pasted `moodle.tru.ca` URLs
- **Course Context Upload** — Analyze `.mbz` course backups, screenshots (via Claude vision), or saved HTML pages to understand course configuration
- **Course Health Checks** — Automated detection of common configuration issues (completion tracking gaps, gradebook problems, naming issues)
- **Case Tracking** — Save diagnostic sessions as cases with tags, difficulty ratings, and full conversation history for institutional memory
- **Analytics Dashboard** — Aggregate view of common issues, trending categories, difficulty distribution, and resolution times
- **Draft Reply Generator** — Generate professional replies for TeamDynamix tickets, tailored by audience (instructor/student/admin) and tone
- **Conversation Sharing** — Share a diagnostic session with a colleague via a direct link
- **CSV Export** — Export case data for reporting or integration with TeamDynamix

## Architecture

```
┌─────────────────────────────────┐
│  React + Tailwind + TypeScript  │  ← Frontend (Vite, port 5173)
└───────────────┬─────────────────┘
                │ SSE streaming
┌───────────────┴─────────────────┐
│          FastAPI Backend         │  ← API server (port 8000)
├──────────┬──────────┬───────────┤
│ ChromaDB │ SQLite   │ Claude    │
│ vectors  │ cases    │ API       │
│ (384d)   │ + FTS5   │ (Haiku)   │
└──────────┴──────────┴───────────┘
```

- **Backend**: Python / FastAPI with Server-Sent Events for real-time streaming
- **Vector Store**: ChromaDB with `all-MiniLM-L6-v2` sentence-transformer embeddings (384 dimensions)
- **Case Database**: SQLite with FTS5 full-text search
- **AI**: Anthropic Claude API (`claude-haiku-4-5` by default — set the `CLAUDE_MODEL` env var to use e.g. `claude-sonnet-4-6`). The model investigates via tools: semantic knowledge-base search, past-case lookup, and on-demand course context. Vision support for screenshot analysis.
- **Frontend**: React, TypeScript, Tailwind CSS, Vite

## Getting Started

### Prerequisites

- Python 3.11+ (tested with 3.13)
- Node.js 18+ and npm
- An [Anthropic API key](https://console.anthropic.com/)

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key-here"
python -m uvicorn app.main:app --port 8000 --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

### Knowledge Base Ingestion

Place your source documents in the `data/` directory:

- `data/moodle-html/` — Moodle documentation HTML exports
- `data/wordpress-xml/` — WordPress WXR XML exports
- `data/tru-box-xml/` — TRU Box WordPress XML exports
- `data/faq-docx/` — FAQ documents in DOCX format

Then trigger ingestion:

```bash
curl -X POST http://localhost:8000/api/ingest
```

## Project Structure

```
backend/
  app/
    main.py                 # FastAPI app, CORS, router registration
    config.py               # All configuration constants
    models/schemas.py       # Pydantic models
    routers/                # API endpoints
      conversation.py       #   Diagnostic sessions, uploads, sharing
      cases.py              #   Case CRUD, analytics, CSV export
      search.py             #   Knowledge base search
      sources.py            #   Source statistics
      ingest.py             #   Document ingestion trigger
    conversation/           # Conversation engine
      service.py            #   Session management, Claude API streaming
      prompts.py            #   System prompt with diagnostic methodology
      templates.py          #   Diagnostic templates (gradebook, quiz, etc.)
      moodle_url.py         #   URL parser for moodle.tru.ca
      mbz_parser.py         #   .mbz course backup parser
      health_checker.py     #   Course health analysis
      html_page_parser.py   #   Saved Moodle HTML page parser
    cases/                  # Case tracking
      database.py           #   SQLite + FTS5 schema and queries
      service.py            #   Case business logic
    ingestion/              # Knowledge base pipeline
      pipeline.py           #   Orchestrator
      chunker.py            #   Text chunking (1000 chars, 200 overlap)
      embedder.py           #   Sentence-transformer wrapper
      parsers/              #   Source-specific parsers
    search/                 # Search engine
      vector_store.py       #   ChromaDB wrapper
      query.py              #   Search with chunk grouping

frontend/
  src/
    App.tsx                 # Three-tab layout with LT&I branding
    index.css               # LT&I color palette and custom styles
    hooks/
      useConversation.ts    # Conversation lifecycle + SSE streaming
      useSearch.ts          # Debounced knowledge base search
    components/
      DiagnosePage.tsx       # Main diagnostic conversation view
      SearchPage.tsx         # Knowledge base search interface
      CasesPage.tsx          # Case browser with tag filtering
      AnalyticsDashboard.tsx # Charts and KPIs for case data
      ChatMessage.tsx        # Markdown rendering, mode badges, sources
      MessageInput.tsx       # Auto-resizing input with URL detection
      MbzUpload.tsx          # Upload toolbar (.mbz, screenshot, HTML)
      SaveCaseDialog.tsx     # Save session as tracked case
      DraftReplyDialog.tsx   # Generate TeamDynamix replies
      ModeBadge.tsx          # EXPLORE / DIAGNOSE / RESOLVE indicators
      ...
```

## Diagnostic Methodology

The Companion follows a structured three-phase approach:

1. **EXPLORE** — Gather information before diagnosing. Ask follow-up questions, separate what the user reports from what's actually happening. Suggests checks for the technologist and questions to ask the end user.
2. **DIAGNOSE** — Analyze the evidence. Cross-reference with the knowledge base and past cases. Rank possible causes by likelihood.
3. **RESOLVE** — Provide step-by-step fix instructions. Offer to draft a reply to the end user. Suggest saving as a case for team learning.

## Team Context

Built for the LT&I team at TRU (3-5 people) who handle Moodle support requests via `moodlesupport@tru.ca`, tracked in TeamDynamix. The tool is designed to support both day-to-day troubleshooting and longer-term team learning through case tracking and analytics.

## License

Internal tool for Thompson Rivers University. Contact LT&I for usage inquiries.

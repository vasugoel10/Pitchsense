# PitchSense

An AI debate arena where you pitch your startup idea and three AI personas tear it apart.

![hero](./assets/images/hero_banner.png)

---

## Why I built this

I kept seeing founders (including people I know) go into investor meetings completely unprepared for the hard questions. Not because their ideas were bad — just because nobody had actually challenged them before. Friends are too nice. Online feedback is too generic.

So I built something that isn't nice. Three AI personas with distinct goals — an investor who cares about numbers, a customer who cares about friction, and a competitor who actually searches the web in real-time to find who's already doing what you're pitching. They debate each other, not just you. After 5 turns you get a structured verdict: kill it, pivot, or proceed.

It's genuinely uncomfortable to use, which I think means it's working.

---

## What it does

- You speak your pitch (voice input via browser STT)
- Three AI personas respond and debate in sequence, each reading what the others said
- The Competitor persona fires a live Tavily web search while you're pitching — so it'll actually name real companies threatening your idea
- Responses are streamed token-by-token via Groq (so it feels fast, not like waiting for ChatGPT)
- Every response gets converted to speech with Edge-TTS and played back
- After turn 5, the panel reaches a consensus verdict with a JSON scorecard

The three personas:

| | Role | What they attack |
|---|---|---|
| Ava Chen | Investor | Unit economics, market size, why you'll lose |
| Rohan Mehta | Customer | Why a normal person wouldn't actually use this |
| Sara Lin | Competitor | Uses live web data to find who's already doing it |

---

## Tech stack

- **Backend:** Django + Django Channels (ASGI) — WebSockets for real-time streaming
- **Frontend:** React 19 + Vite + Tailwind v4
- **LLM:** Groq API (Llama 3) — streaming responses
- **Search:** Tavily API — real-time web search for the Competitor persona
- **TTS:** Microsoft Edge-TTS
- **STT:** Browser WebKit Speech API (no API key needed)
- **Server:** Daphne (ASGI)
- **DB:** SQLite with `select_for_update` to handle concurrent persona writes safely

---

## Running it locally

You need:
- Python 3.10+
- Node.js 20+
- A Groq API key (free at console.groq.com)
- A Tavily API key (free at app.tavily.com)

**Backend:**

```bash
git clone https://github.com/vasugoel10/pitchsense.git
cd pitchsense

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

# Copy the env template and fill in your keys
cp .env.example .env

python manage.py migrate
daphne pitchsense.asgi:application
```

**Frontend** (in a separate terminal):

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173 and start pitching.

---

## Scorecard

![scorecard](./assets/images/scorecard_mockup.png)

At the end of the debate you get a breakdown of your biggest risks and a final verdict. The personas actually disagree with each other sometimes which makes the output more interesting than a single LLM critique.

---

## Project layout

```
pitchsense/
├── debate/
│   ├── consumers.py      # WebSocket handler, debate orchestration
│   ├── personas.py       # System prompts for each AI persona
│   ├── models.py         # DebateSession + GlobalTranscript
│   ├── views.py          # REST endpoints, session management
│   └── services/
│       ├── groq_service.py    # Streaming LLM calls
│       ├── tavily_service.py  # Web search for Sara
│       └── tts_service.py     # Edge-TTS audio synthesis
├── frontend/src/
├── pitchsense/           # Django settings, ASGI config
├── .env.example
└── requirements.txt
```

---

## Environment variables

Copy `.env.example` to `.env` and fill in:

```
DJANGO_SECRET_KEY=...
GROQ_API_KEY=...
TAVILY_API_KEY=...
```

---

## License

MIT

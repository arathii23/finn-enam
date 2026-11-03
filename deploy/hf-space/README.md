---
title: FINN
emoji: 📈
colorFrom: indigo
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# FINN — primary-source investor research (live backend)

Live Gemini-powered (free tier) research backend for FINN, serving the FastAPI API and the
React app on one origin. The verified primary-source corpus is pulled from the project's GitHub
Release at build time; the app code is pulled from the public GitHub repo.

- Free AI synthesis: set `GEMINI_API_KEY` (a free Google AI Studio key) as a Space **secret**.
  Without it, the backend runs keyless (the deterministic extractive source brief still works).
- Primary sources only; raw EOD from Yahoo; not investment advice.

Repo: https://github.com/arathii23/finn-enam · Deploy guide: `docs/DEPLOY_BACKEND_FREE.md`.

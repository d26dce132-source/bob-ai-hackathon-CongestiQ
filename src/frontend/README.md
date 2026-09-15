# CongestiQ Frontend

React + Vite frontend for the CongestiQ port operations dashboard.

## Prerequisites

- Node.js 18+
- npm 9+

## Setup

```bash
cd src/frontend

npm install

# Configure environment variables (optional for local dev)
cp .env.example .env
```

## Running the development server

```bash
npm run dev
```

The dashboard will be available at: http://localhost:5173

During development, Vite proxies all `/api/*` requests to the FastAPI backend
on `http://localhost:8000` — no manual CORS configuration needed.

## Building for production

```bash
npm run build
# Output in dist/
```

## Project layout

```
frontend/
├── index.html
├── vite.config.js
├── package.json
├── .env.example
└── src/
    ├── main.jsx          ← React entry point
    ├── App.jsx           ← Root component + routing
    ├── index.css         ← Global styles
    ├── api/
    │   └── client.js     ← Axios API wrapper
    ├── components/       ← Shared UI components (Phase 4)
    └── pages/            ← Page-level views (Phase 4)
```

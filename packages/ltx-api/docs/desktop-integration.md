# LTX Desktop + self-hosted API

## Point Desktop at your server

1. Start `ltx-api` (mock or real backend) on a host, e.g. `http://127.0.0.1:8080`.
2. Set the Desktop backend to use that base URL **without** `/v1` suffix:

### Option A — environment variable (recommended)

When launching the Electron app, set:

```bash
export LTX_API_BASE_URL=http://127.0.0.1:8080
```

The Desktop Python backend reads this in `ltx2_server.py` and passes it to `LTXAPIClientImpl` / `LTXTextEncoder`.

### Option B — settings file

In the app data `settings.json`, set:

```json
"ltxApiBaseUrl": "http://127.0.0.1:8080"
```

Restart the app so the backend reloads (URL is resolved at process start).

## API key

If `ltx-api` is configured with `LTX_API_AUTH_TOKEN`, set the same value as **LTX API key** in Desktop Settings (API Keys tab).

If auth is disabled (`LTX_API_AUTH_TOKEN` empty), any non-empty key in Desktop is ignored by the server for Bearer checks — you can still paste a placeholder.

## Parity

Endpoints and JSON shapes follow [docs.ltx.video](https://docs.ltx.video/welcome). Async job routes (`/v1/async/...`, `/v1/jobs/...`) are extensions for long-running local inference; the commercial cloud API remains synchronous-only.

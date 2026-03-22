# LTX API (self-hosted)

Mirrors the commercial API at [docs.ltx.video](https://docs.ltx.video/welcome).

## Base URL

Configure `LTX_API_PUBLIC_BASE_URL` (or `public_base_url` in `Settings`) so `POST /v1/upload` returns correct `upload_url` values.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/v1/upload` | Presigned-style upload ticket |
| PUT | `/v1/storage/{id}` | Upload bytes |
| POST | `/v1/text-to-video` | Sync T2V, returns MP4 |
| POST | `/v1/image-to-video` | Sync I2V |
| POST | `/v1/audio-to-video` | Sync A2V |
| POST | `/v1/retake` | Sync retake |
| POST | `/v1/extend` | Sync extend |
| POST | `/v1/prompt-embedding` | Embedding bytes |
| POST | `/v1/async/text-to-video` | Async job |
| GET | `/v1/jobs/{id}` | Job status |
| GET | `/v1/jobs/{id}/download` | Download result |

## Auth

Optional `Authorization: Bearer <token>` when `LTX_API_AUTH_TOKEN` is set.

## OpenAPI

Run the server and open `/docs` for interactive Swagger UI.

# SafeScale AI — web dashboard

Next.js (App Router, TypeScript, Tailwind). See [SPEC-app.md](../SPEC-app.md).

```bash
# terminal 1: the API (from pipeline/)
uv run uvicorn safescale.api.app:app --port 8000
# terminal 2: the dashboard; /api is proxied to :8000 in development
npm install && npm run dev
```

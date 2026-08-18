First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

## Backend and pipeline workers

From the repository root, the full local stack is started with:

```powershell
docker compose up -d --build
```

See [CELERY_README.md](CELERY_README.md) for pipeline queues, schedule,
Flower, diagnostics, and rollback instructions.

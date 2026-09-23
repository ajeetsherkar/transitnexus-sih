# TransitNexus Round 3 Backend Deployment

## Service

- Platform: Render
- Service: `transitnexus-v3`
- Branch: `round3`
- Runtime: Python
- Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Health endpoint: `/health`

## Database

- Platform: Supabase PostgreSQL
- SQLAlchemy driver: Psycopg 3
- Production database is configured through `DATABASE_URL`.
- Database credentials are stored only as deployment environment variables.

## Required Environment Variables

```text
DATABASE_URL
READ_TOKEN
ADMIN_TOKEN
```

Never commit production credentials or API keys.

## Fleet

Production simulator buses: `TN-BUS-001` through `TN-BUS-010`.

Cloud API keys are stored locally in `cloud_keys.json`, which is ignored by Git.

## Round 3 Cloud Validation

The deployed backend was validated with a 10-bus fleet simulation.

- 10 unique buses reported the same pothole.
- Reports were deduplicated into Incident `1`.
- Incident status became `VERIFIED`.
- Incident report count: `11`.
- Unique buses: `10`.
- Confidence: `0.99`.

## Restart Persistence

After restarting/redeploying the Render service, the same incident was queried from the production database.

- Incident `1` still existed.
- Status remained `VERIFIED`.
- Report count remained `11`.
- Unique buses remained `10`.
- All `11` reports remained attached.

This confirms incident state persists in PostgreSQL across backend restarts.

## Simulator

The fleet simulator supports a configurable bus prefix:

```bash
python tools/simulate_fleet.py --help
```

Example:

```bash
python tools/simulate_fleet.py --buses 10 --bus-prefix TN-BUS --scenario same-pothole --keys cloud_keys.json
```

Do not commit `cloud_keys.json`.

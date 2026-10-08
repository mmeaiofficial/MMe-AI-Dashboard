# MME OS

MME's internal Business OS: Stage 1 of the plan in the *MME AI Business OS: Stage 1 Blueprint*.
This repository currently delivers **Milestone 0 (foundation) and Milestone 1 (access and organization)**.

| Area | State |
|---|---|
| Google sign-in (OIDC + PKCE), password fallback, sessions in httpOnly cookies, CSRF | built |
| MFA (authenticator app) required for Super Admins and admin/export permissions | built |
| Roles with grants = permission + scope (own / team / department / all), enforced in the API | built |
| Super Admin console: invite, deactivate (ends sessions, hands over teams/reports), roles, Super Admin status, MFA reset | built |
| Departments, teams, membership, employee profiles (scoped) | built |
| Append-only audit log (database-enforced) for sign-ins, access changes and admin actions | built |
| Last Super Admin protection (API rule + database trigger) | built |
| Worker, file storage, n8n, AI layer | Milestones 2–4 |
| CRM, sales, clients, billing, projects/tasks, attendance/leave, dashboard | Milestones 2–5 |

## Run locally

```bash
cp .env.example .env              # fill GOOGLE_CLIENT_ID/SECRET and BOOTSTRAP_SUPER_ADMINS
docker compose -f infra/docker-compose.yml up --build
docker compose -f infra/docker-compose.yml exec api python -m scripts.seed --org-name "MME AI" --domain mme-ai.com
open http://localhost:3000/sign-in
```

The first person in `BOOTSTRAP_SUPER_ADMINS` to sign in with Google becomes Super Admin and must set up an authenticator.
Everyone else needs an invitation (Users and access → Invite), or a Google account on a domain passed to `--domain`, which joins with the base Employee role.

### Google OAuth client
Google Cloud console → APIs & Services → Credentials → Create OAuth client ID → Web application.
Authorized redirect URIs: `http://localhost:8000/api/v1/auth/google/callback` (and the production API origin + the same path).

## Tests

| Suite | Needs | Command |
|---|---|---|
| Core security: permission engine, scopes, anti-escalation, MFA codes, passwords, encryption, Google token checks, sign-in rules, production config | Python only | `cd apps/api && python -m unittest discover -s tests/core -t .` |
| API: every route declares access, authorization matrix per role, scopes, CSRF, audit, deactivation, Super Admin rules, schema parity | PostgreSQL | `cd apps/api && TEST_DATABASE_URL=… pytest tests/api` |
| Web: type check and production build | Node 22 | `cd apps/web && npm run typecheck && npm run build` |

CI (`.github/workflows/ci.yml`) runs all of them plus migrations up/down, `pip-audit`, `bandit`, `npm audit` and `gitleaks` on every pull request.

## Layout

```
apps/api      FastAPI · app/authz (permission engine) · app/core · app/modules/{identity,access,org} · app/audit · migrations · tests
apps/web      Next.js console: sign-in, MFA, home, people, teams, users and access, roles and permissions, audit log
infra         docker-compose for local work
docs          security model, decisions
```

## Production checklist (before staging/production)
- `APP_ENV=production` refuses to start with a weak `SECRET_KEY`, missing encryption keys, missing Google credentials, non-https origins or development database credentials.
- Set `RATE_LIMIT_BACKEND=redis` (memory is refused in production).
- Run the API behind TLS; set `COOKIE_DOMAIN` if web and API are on sibling subdomains.
- Keep the repository private.

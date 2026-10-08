# Engineering decisions (Milestones 0–1)

| # | Decision | Why |
|---|---|---|
| 1 | The SQL migration file is the schema's source of truth; ORM models mirror it and a test checks parity | Constraints, triggers (append-only audit, last Super Admin) and checks live in the database where they can't be bypassed |
| 2 | Super Admin is a user flag, not a role | Role edits can never mint a Super Admin; changing it has its own rules and audit event |
| 3 | Permission engine is framework-free (`app/authz/engine.py`) | Every rule is unit-tested without a database; the same function computes `/me` permissions and enforces requests |
| 4 | Out-of-scope and other-organization records return 404 | IDs can't be probed |
| 5 | Passwords use scrypt (standard library) | Memory-hard, no extra dependency; Argon2id can replace it behind the same `hash_password` |
| 6 | Sessions are server-side rows, not JWTs | Deactivation and "sign out everywhere" take effect immediately |
| 7 | `organization_id` on every table now, one organization in Stage 1 | Stage 2/3 multi-tenancy without migrating every table |
| 8 | Business change + audit event in one transaction; failed sign-in events in their own | No change without its record; failed attempts still recorded |
| 9 | Google OIDC verified locally (signature, issuer, audience, expiry, nonce, verified email) with PKCE | No third-party auth service needed in Stage 1 |

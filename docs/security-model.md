# Security model (Milestones 0–1)

## Who can get in
1. `BOOTSTRAP_SUPER_ADMINS` emails become Super Admin on their first Google sign-in.
2. An open, unexpired invitation for that email (created by a Super Admin) creates the account with the invited roles and teams.
3. A verified Google account on an organization `allowed_domains` entry joins with the base Employee role.
4. Everyone else is refused. A deactivated account is refused, and an email already linked to a different Google account is refused.

## Sessions
- Random 256-bit token in an httpOnly, SameSite=Lax cookie (Secure outside development); only its SHA-256 is stored.
- Absolute lifetime `SESSION_HOURS`, idle timeout `SESSION_IDLE_MINUTES`; "sign out everywhere" revokes all.
- Writes need `X-CSRF-Token` = HMAC(secret, session token), returned by `/me`.
- Deactivation, Super Admin changes and MFA resets revoke the person's sessions immediately.

## MFA
- TOTP (RFC 6238), secrets encrypted with AES-256-GCM bound to the user id; a used code can't be replayed.
- Required for Super Admins and anyone after enrolment; `admin.*`, `system.*` and every `*.export` permission only take effect once MFA is passed in the session.

## Authorization
- Permission = `module.resource.action`; grant = permission + scope (`own` < `team` < `department` < `all`); a role = set of grants.
- Effective scope = widest across a person's roles; `resource.manage` implies every action.
- Every route declares its permission (`requires(...)`); a test fails the build if a route declares nothing.
- Lists are filtered by scope in SQL; single records outside scope or in another organization return 404.
- Super Admin is a user flag, not a role, so editing roles can never create one.

## Anti-escalation
- Nobody changes their own roles or Super Admin status.
- Only Super Admins edit roles, and not a role they hold.
- A delegated admin can't grant a permission wider than one they hold.
- The last active Super Admin can't be removed (API rule and database trigger).

## Audit
- `audit_events` is append-only: UPDATE and DELETE raise an error in the database.
- Business changes and their audit event commit in one transaction; failed sign-ins and wrong MFA codes are written in their own transaction so a failed request still leaves a trace.
- Secrets in before/after values are redacted.

## Encryption model (stated plainly)
TLS in transit, provider encryption at rest, plus application-level AES-GCM for secrets (MFA secrets now; integration tokens later). This is not end-to-end encryption: the server reads business data to search, report and automate.

## Known gaps to close in later milestones
- Email delivery of invitations (the link is shown once to the admin for now).
- File uploads, malware scanning and signed URLs arrive with the worker in Milestone 2.
- Row-level security on `organization_id` is planned for Stage 2 as a second wall behind API checks.
- Password sign-in exists for accounts without Google; there is no self-service password reset yet (Super Admin resets).

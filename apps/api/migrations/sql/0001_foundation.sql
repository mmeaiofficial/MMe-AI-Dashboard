-- MME OS · Milestones 0 + 1 · foundation, identity, access, organization, audit
-- Every business table carries organization_id (Stage 2/3 multi-tenancy).
-- Applied by Alembic revision 0001 (migrations/versions/0001_foundation.py).

CREATE TABLE organizations (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
    slug            text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9-]{2,60}$'),
    kind            text NOT NULL DEFAULT 'internal' CHECK (kind IN ('internal', 'client')),
    -- allowed_domains: Google accounts on these domains may accept invitations / sign in once invited
    settings        jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE departments (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
    head_user_id    uuid,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    deleted_at      timestamptz,
    UNIQUE (organization_id, name)
);

CREATE TABLE users (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           text NOT NULL CHECK (email = lower(email) AND email LIKE '%_@_%'),
    full_name       text NOT NULL DEFAULT '' CHECK (length(full_name) <= 200),
    avatar_url      text CHECK (avatar_url IS NULL OR avatar_url LIKE 'https://%'),
    google_subject  text,
    password_hash   text,
    status          text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'deactivated')),
    is_super_admin  boolean NOT NULL DEFAULT false,
    department_id   uuid REFERENCES departments(id) ON DELETE SET NULL,
    mfa_required    boolean NOT NULL DEFAULT false,
    last_login_at   timestamptz,
    deactivated_at  timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, email),
    UNIQUE (google_subject)
);
ALTER TABLE departments ADD CONSTRAINT departments_head_fk FOREIGN KEY (head_user_id) REFERENCES users(id) ON DELETE SET NULL;
CREATE INDEX users_org_status_idx ON users (organization_id, status);

CREATE TABLE teams (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    department_id   uuid REFERENCES departments(id) ON DELETE SET NULL,
    name            text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
    kind            text NOT NULL DEFAULT 'custom' CHECK (kind IN ('sales', 'marketing', 'tech', 'ai_automation', 'customer_success', 'finance_ops', 'custom')),
    lead_user_id    uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    deleted_at      timestamptz,
    UNIQUE (organization_id, name)
);

CREATE TABLE team_members (
    team_id         uuid NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    is_manager      boolean NOT NULL DEFAULT false,
    added_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (team_id, user_id)
);
CREATE INDEX team_members_user_idx ON team_members (user_id);

-- HR profile for a user (one per user). Business records point at users.
CREATE TABLE employees (
    user_id         uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    employee_code   text,
    designation     text CHECK (length(designation) <= 120),
    manager_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    employment_type text NOT NULL DEFAULT 'full_time' CHECK (employment_type IN ('full_time', 'part_time', 'intern', 'contract')),
    joined_on       date,
    left_on         date,
    phone           text CHECK (length(phone) <= 30),
    location        text CHECK (length(location) <= 120),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, employee_code)
);

-- ---------- access control ----------
CREATE TABLE roles (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    key             text NOT NULL CHECK (key ~ '^[a-z0-9_]{2,60}$'),
    name            text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
    description     text NOT NULL DEFAULT '',
    is_system       boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, key)
);

CREATE TABLE role_grants (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id         uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    permission      text NOT NULL CHECK (permission ~ '^[a-z_]+\.[a-z_]+\.(view|create|edit|delete|export|approve|manage)$'),
    scope           text NOT NULL CHECK (scope IN ('own', 'team', 'department', 'all')),
    UNIQUE (role_id, permission)
);

CREATE TABLE user_roles (
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id         uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    granted_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    granted_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);

-- ---------- identity ----------
CREATE TABLE invitations (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           text NOT NULL CHECK (email = lower(email)),
    role_ids        uuid[] NOT NULL DEFAULT '{}',
    team_ids        uuid[] NOT NULL DEFAULT '{}',
    department_id   uuid REFERENCES departments(id) ON DELETE SET NULL,
    token_hash      text NOT NULL UNIQUE,
    invited_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    expires_at      timestamptz NOT NULL,
    accepted_at     timestamptz,
    revoked_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX invitations_open_email_idx ON invitations (organization_id, email) WHERE accepted_at IS NULL AND revoked_at IS NULL;

CREATE TABLE sessions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    token_hash      text NOT NULL UNIQUE,           -- sha256 of the cookie value; the raw token is never stored
    mfa_passed      boolean NOT NULL DEFAULT false,
    ip              inet,
    user_agent      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    last_seen_at    timestamptz NOT NULL DEFAULT now(),
    expires_at      timestamptz NOT NULL,
    revoked_at      timestamptz
);
CREATE INDEX sessions_user_idx ON sessions (user_id) WHERE revoked_at IS NULL;

CREATE TABLE mfa_factors (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    kind            text NOT NULL DEFAULT 'totp' CHECK (kind = 'totp'),
    secret_enc      text NOT NULL,                  -- AES-GCM, see core/crypto.py
    confirmed_at    timestamptz,
    last_used_step  bigint,                         -- blocks replay of a used code
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, kind)
);

CREATE TABLE api_keys (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id         uuid REFERENCES users(id) ON DELETE CASCADE,
    name            text NOT NULL,
    prefix          text NOT NULL,                  -- shown in lists, e.g. mme_live_ab12
    key_hash        text NOT NULL UNIQUE,
    permissions     text[] NOT NULL DEFAULT '{}',
    expires_at      timestamptz,
    last_used_at    timestamptz,
    revoked_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- ---------- platform ----------
CREATE TABLE audit_events (
    id              bigserial PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    actor_user_id   uuid REFERENCES users(id) ON DELETE SET NULL,
    action          text NOT NULL CHECK (action ~ '^[a-z_]+\.[a-z_.]+$'),
    target_type     text,
    target_id       text,
    before          jsonb,
    after           jsonb,
    ip              inet,
    user_agent      text,
    request_id      text,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_events_org_time_idx ON audit_events (organization_id, created_at DESC);
CREATE INDEX audit_events_target_idx ON audit_events (organization_id, target_type, target_id);

-- Audit log is append-only: block UPDATE and DELETE at the database level.
CREATE FUNCTION audit_events_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only';
END;
$$;
CREATE TRIGGER audit_events_no_update BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();

CREATE TABLE files (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    owner_id        uuid REFERENCES users(id) ON DELETE SET NULL,
    storage_key     text NOT NULL UNIQUE,
    filename        text NOT NULL CHECK (length(filename) <= 255),
    content_type    text NOT NULL,
    size_bytes      bigint NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 26214400),
    sha256          text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    deleted_at      timestamptz
);

-- Transactional outbox: written with the business change, delivered by the worker (webhooks, n8n).
CREATE TABLE outbox_events (
    id              bigserial PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    topic           text NOT NULL,
    payload         jsonb NOT NULL,
    attempts        int NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    delivered_at    timestamptz,
    last_error      text,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX outbox_pending_idx ON outbox_events (next_attempt_at) WHERE delivered_at IS NULL;

-- updated_at maintenance
CREATE FUNCTION touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;
CREATE TRIGGER organizations_touch BEFORE UPDATE ON organizations FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER departments_touch BEFORE UPDATE ON departments FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER users_touch BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER teams_touch BEFORE UPDATE ON teams FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER employees_touch BEFORE UPDATE ON employees FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER roles_touch BEFORE UPDATE ON roles FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- At least one active super admin must remain in each organization.
CREATE FUNCTION keep_one_super_admin() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (OLD.is_super_admin AND OLD.status = 'active')
       AND (NEW.is_super_admin = false OR NEW.status <> 'active') THEN
        IF NOT EXISTS (
            SELECT 1 FROM users
            WHERE organization_id = OLD.organization_id AND id <> OLD.id
              AND is_super_admin AND status = 'active'
        ) THEN
            RAISE EXCEPTION 'cannot remove the last active super admin';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER users_keep_super_admin BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION keep_one_super_admin();

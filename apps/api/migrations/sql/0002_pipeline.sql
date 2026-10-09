-- Milestone 3 (first slice): the MME-AI pipeline.
-- Lead team finds leads -> Sales L1 cold-calls them -> Sales L2 runs the booked meeting ->
-- a won meeting becomes a client, a project and one ticket per confirmed feature for the tech team.

-- Team kinds for the pipeline stages, so handoffs know where to send work.
ALTER TABLE teams DROP CONSTRAINT teams_kind_check;
ALTER TABLE teams ADD CONSTRAINT teams_kind_check CHECK (kind IN (
    'lead_gen', 'sales_l1', 'sales_l2', 'sales', 'marketing', 'tech', 'ai_automation', 'customer_success', 'finance_ops', 'custom'));

CREATE TABLE leads (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    contact_name    text NOT NULL CHECK (length(contact_name) BETWEEN 1 AND 200),
    company         text CHECK (length(company) <= 200),
    phone           text CHECK (length(phone) <= 30),
    email           text CHECK (length(email) <= 254),
    city            text CHECK (length(city) <= 120),
    industry        text CHECK (length(industry) <= 120),
    website         text CHECK (length(website) <= 300),
    source          text NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'import', 'website', 'referral', 'social', 'cold_list', 'event', 'other')),
    notes           text CHECK (length(notes) <= 4000),
    status          text NOT NULL DEFAULT 'new' CHECK (status IN (
                        'new', 'qualified', 'disqualified', 'contacted', 'callback', 'not_interested', 'meeting_booked', 'won', 'lost')),
    status_reason   text CHECK (length(status_reason) <= 500),
    -- Who holds the lead at each stage; the *_team_id columns drive "team" data scope per stage.
    created_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    source_team_id  uuid REFERENCES teams(id) ON DELETE SET NULL,
    caller_id       uuid REFERENCES users(id) ON DELETE SET NULL,
    caller_team_id  uuid REFERENCES teams(id) ON DELETE SET NULL,
    closer_id       uuid REFERENCES users(id) ON DELETE SET NULL,
    closer_team_id  uuid REFERENCES teams(id) ON DELETE SET NULL,
    call_attempts   integer NOT NULL DEFAULT 0 CHECK (call_attempts >= 0),
    last_called_at  timestamptz,
    next_call_at    timestamptz,
    qualified_at    timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX leads_org_status_idx ON leads (organization_id, status);
CREATE INDEX leads_caller_idx ON leads (caller_id) WHERE caller_id IS NOT NULL;
CREATE INDEX leads_closer_idx ON leads (closer_id) WHERE closer_id IS NOT NULL;
CREATE INDEX leads_phone_idx ON leads (organization_id, phone) WHERE phone IS NOT NULL;
CREATE INDEX leads_email_idx ON leads (organization_id, lower(email)) WHERE email IS NOT NULL;

CREATE TABLE lead_calls (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    lead_id         uuid NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    caller_id       uuid REFERENCES users(id) ON DELETE SET NULL,
    outcome         text NOT NULL CHECK (outcome IN ('no_answer', 'busy', 'wrong_number', 'not_interested', 'callback', 'interested', 'meeting_booked')),
    notes           text CHECK (length(notes) <= 2000),
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX lead_calls_lead_idx ON lead_calls (lead_id, created_at DESC);
CREATE INDEX lead_calls_caller_idx ON lead_calls (caller_id, created_at DESC);

CREATE TABLE meetings (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    lead_id          uuid NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    scheduled_at     timestamptz NOT NULL,
    duration_minutes integer NOT NULL DEFAULT 30 CHECK (duration_minutes BETWEEN 5 AND 480),
    mode             text NOT NULL DEFAULT 'google_meet' CHECK (mode IN ('google_meet', 'zoom', 'phone', 'in_person', 'other')),
    link_or_location text CHECK (length(link_or_location) <= 500),
    agenda           text CHECK (length(agenda) <= 2000),
    booked_by        uuid REFERENCES users(id) ON DELETE SET NULL,
    closer_id        uuid REFERENCES users(id) ON DELETE SET NULL,
    closer_team_id   uuid REFERENCES teams(id) ON DELETE SET NULL,
    status           text NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'no_show', 'cancelled')),
    outcome          text CHECK (outcome IN ('won', 'lost')),
    outcome_notes    text CHECK (length(outcome_notes) <= 4000),
    deal_value       numeric(12, 2) CHECK (deal_value >= 0),
    completed_at     timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX meetings_closer_idx ON meetings (closer_id, scheduled_at);
CREATE INDEX meetings_org_status_idx ON meetings (organization_id, status, scheduled_at);

CREATE TABLE clients (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    lead_id         uuid REFERENCES leads(id) ON DELETE SET NULL,
    name            text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
    contact_name    text CHECK (length(contact_name) <= 200),
    email           text CHECK (length(email) <= 254),
    phone           text CHECK (length(phone) <= 30),
    created_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE projects (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    client_id       uuid NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meeting_id      uuid REFERENCES meetings(id) ON DELETE SET NULL,
    name            text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
    summary         text CHECK (length(summary) <= 4000),
    status          text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'on_hold', 'done')),
    created_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE tickets (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    number          integer NOT NULL CHECK (number > 0),
    project_id      uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    client_id       uuid NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    title           text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    description     text CHECK (length(description) <= 8000),
    priority        text NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    status          text NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'review', 'done')),
    assignee_id     uuid REFERENCES users(id) ON DELETE SET NULL,
    team_id         uuid REFERENCES teams(id) ON DELETE SET NULL,
    created_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    due_on          date,
    done_at         timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, number)
);
CREATE INDEX tickets_org_status_idx ON tickets (organization_id, status);
CREATE INDEX tickets_assignee_idx ON tickets (assignee_id) WHERE assignee_id IS NOT NULL;

CREATE TABLE ticket_notes (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    ticket_id       uuid NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    author_id       uuid REFERENCES users(id) ON DELETE SET NULL,
    body            text NOT NULL CHECK (length(body) BETWEEN 1 AND 4000),
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ticket_notes_ticket_idx ON ticket_notes (ticket_id, created_at);

CREATE TRIGGER leads_touch BEFORE UPDATE ON leads FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER meetings_touch BEFORE UPDATE ON meetings FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER projects_touch BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER tickets_touch BEFORE UPDATE ON tickets FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

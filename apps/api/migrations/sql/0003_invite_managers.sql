-- Invitations remember which of their teams the person will manage, so access given by email
-- (job + team + "manages this team") is complete the moment they first sign in with Google.
ALTER TABLE invitations ADD COLUMN manager_team_ids uuid[] NOT NULL DEFAULT '{}';

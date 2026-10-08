"""Core security tests. Standard library only: run with `python -m unittest discover -s tests/core`
from apps/api. They also run under pytest in CI."""
import base64
import os
import time
import unittest
import uuid

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from app.authz import engine as E
from app.authz.catalog import ALL_PERMISSIONS, DEFAULT_ROLES, validate_catalog
from app.core import security as SEC
from app.core.config import ConfigError, load_settings
from app.core.crypto import FieldCipher
from app.core.google_oidc import InvalidGoogleToken, build_auth_request, verify_id_token
from app.modules.identity.policy import Decision, ExistingUser, decide_sign_in

ORG, OTHER_ORG = uuid.uuid4(), uuid.uuid4()
ME, PEER, STRANGER = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
TEAM_A, TEAM_B, DEPT = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def role_grants(key):
    return tuple(E.Grant(p, s) for p, s in DEFAULT_ROLES[key]["grants"])


def subject(*roles, **kw):
    grants = tuple(g for r in roles for g in role_grants(r))
    base = dict(user_id=ME, organization_id=ORG, grants=grants, team_ids=frozenset({TEAM_A}), department_id=DEPT)
    base.update(kw)
    return E.Subject(**base)


class CatalogTests(unittest.TestCase):
    def test_default_roles_valid(self):
        validate_catalog()
        self.assertIn("crm.leads.view", ALL_PERMISSIONS)

    def test_no_default_role_can_manage_access(self):
        for key, role in DEFAULT_ROLES.items():
            for perm, _ in role["grants"]:
                self.assertFalse(perm.startswith(("admin.", "system.")), f"{key} grants {perm}")


class ScopeTests(unittest.TestCase):
    def lead(self, owner=None, team=None, dept=None, org=ORG, assignees=()):
        return E.RecordRef(organization_id=org, owner_id=owner, team_id=team, department_id=dept, assignee_ids=frozenset(assignees))

    def test_sales_exec_sees_only_own_leads(self):
        s = subject("sales_executive")
        E.check(s, "crm.leads.view", self.lead(owner=ME))
        with self.assertRaises(E.NotFound):
            E.check(s, "crm.leads.view", self.lead(owner=PEER, team=TEAM_A))

    def test_assignee_counts_as_own(self):
        E.check(subject("sales_executive"), "crm.leads.view", self.lead(owner=PEER, assignees=[ME]))

    def test_sales_manager_sees_team_not_other_team(self):
        s = subject("sales_manager")
        E.check(s, "crm.leads.view", self.lead(owner=PEER, team=TEAM_A))
        with self.assertRaises(E.NotFound):
            E.check(s, "crm.leads.view", self.lead(owner=PEER, team=TEAM_B))

    def test_widest_scope_wins_across_roles(self):
        s = subject("sales_executive", "sales_manager")
        self.assertEqual(E.scope_for(s, "crm.leads.view"), "team")

    def test_missing_permission_is_forbidden(self):
        with self.assertRaises(E.Forbidden):
            E.check(subject("employee"), "crm.leads.view", self.lead(owner=ME))

    def test_other_org_is_not_found_even_without_permission(self):
        with self.assertRaises(E.NotFound):
            E.check(subject("employee"), "crm.leads.view", self.lead(owner=ME, org=OTHER_ORG))
        with self.assertRaises(E.NotFound):
            E.check(subject(is_super_admin=True, mfa_passed=True), "crm.leads.view", self.lead(owner=ME, org=OTHER_ORG))

    def test_manage_implies_other_actions(self):
        s = E.Subject(user_id=ME, organization_id=ORG, grants=(E.Grant("work.tasks.manage", "team"),), team_ids=frozenset({TEAM_A}))
        self.assertEqual(E.scope_for(s, "work.tasks.delete"), "team")

    def test_department_scope(self):
        s = E.Subject(user_id=ME, organization_id=ORG, grants=(E.Grant("hr.leave.approve", "department"),), department_id=DEPT)
        E.check(s, "hr.leave.approve", self.lead(owner=PEER, dept=DEPT))
        with self.assertRaises(E.NotFound):
            E.check(s, "hr.leave.approve", self.lead(owner=PEER, dept=uuid.uuid4()))

    def test_deactivated_user_has_nothing(self):
        s = subject("operations_admin", active=False)
        self.assertIsNone(E.scope_for(s, "crm.leads.view"))

    def test_criteria_shapes(self):
        c = E.criteria(subject("sales_manager"), "crm.leads.view")
        self.assertFalse(c.all_records)
        self.assertEqual(c.team_ids, frozenset({TEAM_A}))
        self.assertEqual(c.user_ids, frozenset({ME}))
        self.assertTrue(E.criteria(subject("operations_admin"), "crm.leads.view").all_records)
        with self.assertRaises(E.Forbidden):
            E.criteria(subject("employee"), "crm.leads.view")

    def test_export_needs_mfa(self):
        s = subject("sales_manager")
        self.assertIsNone(E.scope_for(s, "crm.leads.export"))
        self.assertEqual(E.scope_for(subject("sales_manager", mfa_passed=True), "crm.leads.export"), "team")

    def test_super_admin_admin_actions_need_mfa(self):
        self.assertIsNone(E.scope_for(subject(is_super_admin=True), "admin.roles.manage"))
        self.assertEqual(E.scope_for(subject(is_super_admin=True, mfa_passed=True), "admin.roles.manage"), "all")
        self.assertEqual(E.scope_for(subject(is_super_admin=True), "crm.leads.view"), "all")


class EscalationTests(unittest.TestCase):
    def test_nobody_changes_own_roles(self):
        admin = subject(is_super_admin=True, mfa_passed=True)
        with self.assertRaises(E.EscalationDenied):
            E.check_role_assignment(admin, ME, role_grants("employee"))

    def test_employee_cannot_assign_roles(self):
        with self.assertRaises(E.Forbidden):
            E.check_role_assignment(subject("operations_admin", mfa_passed=True), PEER, role_grants("employee"))

    def test_delegated_admin_cannot_grant_wider_than_held(self):
        delegate = E.Subject(user_id=ME, organization_id=ORG, mfa_passed=True,
                             grants=(E.Grant("admin.roles.manage", "all"), E.Grant("crm.leads.view", "team")))
        E.check_role_assignment(delegate, PEER, (E.Grant("crm.leads.view", "own"),))
        with self.assertRaises(E.EscalationDenied):
            E.check_role_assignment(delegate, PEER, (E.Grant("crm.leads.view", "all"),))
        with self.assertRaises(E.EscalationDenied):
            E.check_role_assignment(delegate, PEER, (E.Grant("billing.subscriptions.view", "own"),))

    def test_only_super_admin_edits_roles_and_not_own(self):
        with self.assertRaises(E.EscalationDenied):
            E.check_role_edit(subject("operations_admin", mfa_passed=True), role_grants("employee"), actor_holds_role=False)
        with self.assertRaises(E.EscalationDenied):
            E.check_role_edit(subject(is_super_admin=True, mfa_passed=True), role_grants("employee"), actor_holds_role=True)
        E.check_role_edit(subject(is_super_admin=True, mfa_passed=True), role_grants("employee"), actor_holds_role=False)

    def test_super_admin_status_rules(self):
        sa = subject(is_super_admin=True, mfa_passed=True)
        with self.assertRaises(E.EscalationDenied):
            E.check_super_admin_change(sa, ME, False, 3)
        with self.assertRaises(E.EscalationDenied):
            E.check_super_admin_change(sa, PEER, False, 1)
        with self.assertRaises(E.EscalationDenied):
            E.check_super_admin_change(subject(is_super_admin=True), PEER, True, 1)
        with self.assertRaises(E.EscalationDenied):
            E.check_super_admin_change(subject("operations_admin", mfa_passed=True), PEER, True, 1)
        E.check_super_admin_change(sa, PEER, True, 1)


class SecurityTests(unittest.TestCase):
    def test_password_roundtrip_and_rejects(self):
        h = SEC.hash_password("correct horse battery")
        self.assertTrue(SEC.verify_password("correct horse battery", h))
        self.assertFalse(SEC.verify_password("wrong horse battery", h))
        self.assertFalse(SEC.verify_password("anything", None))
        self.assertNotEqual(h, SEC.hash_password("correct horse battery"))
        with self.assertRaises(ValueError):
            SEC.hash_password("short")

    def test_totp_rfc6238_vector(self):
        secret = base64.b32encode(b"12345678901234567890").decode()
        self.assertEqual(SEC.totp_at(secret, 59 // 30), "287082")
        self.assertEqual(SEC.totp_at(secret, 1111111109 // 30), "081804")

    def test_totp_verify_window_and_replay(self):
        secret = SEC.new_totp_secret()
        now = 1_800_000_000
        code = SEC.totp_at(secret, now // 30)
        step = SEC.verify_totp(secret, code, None, now=now)
        self.assertEqual(step, now // 30)
        self.assertIsNone(SEC.verify_totp(secret, code, step, now=now), "replay must fail")
        self.assertIsNotNone(SEC.verify_totp(secret, SEC.totp_at(secret, now // 30 - 1), None, now=now))
        self.assertIsNone(SEC.verify_totp(secret, SEC.totp_at(secret, now // 30 - 3), None, now=now))
        self.assertIsNone(SEC.verify_totp(secret, "12ab56", None, now=now))

    def test_tokens_and_csrf(self):
        t = SEC.new_token()
        self.assertEqual(len(SEC.token_hash(t)), 64)
        c = SEC.csrf_token(t, "k" * 32)
        self.assertTrue(SEC.verify_csrf(t, "k" * 32, c))
        self.assertFalse(SEC.verify_csrf(SEC.new_token(), "k" * 32, c))
        self.assertFalse(SEC.verify_csrf(t, "k" * 32, None))
        key, prefix = SEC.new_api_key()
        self.assertTrue(key.startswith(prefix) and prefix.startswith("mme_live_"))


class CryptoTests(unittest.TestCase):
    def setUp(self):
        self.k1, self.k2 = os.urandom(32), os.urandom(32)

    def test_roundtrip_context_and_tamper(self):
        c = FieldCipher({"k1": self.k1}, "k1")
        ct = c.encrypt("JBSWY3DPEHPK3PXP", "mfa:user-1")
        self.assertEqual(c.decrypt(ct, "mfa:user-1"), "JBSWY3DPEHPK3PXP")
        with self.assertRaises(Exception):
            c.decrypt(ct, "mfa:user-2")
        parts = ct.split(".")
        parts[3] = parts[3][:-2] + ("AA" if parts[3][-2:] != "AA" else "BB")
        with self.assertRaises(Exception):
            c.decrypt(".".join(parts), "mfa:user-1")

    def test_rotation(self):
        old = FieldCipher({"k1": self.k1}, "k1").encrypt("s", "ctx")
        new = FieldCipher({"k1": self.k1, "k2": self.k2}, "k2")
        self.assertEqual(new.decrypt(old, "ctx"), "s")
        self.assertTrue(new.needs_rotation(old))
        self.assertFalse(new.needs_rotation(new.encrypt("s", "ctx")))

    def test_from_env(self):
        spec = "k1:" + base64.urlsafe_b64encode(self.k1).decode()
        c = FieldCipher.from_env(spec, "k1")
        self.assertEqual(c.decrypt(c.encrypt("x", "y"), "y"), "x")


class GoogleTests(unittest.TestCase):
    CLIENT = "client-123.apps.googleusercontent.com"

    def setUp(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.pub = self.key.public_key()

    def token(self, **over):
        now = int(time.time())
        claims = {"iss": "https://accounts.google.com", "aud": self.CLIENT, "sub": "1234", "iat": now, "exp": now + 600,
                  "email": "Neha@MME-AI.com", "email_verified": True, "nonce": "n1", "name": "Neha", "hd": "mme-ai.com"}
        claims.update(over)
        return jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "k"})

    def verify(self, tok, nonce="n1", key=None):
        return verify_id_token(tok, self.CLIENT, nonce, key_resolver=lambda _t: key or self.pub)

    def test_valid(self):
        ident = self.verify(self.token())
        self.assertEqual(ident.email, "neha@mme-ai.com")
        self.assertEqual(ident.hosted_domain, "mme-ai.com")

    def test_rejections(self):
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
        cases = [
            (self.token(aud="someone-else"), "n1", None),
            (self.token(iss="https://evil.example"), "n1", None),
            (self.token(exp=int(time.time()) - 3600), "n1", None),
            (self.token(), "different-nonce", None),
            (self.token(email_verified=False), "n1", None),
            (self.token(), "n1", other),
        ]
        for tok, nonce, key in cases:
            with self.assertRaises(InvalidGoogleToken):
                self.verify(tok, nonce, key)

    def test_auth_request_has_pkce_and_state(self):
        req = build_auth_request(self.CLIENT, "https://api.example/auth/google/callback")
        self.assertIn("code_challenge_method=S256", req.url)
        self.assertIn(req.state, req.url)
        self.assertNotIn(req.code_verifier, req.url)


class SignInPolicyTests(unittest.TestCase):
    def test_branches(self):
        active = ExistingUser("active", "g1")
        self.assertEqual(decide_sign_in("a@x.com", "g1", active, False, []), Decision.SIGN_IN)
        self.assertEqual(decide_sign_in("a@x.com", "g2", active, False, []), Decision.DENY_SUBJECT_MISMATCH)
        self.assertEqual(decide_sign_in("a@x.com", "g1", ExistingUser("deactivated", "g1"), True, ["x.com"]), Decision.DENY_DEACTIVATED)
        self.assertEqual(decide_sign_in("a@x.com", "g1", None, True, []), Decision.CREATE_FROM_INVITE)
        self.assertEqual(decide_sign_in("A@MME-AI.com", "g1", None, False, ["mme-ai.com"]), Decision.CREATE_FROM_DOMAIN)
        self.assertEqual(decide_sign_in("a@gmail.com", "g1", None, False, ["mme-ai.com"]), Decision.DENY_NOT_INVITED)


class ConfigTests(unittest.TestCase):
    def test_dev_defaults_load(self):
        self.assertEqual(load_settings({}).env, "development")

    def test_production_refuses_unsafe_values(self):
        with self.assertRaises(ConfigError):
            load_settings({"APP_ENV": "production"})
        with self.assertRaises(ConfigError):
            load_settings({"APP_ENV": "production", "SECRET_KEY": "your-secret-key-change-in-production"})

    def test_production_ok_when_configured(self):
        env = {"APP_ENV": "production", "SECRET_KEY": "x" * 48, "FIELD_ENCRYPTION_KEYS": "k1:" + base64.urlsafe_b64encode(os.urandom(32)).decode(),
               "FIELD_ENCRYPTION_ACTIVE_KID": "k1", "GOOGLE_CLIENT_ID": "id", "GOOGLE_CLIENT_SECRET": "s",
               "WEB_ORIGIN": "https://os.mme-ai.com", "API_ORIGIN": "https://api.mme-ai.com", "DATABASE_URL": "postgresql+psycopg://app:pw@db:5432/mme",
               "BOOTSTRAP_SUPER_ADMINS": "A@B.com, c@d.com"}
        s = load_settings(env)
        self.assertTrue(s.cookie_secure)
        self.assertEqual(s.bootstrap_super_admins, ("a@b.com", "c@d.com"))


if __name__ == "__main__":
    unittest.main()

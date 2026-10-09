"""Ask Rekha: the tool loop and, above all, that tools never return more than the caller may see.

A scripted fake replaces the Anthropic client, so these tests make no network calls.
"""
from __future__ import annotations

import json
from types import SimpleNamespace as NS

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.models import AuditEvent
from app.modules.assistant import router as rekha


class FakeClaude:
    """Replies with each scripted response in turn and records every request it receives."""

    def __init__(self, script):
        self.script, self.requests = list(script), []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        return self.script.pop(0)


def tool_call(name, args=None):
    block = NS(type="tool_use", id=f"tu_{name}", name=name, input=args or {})
    return NS(content=[block], stop_reason="tool_use", usage=NS(input_tokens=10, output_tokens=5))


def answer(text="Done.", stop="end_turn"):
    return NS(content=[NS(type="text", text=text)], stop_reason=stop, usage=NS(input_tokens=10, output_tokens=5))


@pytest.fixture()
def claude(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def install(*script):
        fake = FakeClaude(script)
        monkeypatch.setattr(rekha, "_client", lambda: fake)
        return fake
    return install


def ask(client, text="hi"):
    return client.send("POST", "/assistant/chat", {"messages": [{"role": "user", "content": text}]})


def tool_result(fake):
    """The tool_result block Rekha sent back to the model in its second request."""
    block = fake.requests[1]["messages"][-1]["content"][0]
    return block, (json.loads(block["content"]) if not block["is_error"] else block["content"])


def test_status_and_missing_key(as_user, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    c = as_user("emp")
    assert c.get("/assistant/status").json()["enabled"] is False
    r = ask(c)
    assert r.status_code == 503 and "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_chat_needs_sign_in_and_csrf(as_user, claude):
    claude(answer())
    assert as_user("emp").send("POST", "/assistant/chat", {"messages": [{"role": "user", "content": "hi"}]}, csrf=False).status_code == 403


def test_last_turn_must_be_user(as_user, claude):
    claude(answer())
    turns = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    r = as_user("emp").send("POST", "/assistant/chat", {"messages": turns})
    assert r.status_code == 422


def test_people_search_is_scoped(as_user, claude):
    fake = claude(tool_call("search_people"), answer("Two people."))
    r = ask(as_user("sales_exec"), "who can I see?")
    assert r.status_code == 200, r.text
    assert r.json() == {"reply": "Two people.", "tools_used": ["search_people"], "stop": "end_turn"}
    block, data = tool_result(fake)
    assert block["is_error"] is False
    # Sales executives see their own team only, exactly as GET /employees does.
    assert {p["email"] for p in data["people"]} == {"salesmgr@mme-ai.com", "sales@mme-ai.com"}


def test_super_admin_sees_everyone(as_user, claude):
    fake = claude(tool_call("search_people", {"query": "mme-ai.com"}), answer())
    ask(as_user("founder"))
    _, data = tool_result(fake)
    assert data["total"] == 7


@pytest.mark.parametrize("who,tool,args", [
    ("emp", "recent_activity", {"days": 3}),
    ("sales_exec", "get_team_members", {"team_name": "Tech"}),
    ("dev", "list_roles", {}),
])
def test_tools_refuse_without_permission(as_user, claude, who, tool, args):
    fake = claude(tool_call(tool, args), answer("You don't have access."))
    assert ask(as_user(who)).status_code == 200
    block, msg = tool_result(fake)
    assert block["is_error"] is True and "doesn't have access" in msg


def test_team_outside_scope_looks_absent(as_user, claude):
    # A sales manager can view their own team but not Tech: the tool must not confirm Tech exists.
    fake = claude(tool_call("get_team_members", {"team_name": "Tech"}), answer())
    ask(as_user("sales_mgr"))
    block, msg = tool_result(fake)
    assert block["is_error"] is True and "No team named" in msg


def test_profile_tool_needs_no_permission(as_user, claude):
    fake = claude(tool_call("get_my_profile"), answer())
    ask(as_user("emp"))
    _, data = tool_result(fake)
    assert data["email"] == "emp@mme-ai.com" and data["teams"] == [{"name": "Tech", "is_manager": False}]


def test_refusal_and_audit_metadata_only(as_user, claude):
    claude(answer("", stop="refusal"))
    r = ask(as_user("ops"), "something secret")
    assert r.json()["reply"] == "I can't help with that one." and r.json()["stop"] == "refusal"
    db = SessionLocal()
    ev = db.scalars(select(AuditEvent).where(AuditEvent.action == "ai.assistant_asked")).one()
    db.close()
    assert ev.after["stop"] == "refusal" and "something secret" not in json.dumps(ev.after)


def test_runaway_tool_loop_stops(as_user, claude):
    claude(*[tool_call("get_my_profile") for _ in range(rekha.MAX_TOOL_ROUNDS)])
    r = ask(as_user("emp"))
    assert r.status_code == 200 and r.json()["stop"] == "max_rounds"


def test_request_shape(as_user, claude):
    fake = claude(answer())
    ask(as_user("emp"), "hello")
    req = fake.requests[0]
    assert req["model"] == rekha.MODEL and req["fallbacks"] == "default" and rekha.FALLBACK_BETA in req["betas"]
    assert [t["name"] for t in req["tools"]] == [t.name for t in rekha.TOOLS]
    assert req["messages"] == [{"role": "user", "content": "hello"}]

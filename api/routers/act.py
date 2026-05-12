"""
Action Center endpoints — the "Act" leg of OODA.

Day 5 (EXECUTION_HANDOFF §5.3). Four endpoints:

  * POST /act/email/draft     — LLM drafts an email for the operator to review.
                                Writes a row to governance.action_history with
                                status='drafted'. Returns the draft text and the
                                action_id so the dashboard can show / edit / send.
  * POST /act/email/send      — Marks an existing draft as 'sent'. SMTP delivery
                                is gated behind SMTP_* env vars; without them
                                the row is flipped to 'sent' but no network
                                I/O happens (the operator copied / sent
                                manually). This keeps the demo runnable on
                                a laptop without an SMTP relay.
  * POST /act/webhook         — Fire a configured webhook (Slack / Linear /
                                Jira) with a structured payload. The URL is
                                read from env vars at request time, not at
                                import — keeps secret reloads cheap.
  * POST /act/escalate        — Writes a critical row to governance.alerts so
                                the Data Health page surfaces an unresolved
                                incident. Also writes to action_history for
                                provenance.

None of these endpoints actually charge money — the SMTP / webhook calls are
gated by env vars and degrade gracefully when those are missing.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from typing import Literal

import httpx
from db import get_db, log_audit
from fastapi import APIRouter, HTTPException
from llm_client import complete, is_available
from pydantic import BaseModel, Field

from routers.governance import (
    fetch_action,
    insert_action,
    update_action_status,
)

router = APIRouter()


# ── Shared schemas ─────────────────────────────────────────────────────

class ActionResponse(BaseModel):
    action_id: int | None
    status: Literal["drafted", "sent", "failed", "cancelled"]
    detail: str | None = None
    generated_at: str


# ── Email draft (LLM) ──────────────────────────────────────────────────

EMAIL_DRAFT_SYSTEM = """You are the Marketplace Decision Cockpit's outbound communications drafter.
You write short, action-oriented emails on behalf of the Head of E-commerce Operations.

Constraints:
- 120 words or fewer, including the subject.
- First line is "Subject: ..." then a blank line, then the body.
- Tone: professional, factual, no sycophancy. No emojis.
- Reference only numbers you've been given in DATA CONTEXT. Don't invent.
- Body opens with one-sentence context, lists 2–3 concrete asks, closes with a deadline.
- Sign-off: "— Operations, Olist marketplace".

Output the email body only. No preamble, no commentary, no JSON, no fences.
"""


class EmailDraftRequest(BaseModel):
    subject_ref: str = Field(description="e.g. 'otif_rate@2018-08-29' or 'seller@a1b2c3d4'")
    target_role: Literal["seller", "internal_ops", "carrier", "category_manager"] = "seller"
    context: dict = Field(default_factory=dict,
        description="DATA CONTEXT the model can cite (numbers, names, dates)")
    recipient: str | None = Field(default=None, description="Email address (optional)")
    created_by: str | None = None


@router.post("/act/email/draft", response_model=ActionResponse)
async def draft_email(req: EmailDraftRequest) -> ActionResponse:
    """Have the LLM draft an email. Always records a row to
    governance.action_history with status='drafted' — even when the LLM
    is unavailable, in which case the body is a template the operator
    can edit."""
    started = time.perf_counter()

    if is_available():
        try:
            user = (
                f"Recipient role: {req.target_role}\n"
                f"Subject ref: {req.subject_ref}\n"
                f"DATA CONTEXT (cite only these):\n{json.dumps(req.context, default=str)[:1500]}"
            )
            llm = complete(
                system=EMAIL_DRAFT_SYSTEM,
                user=user,
                max_tokens=500,
                temperature=0.3,
            )
            body = llm.text.strip()
            provider, model = llm.provider, llm.model
        except Exception as e:
            body = _template_email(req)
            provider, model = "template", f"fallback (LLM error: {str(e)[:80]})"
    else:
        body = _template_email(req)
        provider, model = "template", "fallback"

    title_line = body.splitlines()[0][:200] if body else "(empty)"
    action_id = insert_action(
        action_type="email",
        channel=f"email:{req.target_role}",
        subject_ref=req.subject_ref,
        status="drafted",
        title=title_line.replace("Subject: ", "", 1),
        payload={
            "body": body,
            "recipient": req.recipient,
            "target_role": req.target_role,
            "context": req.context,
            "drafted_by_provider": provider,
            "drafted_by_model": model,
        },
        created_by=req.created_by,
    )

    log_audit(
        endpoint="POST /api/v1/act/email/draft",
        user_input=req.subject_ref,
        llm_provider=provider,
        llm_model=model,
        llm_output=body,
        data_context=req.context,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )

    return ActionResponse(
        action_id=action_id,
        status="drafted",
        detail=body,
        generated_at=datetime.now(UTC).isoformat(),
    )


def _template_email(req: EmailDraftRequest) -> str:
    """Fallback body when the LLM is unavailable. Operator edits before sending."""
    subj = req.subject_ref
    return (
        f"Subject: Action needed on {subj}\n\n"
        f"Hi,\n\n"
        f"Our operational monitoring flagged {subj} for review. "
        f"Could you confirm the cause and propose a remediation by end of business tomorrow?\n\n"
        f"- Acknowledge receipt of this message.\n"
        f"- Share root cause analysis.\n"
        f"- Confirm action plan and timeline.\n\n"
        f"— Operations, Olist marketplace"
    )


# ── Email send (records 'sent', no SMTP unless configured) ────────────

class EmailSendRequest(BaseModel):
    action_id: int = Field(description="Existing draft id from /act/email/draft")
    body: str | None = Field(default=None,
        description="Optional edited body. If omitted, sends the original draft.")
    recipient: str | None = Field(default=None,
        description="Optional override; falls back to the draft's payload.recipient")


@router.post("/act/email/send", response_model=ActionResponse)
async def send_email(req: EmailSendRequest) -> ActionResponse:
    """Flip a draft to 'sent'. Only makes a real SMTP call when
    SMTP_HOST + SMTP_USER + SMTP_PASSWORD are all set; otherwise records
    the intent and lets the operator deliver manually."""
    action = fetch_action(req.action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"action {req.action_id} not found")
    if action["action_type"] != "email":
        raise HTTPException(status_code=400, detail="action is not an email")
    if action["status"] not in ("drafted", "failed"):
        raise HTTPException(status_code=409,
            detail=f"action already in status '{action['status']}'")

    payload = dict(action["payload"] or {})
    body = req.body or payload.get("body") or ""
    recipient = req.recipient or payload.get("recipient") or ""

    smtp_ready = all([
        os.getenv("SMTP_HOST"),
        os.getenv("SMTP_USER"),
        os.getenv("SMTP_PASSWORD"),
    ])
    sent_ok = True
    delivery_err: str | None = None

    if smtp_ready and recipient:
        try:
            _smtp_send(body=body, recipient=recipient)
        except Exception as e:
            sent_ok = False
            delivery_err = str(e)[:300]

    result = {
        "smtp_attempted": bool(smtp_ready and recipient),
        "smtp_ok": sent_ok,
        "error": delivery_err,
        "final_recipient": recipient,
        "final_body": body,
    }
    new_status = "sent" if sent_ok else "failed"
    update_action_status(req.action_id, status=new_status, result=result)

    return ActionResponse(
        action_id=req.action_id,
        status=new_status,
        detail=delivery_err if not sent_ok else (
            "SMTP delivered" if smtp_ready and recipient
            else "Recorded as sent (no SMTP configured — operator delivered manually)"
        ),
        generated_at=datetime.now(UTC).isoformat(),
    )


def _smtp_send(*, body: str, recipient: str) -> None:
    """Plain SMTP send. Imported lazily so the api stays bootable without
    smtplib being healthy. Subject is parsed off the first line."""
    import smtplib
    from email.message import EmailMessage

    lines = body.splitlines()
    subject = "Operations update"
    body_lines = lines
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body_lines = lines[2:] if len(lines) > 1 and lines[1].strip() == "" else lines[1:]

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("SMTP_FROM", os.environ["SMTP_USER"])
    msg["To"] = recipient
    msg.set_content("\n".join(body_lines))

    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=15) as srv:
        srv.starttls()
        srv.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        srv.send_message(msg)


# ── Webhook (Slack / Linear / Jira) ────────────────────────────────────

class WebhookRequest(BaseModel):
    subject_ref: str
    channel: Literal["slack", "linear", "jira"] = "slack"
    title: str
    body: str
    severity: Literal["info", "warning", "critical"] = "warning"
    created_by: str | None = None


_WEBHOOK_ENV_MAP = {
    "slack":  ("WEBHOOK_SLACK_URL", "WEBHOOK_SLACK_TOKEN"),
    "linear": ("WEBHOOK_LINEAR_URL", "WEBHOOK_LINEAR_TOKEN"),
    "jira":   ("WEBHOOK_JIRA_URL", "WEBHOOK_JIRA_TOKEN"),
}


@router.post("/act/webhook", response_model=ActionResponse)
async def fire_webhook(req: WebhookRequest) -> ActionResponse:
    """POST a structured message to a configured webhook. Records the
    attempt + outcome to governance.action_history."""
    url_env, tok_env = _WEBHOOK_ENV_MAP[req.channel]
    url = os.getenv(url_env)
    token = os.getenv(tok_env)

    payload = {
        "subject_ref": req.subject_ref,
        "title": req.title,
        "body": req.body,
        "severity": req.severity,
    }

    status = "drafted"
    result: dict = {"channel": req.channel, "url_configured": bool(url)}

    if url:
        try:
            with httpx.Client(timeout=10) as client:
                headers = {"Content-Type": "application/json"}
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                rsp = client.post(url, headers=headers, json=payload)
                result["http_status"] = rsp.status_code
                if 200 <= rsp.status_code < 300:
                    status = "sent"
                else:
                    status = "failed"
                    result["body"] = rsp.text[:500]
        except Exception as e:
            status = "failed"
            result["error"] = str(e)[:300]
    else:
        # No URL configured — record as drafted, operator can rerun later.
        result["error"] = f"{url_env} not set"

    action_id = insert_action(
        action_type="webhook",
        channel=req.channel,
        subject_ref=req.subject_ref,
        status=status,
        title=req.title,
        payload=payload,
        result=result,
        created_by=req.created_by,
    )

    return ActionResponse(
        action_id=action_id,
        status=status,
        detail=(
            f"{req.channel} POSTed: HTTP {result.get('http_status')}"
            if status == "sent"
            else result.get("error") or "webhook not configured"
        ),
        generated_at=datetime.now(UTC).isoformat(),
    )


# ── Escalation (writes governance.alerts + action_history) ─────────────

class EscalateRequest(BaseModel):
    subject_ref: str
    severity: Literal["warning", "critical"] = "critical"
    reason: str
    created_by: str | None = None


@router.post("/act/escalate", response_model=ActionResponse)
async def escalate(req: EscalateRequest) -> ActionResponse:
    """Open a high-priority alert in governance.alerts AND record the
    escalation in action_history. Idempotent on (kind, source_ref)."""
    details = {"reason": req.reason, "subject_ref": req.subject_ref}
    payload = json.dumps(details, default=str)

    alert_id: int | None = None
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE governance.alerts
                       SET created_at = now(),
                           severity   = %s,
                           message    = %s,
                           details    = %s::jsonb
                     WHERE kind = 'pipeline_error'
                       AND source_ref = %s
                       AND resolved_at IS NULL
                """, (req.severity, req.reason, payload, req.subject_ref))
                if cur.rowcount == 0:
                    cur.execute("""
                        INSERT INTO governance.alerts
                            (kind, severity, source_ref, message, details)
                        VALUES ('pipeline_error', %s, %s, %s, %s::jsonb)
                        RETURNING id
                    """, (req.severity, req.subject_ref, req.reason, payload))
                    row = cur.fetchone()
                    alert_id = int(row["id"]) if row else None
                conn.commit()
    except Exception:
        alert_id = None

    action_id = insert_action(
        action_type="escalation",
        channel="escalate:internal",
        subject_ref=req.subject_ref,
        status="sent",
        title=req.reason[:140],
        payload=details,
        result={"alert_id": alert_id, "severity": req.severity},
        created_by=req.created_by,
    )

    return ActionResponse(
        action_id=action_id,
        status="sent",
        detail=f"escalated as {req.severity}; alert_id={alert_id}",
        generated_at=datetime.now(UTC).isoformat(),
    )

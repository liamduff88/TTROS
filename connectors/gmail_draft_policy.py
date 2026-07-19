"""Executable authority boundary for Gmail draft creation.

Revisit: when the live Composio Gmail action catalog changes. · Last touched: 2026-07-17.
"""

from __future__ import annotations


GMAIL_CREATE_DRAFT_ACTION = "GMAIL_CREATE_EMAIL_DRAFT"

GMAIL_AUTHORITY_CONTRACT = {
    "gmail_create_draft": "allowed",
    "gmail_send": "forbidden",
    "gmail_reply": "forbidden",
    "gmail_forward": "forbidden",
    "gmail_schedule_send": "forbidden",
}

# Current live catalog actions are named explicitly for auditability.  The
# generic boundary below also fails closed for future non-read Gmail actions.
EXPLICITLY_FORBIDDEN_GMAIL_ACTIONS = frozenset({
    "GMAIL_SEND_EMAIL",
    "GMAIL_SEND_DRAFT",
    "GMAIL_REPLY_TO_THREAD",
    "GMAIL_FORWARD_MESSAGE",
    "GMAIL_DELETE_DRAFT",
    "GMAIL_UPDATE_DRAFT",
    "GMAIL_BATCH_MODIFY_MESSAGES",
    "GMAIL_MODIFY_THREAD_LABELS",
    "GMAIL_ADD_LABEL_TO_EMAIL",
    "GMAIL_CREATE_LABEL",
})

_READ_ONLY_GMAIL_PREFIXES = (
    "GMAIL_FETCH_",
    "GMAIL_GET_",
    "GMAIL_LIST_",
    "GMAIL_SEARCH_",
)


class GmailAuthorityError(ValueError):
    """The requested action is outside Agentic OS Gmail authority."""


def authorize_draft_action(action: str) -> str:
    """Allow exactly one provider action through the draft-only adapter."""
    normalized = str(action or "").strip().upper()
    if normalized != GMAIL_CREATE_DRAFT_ACTION:
        raise GmailAuthorityError("Gmail draft authority allows only GMAIL_CREATE_EMAIL_DRAFT")
    return normalized


def authorize_generic_gmail_action(action: str) -> str:
    """Keep generic Gmail routing read-only and force drafts through the safe adapter."""
    normalized = str(action or "").strip().upper()
    if not normalized.startswith("GMAIL_"):
        return normalized
    if normalized == GMAIL_CREATE_DRAFT_ACTION:
        raise GmailAuthorityError("Gmail drafts must use the idempotent gmail_draft_adapter")
    if normalized in EXPLICITLY_FORBIDDEN_GMAIL_ACTIONS:
        raise GmailAuthorityError("Gmail action is forbidden by the Agentic OS authority contract")
    if normalized.startswith(_READ_ONLY_GMAIL_PREFIXES):
        return normalized
    raise GmailAuthorityError("Non-read Gmail action is forbidden by the Agentic OS authority contract")

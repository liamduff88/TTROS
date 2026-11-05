"""Dashboard generic Composio route: verified operator + fail-closed read-only classification.

Revisit: when /api/connectors/composio/action, the Remote PC identity gate or the classifier changes. · Last touched: 2026-11-05.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from dashboard.backend import main as backend
import remote_pc

TAILNET = {"x-ttros-remote-pc": "1", "tailscale-user-login": "liamduff88@gmail.com", "origin": "https://vrs-global.tailb38520.ts.net"}


def make_request(headers: dict[str, str]) -> Request:
    raw = [(key.lower().encode(), value.encode()) for key, value in headers.items()]
    return Request({"type": "http", "method": "POST", "path": "/api/connectors/composio/action", "headers": raw, "query_string": b""})


class ClassifierTest(unittest.TestCase):
    def test_reads_are_positively_classified(self):
        reads = ["GMAIL_FETCH_EMAILS", "GMAIL_SEARCH_EMAILS", "LINKEDIN_GET_MY_INFO", "GITHUB_GET_THE_AUTHENTICATED_USER",
                 "YOUTUBE_LIST_CHANNEL_VIDEOS", "GOOGLECALENDAR_FIND_EVENT", "linkedin_get_my_info"]
        reads += [slug for _, mode, slug, _ in backend.COMPOSIO_SMOKE_CHECKS if mode == "tool-run"]
        for slug in reads:
            self.assertEqual(backend.classify_composio_action(slug)[0], "read", slug)

    def test_mutations_unknowns_and_malformed_are_refused(self):
        cases = {
            "GMAIL_SEND_EMAIL": "mutation", "GMAIL_CREATE_EMAIL_DRAFT": "mutation", "LINKEDIN_CREATE_LINKED_IN_POST": "mutation",
            "LINKEDIN_DELETE_LINKED_IN_POST": "mutation", "GMAIL_BATCH_MODIFY_MESSAGES": "mutation", "GITHUB_STAR_A_REPO": "mutation",
            "GOOGLEDRIVE_GET_AND_DELETE_FILE": "mutation", "AGENT_MAIL_SEND_EMAIL": "mutation", "GMAIL_REPLY_TO_THREAD": "mutation",
            "TWITTER_RETWEET": "unknown", "LINKEDIN_MY_INFO": "unknown", "SLACK_CHAT_ME_MESSAGE": "unknown",
            "": "invalid", "GMAIL": "invalid", "GMAIL_FETCH_EMAILS; rm -rf /": "invalid", "GMAIL FETCH": "invalid",
            "GMAIL_FETCH_EMAILS\n": "read",  # surrounding whitespace is stripped, never part of the slug
        }
        for slug, expected in cases.items():
            self.assertEqual(backend.classify_composio_action(slug)[0], expected, repr(slug))


class ActionRouteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [
            patch.object(remote_pc, "RECEIPTS_DIR", Path(self.tmp.name)),
            patch.object(remote_pc, "DENIED_LOG", Path(self.tmp.name) / "denied.jsonl"),
        ]
        # Backstop: the subprocess that would reach Composio is always mocked, so no
        # action (least of all a post) can reach the provider even if the guard fails.
        self.boundary = patch.object(backend, "_run_agentic_os_clean_bash",
                                     return_value={"output": '{"ok": true, "result": {}}'})
        self.provider = self.boundary.start()
        for item in self.patches:
            item.start()

    def tearDown(self):
        self.boundary.stop()
        for item in self.patches:
            item.stop()
        self.tmp.cleanup()

    def call(self, headers, slug, args=None):
        body = backend.ComposioAction(tool_slug=slug, json_args=args if args is not None else {})
        return backend.composio_action(body, make_request(headers))

    def assertRefused(self, headers, slug, fragment):
        with patch.object(backend, "_run_composio_adapter") as adapter:
            with self.assertRaises(HTTPException) as caught:
                self.call(headers, slug)
        self.assertEqual(caught.exception.status_code, 403)
        self.assertIn(fragment, caught.exception.detail)
        adapter.assert_not_called()

    def test_verified_operator_read_runs_through_shared_adapter(self):
        with patch.object(backend, "_run_composio_adapter", return_value={"ok": True, "result": {"name": "x"}}) as adapter:
            result = self.call(TAILNET, "linkedin_get_my_info")
        adapter.assert_called_once_with("tool-run", "LINKEDIN_GET_MY_INFO", {})
        self.assertTrue(result["ok"])
        self.assertEqual(result["tool_slug"], "LINKEDIN_GET_MY_INFO")

    def test_missing_credentials_are_refused_and_logged(self):
        self.assertRefused({}, "GMAIL_FETCH_EMAILS", "missing Remote PC request header")
        self.assertRefused({"x-ttros-remote-pc": "1"}, "GMAIL_FETCH_EMAILS", "no verified operator identity")
        rows = (Path(self.tmp.name) / "denied.jsonl").read_text().splitlines()
        self.assertEqual(len(rows), 2)
        self.assertIn("/api/connectors/composio/action", rows[0])

    def test_unallowlisted_or_forged_identity_is_refused(self):
        self.assertRefused({**TAILNET, "tailscale-user-login": "someone@example.com"}, "GMAIL_FETCH_EMAILS", "not authorised")
        # Any Cloudflare header switches to the JWT path; a forged Tailscale header does not help.
        self.assertRefused({**TAILNET, "cf-ray": "abc"}, "GMAIL_FETCH_EMAILS", "Cloudflare Access assertion missing or invalid")
        self.assertRefused({**TAILNET, "origin": "https://evil.example"}, "GMAIL_FETCH_EMAILS", "cross-site origin refused")

    def test_mutations_and_unknown_actions_never_reach_adapter(self):
        for slug in ("GMAIL_SEND_EMAIL", "GMAIL_CREATE_EMAIL_DRAFT", "LINKEDIN_CREATE_LINKED_IN_POST"):
            self.assertRefused(TAILNET, slug, "refused (mutation)")
        self.assertRefused(TAILNET, "TWITTER_RETWEET", "refused (unknown)")
        self.assertRefused(TAILNET, "GMAIL_FETCH; whoami", "refused (invalid)")

    def test_task_text_route_fails_closed_too(self):
        with patch.object(backend, "_run_composio_adapter", return_value={"ok": True}) as adapter:
            refused = backend._try_composio_task('composio action GMAIL_SEND_EMAIL {"to": "a@example.com"}')
            unknown = backend._try_composio_task("composio action TWITTER_RETWEET {}")
            adapter.assert_not_called()
            allowed = backend._try_composio_task('composio action GMAIL_FETCH_EMAILS {"max_results": 1}')
        self.assertFalse(refused["success"])
        self.assertIn("refused (mutation)", refused["output"])
        self.assertIn("refused (unknown)", unknown["output"])
        self.assertTrue(allowed["success"])
        adapter.assert_called_once_with("tool-run", "GMAIL_FETCH_EMAILS", {"max_results": 1})

    def test_mocked_boundary_catches_a_post_even_if_the_guard_fails(self):
        # Sabotage both gates: the post must land on the mocked subprocess boundary, never a provider.
        with patch.object(backend, "require_remote_operator", return_value={"identity": "x"}), \
             patch.object(backend, "classify_composio_action", return_value=("read", "sabotaged")):
            self.call({}, "LINKEDIN_CREATE_LINKED_IN_POST", {"text": "must not post"})
        self.provider.assert_called_once()
        self.assertIn("LINKEDIN_CREATE_LINKED_IN_POST", self.provider.call_args.args[0])

    def test_guarded_refusals_never_touch_the_execution_boundary(self):
        for slug in ("LINKEDIN_CREATE_LINKED_IN_POST", "GMAIL_SEND_EMAIL", "TWITTER_RETWEET"):
            with self.assertRaises(HTTPException):
                self.call(TAILNET, slug, {"text": "x"})
        with self.assertRaises(HTTPException):
            self.call({"x-ttros-remote-pc": "1"}, "LINKEDIN_GET_MY_INFO")
        self.provider.assert_not_called()

    def test_caller_supplied_identity_headers_do_not_authenticate(self):
        forged_jwt = "eyJhbGciOiJub25lIn0.eyJlbWFpbCI6ImxpYW1kdWZmODhAZ21haWwuY29tIn0."
        cases = [
            ({"x-ttros-remote-pc": "1", "cf-access-jwt-assertion": forged_jwt}, "Cloudflare Access assertion missing or invalid"),
            ({**TAILNET, "cf-access-jwt-assertion": forged_jwt}, "Cloudflare Access assertion missing or invalid"),
            ({**TAILNET, "cf-connecting-ip": "203.0.113.9"}, "Cloudflare Access assertion missing or invalid"),
            ({**TAILNET, "tailscale-funnel-request": "?1"}, "Tailscale Funnel (public) requests are refused"),
            ({**TAILNET, "sec-fetch-site": "cross-site"}, "cross-site request refused"),
            ({"tailscale-user-login": "liamduff88@gmail.com"}, "missing Remote PC request header"),
            ({"x-ttros-remote-pc": "1", "x-forwarded-user": "liamduff88@gmail.com", "x-ttros-operator": "liam"}, "no verified operator identity"),
        ]
        with patch.dict("os.environ", {"TTROS_DASHBOARD_ACCESS_AUTH_DOMAIN": "timetorevenue.cloudflareaccess.com"}):
            for headers, fragment in cases:
                self.assertRefused(headers, "LINKEDIN_GET_MY_INFO", fragment)
        self.provider.assert_not_called()


if __name__ == "__main__":
    unittest.main()

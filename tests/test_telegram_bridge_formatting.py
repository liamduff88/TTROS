import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


BRIDGE = Path(__file__).parents[1] / "connectors" / "telegram_bridge" / "telegram_bridge.py"


def load_bridge():
    module_name = "telegram_bridge_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, BRIDGE)
    module = importlib.util.module_from_spec(spec)
    with patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "read_text", return_value="TELEGRAM_BOT_TOKEN=fake-token\n"), \
         patch.object(Path, "mkdir"):
        spec.loader.exec_module(module)
    return module


class TelegramBridgeFormattingTests(unittest.TestCase):
    @staticmethod
    def make_vault(root):
        (root / "inbox/source_notes").mkdir(parents=True)
        (root / "inbox/README.md").write_text(
            "---\nid: ttros-brain-inbox\ntype: intake\n---\n# Inbox\n",
            encoding="utf-8",
        )
        return root

    def test_submission_ack_timeout_is_short_and_independent_of_claude_execution(self):
        bridge = load_bridge()
        self.assertEqual(bridge.SUBMISSION_ACK_TIMEOUT_SECONDS, 20)
        with patch.object(bridge.urllib.request, "urlopen") as urlopen:
            response = urlopen.return_value.__enter__.return_value
            response.read.return_value = b'{"success":true,"accepted":true,"request_returned_before_completion":true}'
            bridge.post_agent("/api/wsl/hermes", "/work claude bounded proof")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 20)

    def test_hermes_and_coordinated_codex_use_agent_response_timeout(self):
        bridge = load_bridge()
        cases = (
            "/work hermes inspect the routing decision",
            "/work codex inspect the route, then review it",
            "What is the best way to prioritise this work?",
        )
        for task in cases:
            with self.subTest(task=task), patch.object(bridge.urllib.request, "urlopen") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.read.return_value = b'{"success":true}'
                bridge.post_agent("/api/wsl/hermes", task)
            self.assertEqual(urlopen.call_args.kwargs["timeout"], bridge.AGENT_RESPONSE_TIMEOUT_SECONDS)

    def test_status_formats_composite_backend_state_and_stays_inline(self):
        bridge = load_bridge()
        backend_status = {
            "success": True,
            "state": "healthy",
            "bridge": {"state": "running"},
            "queue": {"state": "healthy", "items": 12, "actionable": 0},
            "runner": {"state": "on_demand_idle"},
            "codex": {"state": "ready"},
            "hermes": {"state": "ready"},
            "local_agent_route": {"state": "ready"},
            "last_route_failure": None,
        }
        message = {"chat": {"id": 123}, "text": "/status"}
        with patch.object(bridge, "load_allowed", return_value={"operator_chat_ids": [123], "pilots": {}}), \
             patch.object(bridge, "get_backend_status", return_value=backend_status) as backend, \
             patch.object(bridge, "post_agent") as post_agent, \
             patch.object(bridge, "send") as send:
            bridge.handle_message(message)

        backend.assert_called_once_with()
        post_agent.assert_not_called()
        body = send.call_args.args[1]
        self.assertIn("Overall: healthy", body)
        self.assertIn("Bridge: live handler; backend_process=running; mode=operator", body)
        self.assertIn("Backend: ready", body)
        self.assertIn("Queue: healthy; items=12; actionable=0", body)
        self.assertIn("Runner: on_demand_idle", body)
        self.assertIn("Codex: ready", body)
        self.assertIn("Hermes: ready", body)
        self.assertIn("Local-agent readiness: ready", body)
        self.assertIn("Last route failure: none recorded", body)
        self.assertTrue(send.call_args.kwargs["preserve_format"])

    def test_status_backend_unavailable_is_bounded_and_degraded(self):
        bridge = load_bridge()
        message = {"chat": {"id": 123}, "text": "/status"}
        with patch.object(bridge, "load_allowed", return_value={"operator_chat_ids": [123], "pilots": {}}), \
             patch.object(bridge, "get_backend_status", side_effect=TimeoutError), \
             patch.object(bridge, "send") as send:
            bridge.handle_message(message)

        body = send.call_args.args[1]
        self.assertIn("Overall: degraded", body)
        self.assertIn("Backend: unavailable", body)
        self.assertIn("Queue: unknown", body)
        self.assertIn("Last route failure: backend_status_TimeoutError", body)
        self.assertNotIn("123", body)

    def test_work_codex_uses_existing_queued_hermes_intake_and_fixture_source(self):
        bridge = load_bridge()
        result = {
            "success": True,
            "requested_target": "queue",
            "selected_route": "async_queue",
            "output": "PASS\nWork item ID: AOS-2026-9999\nStatus: agent_todo",
        }
        with patch.object(bridge, "post_agent", return_value=result) as post_agent, \
             patch.object(bridge, "send"):
            bridge.handle_operator(123, "/work codex create the local proof", source="route_repair_fixture")

        post_agent.assert_called_once_with(
            "/api/wsl/hermes",
            "/work codex create the local proof",
            source="route_repair_fixture",
        )

    def test_operator_inbox_text_and_forward_capture_without_queue_or_external_send(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as temp:
            vault = self.make_vault(Path(temp))
            messages = (
                {"message_id": 7, "date": 1784491200, "chat": {"id": 123}, "text": "/inbox Héllo\nworld"},
                {"message_id": 8, "date": 1784491201, "chat": {"id": 123}, "text": "Forwarded content", "forward_origin": {"type": "hidden_user"}},
            )
            with patch.object(bridge.business_brain, "BUSINESS_BRAIN_ROOT", vault), \
                 patch.object(bridge, "load_allowed", return_value={"operator_chat_ids": [123], "pilots": {}}), \
                 patch.object(bridge, "post_agent") as post_agent, \
                 patch.object(bridge, "api") as api, \
                 patch.object(bridge, "send") as send:
                for message in messages:
                    bridge.handle_message(message)
                    bridge.handle_message(message)

            post_agent.assert_not_called()
            api.assert_not_called()
            self.assertEqual(send.call_count, 4)
            self.assertEqual(send.call_args_list[0].args[1], "Captured ✓")
            self.assertEqual(send.call_args_list[1].args[1], "Already captured ✓")
            notes = sorted((vault / "inbox/source_notes").glob("tg_*.md"))
            self.assertEqual(len(notes), 2)
            bodies = "\n".join(path.read_text(encoding="utf-8") for path in notes)
            self.assertIn("Héllo\nworld", bodies)
            self.assertIn("Forwarded content", bodies)
            self.assertNotIn("chat_id", bodies)
            self.assertNotIn("123", bodies)
            self.assertNotIn("fake-token", bodies)

    def test_operator_document_capture_reuses_attachment_download_and_never_queues(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as temp:
            vault = self.make_vault(Path(temp))
            message = {
                "message_id": 9,
                "date": 1784491202,
                "chat": {"id": 123},
                "caption": "/capture supporting file",
                "document": {"file_id": "safe-file", "file_name": "../../brief?.txt", "mime_type": "text/plain"},
            }
            with patch.object(bridge.business_brain, "BUSINESS_BRAIN_ROOT", vault), \
                 patch.object(bridge, "_download_telegram_file", return_value=b"attachment body") as download, \
                 patch.object(bridge, "post_agent") as post_agent:
                result = bridge.capture_operator_message(message)

            download.assert_called_once_with("safe-file")
            post_agent.assert_not_called()
            self.assertEqual(result.attachment_path.read_bytes(), b"attachment body")
            self.assertTrue(result.attachment_path.resolve().is_relative_to((vault / "inbox/source_notes").resolve()))
            self.assertIn("supporting file", result.path.read_text(encoding="utf-8"))

    def test_voice_audio_is_retained_with_honest_local_transcription_fallback(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as temp:
            vault = self.make_vault(Path(temp))
            message = {
                "message_id": 10,
                "date": int(datetime(2026, 7, 19, tzinfo=timezone.utc).timestamp()),
                "chat": {"id": 123},
                "caption": "/inbox",
                "voice": {"file_id": "voice-file", "mime_type": "audio/ogg"},
            }
            with patch.object(bridge.business_brain, "BUSINESS_BRAIN_ROOT", vault), \
                 patch.object(bridge, "_download_telegram_file", return_value=b"OggSfixture"), \
                 patch.dict(bridge.os.environ, {}, clear=True), \
                 patch.object(bridge, "post_agent") as post_agent:
                result = bridge.capture_operator_message(message)

            post_agent.assert_not_called()
            self.assertEqual(result.attachment_path.read_bytes(), b"OggSfixture")
            note = result.path.read_text(encoding="utf-8")
            self.assertIn("content_type: voice", note)
            self.assertIn("transcription_status:", note)
            self.assertIn("unavailable", note)
            self.assertIn("transcription is unavailable", note)

    def test_queue_create_backend_output_is_preserved(self):
        bridge = load_bridge()
        output = "\n".join([
            "PASS",
            "",
            "Work item ID:",
            "- AOS-2026-0014",
            "",
            "Owner:",
            "- revenue",
            "",
            "Status:",
            "- agent_todo",
            "",
            "Next action:",
            "- Review or claim the local queue item.",
            "",
            "Token usage:",
            "- no agent invocation",
        ])
        result = {
            "success": True,
            "requested_target": "queue",
            "selected_route": "local_queue",
            "output": output,
        }

        summary = bridge.summarize_agent_result(result)
        self.assertEqual(summary, output)

        with patch.object(bridge, "api") as api:
            bridge.send(123, summary, preserve_format=bridge.is_queue_backend_result(result))

        api.assert_called_once()
        self.assertEqual(api.call_args.args[1]["text"], output)

    def test_non_queue_backend_output_still_uses_compact_closeout(self):
        bridge = load_bridge()
        result = {
            "success": True,
            "requested_target": "hermes",
            "selected_route": "hermes_coordinator",
            "output": "PASS\nVerbose backend output",
        }

        summary = bridge.summarize_agent_result(result)

        self.assertNotEqual(summary, result["output"])
        self.assertIn("Files touched:", summary)
        self.assertIn("Token usage:", summary)

    def test_completed_queue_output_is_compact_and_lists_documents_to_attach(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = root / "queue" / "receipts" / "AOS-2026-0139.md"
            artifact = root / "workflows" / "queue_artifacts" / "proof.md"
            receipt.parent.mkdir(parents=True)
            artifact.parent.mkdir(parents=True)
            receipt.write_text("PASS\n", encoding="utf-8")
            artifact.write_text("proof\n", encoding="utf-8")
            setattr(bridge, "WORKSPACE", root)
            output = "\n".join([
                "PASS",
                "Work item title: Receipt delivery improvement",
                "Work item ID: AOS-2026-0139",
                "Final status: done",
                "Files touched: workflows/queue_artifacts/proof.md",
                "Validation: Created required local artifact.",
                "Artifacts: workflows/queue_artifacts/proof.md",
                "Token usage: unavailable from current CLI output",
            ])
            result = {"success": True, "requested_target": "queue", "output": output}

            summary = bridge.summarize_agent_result(result)
            docs = bridge.document_paths_for_completion(result, summary)

            self.assertTrue(summary.startswith("[AOS-2026-0139 — Receipt delivery improvement]\nWork item: AOS-2026-0139"))
            self.assertIn("Status: done", summary)
            self.assertIn("Work item: AOS-2026-0139", summary)
            self.assertIn("Final state: done", summary)
            self.assertIn(str(receipt), docs)
            self.assertIn(str(artifact), docs)

    def test_completion_documents_cannot_escape_allowlisted_directory_through_symlink(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = root / "queue" / "receipts"
            private = root / "connectors" / "private.md"
            receipts.mkdir(parents=True)
            private.parent.mkdir(parents=True)
            private.write_text("private fixture\n", encoding="utf-8")
            (receipts / "escape.md").symlink_to(private)
            setattr(bridge, "WORKSPACE", root)
            output = "PASS\nWork item ID: AOS-2026-0139\nValidation: queue/receipts/escape.md\nFinal status: done"

            docs = bridge.document_paths_for_completion({}, output)

            self.assertEqual(docs, [])

    def test_compact_completion_and_receipt_caption_are_title_first(self):
        bridge = load_bridge()
        output = "\n".join([
            "PASS",
            "Work item title: Gmail draft capability",
            "Work item ID: AOS-2026-0131",
            "Final status: done",
            "Files touched: workflows/queue_artifacts/gmail.md",
            "Validation: Gmail draft fixture passed.",
            "Token usage: unavailable from current CLI output",
        ])

        summary = bridge.compact_telegram_closeout(output, success=True)

        self.assertTrue(summary.startswith("[AOS-2026-0131 — Gmail draft capability]\nWork item: AOS-2026-0131"))
        self.assertIn("Status: done", summary)
        self.assertEqual(
            bridge._receipt_caption(summary),
            "AOS-2026-0131 — Gmail draft capability done receipt",
        )

    def test_receipt_caption_uses_work_item_title_when_body_has_no_bracket_header(self):
        bridge = load_bridge()
        body = "PASS\nWork item title: Telegram approval-routing test\nWork item ID: AOS-2026-0136"

        self.assertEqual(
            bridge._receipt_caption(body),
            "AOS-2026-0136 — Telegram approval-routing test done receipt",
        )

    def test_send_attaches_completion_documents_after_message_body(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            document = Path(tmp) / "receipt.md"
            document.write_text("PASS\n", encoding="utf-8")
            with patch.object(bridge, "api") as api, patch.object(bridge, "_multipart_api") as multipart:
                result = bridge.send(123, "[Receipt delivery improvement]\nWork item: AOS-2026-0139", preserve_format=True, document_paths=[str(document)])

        api.assert_called_once()
        multipart.assert_called_once()
        self.assertEqual(api.call_args.args[0], "sendMessage")
        self.assertEqual(multipart.call_args.args[0], "sendDocument")
        self.assertEqual(multipart.call_args.args[1]["caption"], "AOS-2026-0139 — Receipt delivery improvement done receipt")
        self.assertTrue(result["message_sent"])
        self.assertEqual(result["documents"], [{"path": str(document), "sent": True}])


if __name__ == "__main__":
    unittest.main()

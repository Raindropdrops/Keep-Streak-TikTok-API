import unittest
from unittest.mock import Mock, patch
import urllib.error
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import utils


class RecipientSafetyTests(unittest.TestCase):
    def test_message_pool_uses_vietnam_weekday_configuration(self):
        monday = datetime(2026, 6, 15, 4, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with patch.dict(
            utils.os.environ,
            {
                "MESSAGE_MON": "Lời chúc thứ Hai 1|Lời chúc thứ Hai 2",
                "MESSAGES": "Pool chung",
            },
            clear=True,
        ):
            self.assertEqual(
                utils._get_message_pool(monday),
                ["Lời chúc thứ Hai 1", "Lời chúc thứ Hai 2"],
            )

    def test_old_streak_history_is_not_reused_after_pool_changes(self):
        monday = datetime(2026, 6, 15, 4, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with patch.dict(
            utils.os.environ,
            {"MESSAGE_MON": "Chúc ngày mới vui vẻ|Chúc tuần mới thuận lợi"},
            clear=True,
        ):
            with patch("utils.get_vietnam_now", return_value=monday):
                with patch(
                    "utils._load_message_history",
                    return_value=[{"date": "2026-06-15", "message": "streak"}],
                ):
                    with patch("utils._save_message_history"):
                        message = utils.get_message_for_today()

        self.assertIn(
            message,
            ["Chúc ngày mới vui vẻ", "Chúc tuần mới thuận lợi"],
        )
        self.assertNotEqual(message, "streak")

    def test_weekly_pool_avoids_previous_message_from_same_pool(self):
        monday = datetime(2026, 6, 15, 4, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with patch.dict(
            utils.os.environ,
            {"MESSAGE_MON": "Câu thứ nhất|Câu thứ hai"},
            clear=True,
        ):
            with patch("utils.get_vietnam_now", return_value=monday):
                with patch(
                    "utils._load_message_history",
                    return_value=[
                        {"date": "2026-06-08", "message": "Câu thứ nhất"},
                        {"date": "2026-06-14", "message": "Tin Chủ Nhật"},
                    ],
                ):
                    with patch("utils._save_message_history"):
                        self.assertEqual(
                            utils.get_message_for_today(), "Câu thứ hai"
                        )

    def test_enabled_must_be_explicit_boolean_or_integer_one(self):
        self.assertTrue(utils.is_contact_enabled({"enabled": True}))
        self.assertTrue(utils.is_contact_enabled({"enabled": 1}))
        self.assertFalse(utils.is_contact_enabled({"enabled": "1"}))
        self.assertFalse(utils.is_contact_enabled({"enabled": "true"}))
        self.assertFalse(utils.is_contact_enabled({}))

    def test_duplicate_enabled_usernames_are_all_rejected(self):
        contacts = [
            {"username": "ExactUser", "enabled": True},
            {"username": "@exactuser", "enabled": True},
            {"username": "other", "enabled": True},
        ]

        safe = utils.get_safe_enabled_contacts(contacts)

        self.assertEqual([contact["username"] for contact in safe], ["other"])

    def test_recipient_requires_exact_username(self):
        contact = {
            "username": "right_user",
            "conversation_id": "expected-room",
            "user_id": "stale-global-id",
            "sec_uid": "stale-global-secuid",
        }

        self.assertFalse(
            utils.recipient_is_verified(contact, "wrong_user", "expected-room")
        )
        self.assertFalse(
            utils.recipient_is_verified(contact, "right_user", "wrong-room")
        )
        self.assertTrue(
            utils.recipient_is_verified(contact, "@RIGHT_USER", "expected-room")
        )

    def test_shared_display_name_is_not_a_safe_sidebar_label(self):
        first = {
            "username": "first",
            "display_name": "Same Name",
            "aliases": [],
            "enabled": True,
        }
        second = {
            "username": "second",
            "display_name": "Same Name",
            "aliases": [],
            "enabled": True,
        }

        labels = utils.get_contact_sidebar_labels(first, [first, second])

        self.assertNotIn("same name", labels)
        self.assertIn("first", labels)

    def test_cross_contact_alias_does_not_block_primary_labels(self):
        first = {
            "username": "first",
            "display_name": "First Display",
            "aliases": ["second", "Second Display", "old-first"],
            "enabled": True,
        }
        second = {
            "username": "second",
            "display_name": "Second Display",
            "aliases": [],
            "enabled": True,
        }

        labels = utils.get_contact_sidebar_labels(second, [first, second])

        self.assertIn("second", labels)
        self.assertIn("second display", labels)

    def test_sanitize_contact_aliases_removes_other_contacts_primary_labels(self):
        contacts = [
            {
                "username": "first",
                "display_name": "First Display",
                "aliases": ["second", "Second Display", "old-first", "old-first"],
                "enabled": True,
            },
            {
                "username": "second",
                "display_name": "Second Display",
                "aliases": [],
                "enabled": True,
            },
        ]

        changed = utils.sanitize_contact_aliases(contacts)

        self.assertTrue(changed)
        self.assertEqual(contacts[0]["aliases"], ["old-first"])

    @patch("utils.find_chat_nickname_elements")
    def test_duplicate_dom_nodes_in_same_chat_row_are_not_ambiguous(self, elements):
        first = Mock()
        first.text = "Right User"
        first.rect = {"y": 120}
        second = Mock()
        second.text = "Right User"
        second.rect = {"y": 123}
        elements.return_value = [first, second]
        contact = {
            "username": "right_user",
            "display_name": "Right User",
            "aliases": [],
            "enabled": True,
        }

        match, reason = utils.find_unique_chat_element(Mock(), contact, [contact])

        self.assertIs(match, first)
        self.assertIsNone(reason)

    @patch("utils.time.sleep")
    def test_screen_time_modal_is_unlocked_before_sending(self, _sleep):
        browser = Mock()
        body = Mock()
        body.text = "Bạn đã sẵn sàng đóng TikTok? Quay lại TikTok"
        passcode_input = Mock()
        passcode_input.is_displayed.return_value = True
        button = Mock()
        button.is_displayed.return_value = True
        browser.find_element.return_value = body

        def find_elements(by, selector):
            if by == utils.By.CSS_SELECTOR and selector == "input[type='password']":
                return [passcode_input]
            if by == utils.By.XPATH and "Quay lại TikTok" in selector:
                return [button]
            return []

        browser.find_elements.side_effect = find_elements

        with patch.dict(utils.os.environ, {"TIKTOK_SCREEN_TIME_PASSCODE": "9876"}):
            unlocked = utils._unlock_tiktok_screen_time_modal(browser)

        self.assertTrue(unlocked)
        passcode_input.send_keys.assert_called_once_with("9876")
        browser.execute_script.assert_called_once_with(
            "arguments[0].click();", button
        )

    def test_resolver_never_mutates_contact_matched_only_by_display_name(self):
        existing = {
            "username": "allowed_user",
            "display_name": "Shared Name",
            "aliases": [],
            "enabled": True,
        }
        contacts = [existing]

        resolved, is_new = utils.update_contact_in_list(
            contacts,
            {
                "username": "different_user",
                "display_name": "Shared Name",
                "profile_url": "https://www.tiktok.com/@different_user",
            },
        )

        self.assertTrue(is_new)
        self.assertEqual(existing["username"], "allowed_user")
        self.assertTrue(existing["enabled"])
        self.assertEqual(resolved["username"], "different_user")
        self.assertFalse(resolved["enabled"])

    def test_remote_contact_failure_returns_no_recipients(self):
        with patch.dict(
            utils.os.environ,
            {"API_BASE_URL": "https://example.invalid", "API_KEY": "secret"},
        ):
            with patch(
                "utils.urllib.request.urlopen",
                side_effect=urllib.error.URLError("offline"),
            ):
                self.assertEqual(utils.load_contacts(), [])

    def test_active_profile_extraction_never_scans_global_profile_links(self):
        browser = Mock()
        browser.find_elements.return_value = []

        profile = utils.extract_active_chat_profile(browser)

        self.assertEqual(profile, (None, None))
        requested_selectors = [
            call.args[1] for call in browser.find_elements.call_args_list
        ]
        self.assertNotIn("a[href*='/@']", requested_selectors)

    @patch("utils.time.sleep")
    @patch("utils._load_delivery_history", return_value={})
    @patch("utils.save_contacts")
    @patch("utils.handle_send_failure")
    @patch("utils.send_telegram_summary")
    @patch("utils.send_and_verify_message")
    @patch("utils.find_unique_chat_element", return_value=(None, "not_found"))
    @patch("utils.extract_conversation_id", return_value=None)
    @patch("utils.extract_active_chat_profile")
    @patch("utils.get_message_for_today", return_value="streak")
    @patch("utils.load_contacts")
    @patch("utils.is_logged_in", return_value=True)
    def test_send_flow_never_sends_when_active_username_is_wrong(
        self,
        _is_logged_in,
        load_contacts,
        _message,
        active_profile,
        _conversation_id,
        _find_chat,
        send_message,
        _telegram,
        _handle_failure,
        _save_contacts,
        _delivery_history,
        _sleep,
    ):
        load_contacts.return_value = [
            {
                "username": "right_user",
                "display_name": "Right User",
                "aliases": [],
                "enabled": True,
                "user_id": "global-id-that-used-to-match",
            }
        ]
        active_profile.return_value = (
            "https://www.tiktok.com/@wrong_user",
            "wrong_user",
        )
        browser = Mock()

        result = utils.send_messages_flow(browser, Mock())

        send_message.assert_not_called()
        self.assertEqual(result["sent_count"], 0)
        self.assertEqual(
            result["details"][0]["reason"], "not_found"
        )
        self.assertEqual(result["status"], "partial")

    @patch("utils.time.sleep")
    @patch("utils._load_delivery_history", return_value={})
    @patch("utils.save_contacts")
    @patch("utils.send_telegram_summary")
    @patch("utils.send_and_verify_message", return_value=(True, "success"))
    @patch("utils.extract_conversation_id", return_value=None)
    @patch(
        "utils.extract_active_chat_profile",
        return_value=("https://www.tiktok.com/@right_user", "right_user"),
    )
    @patch("utils.get_message_for_today", return_value="streak")
    @patch("utils.load_contacts")
    @patch("utils.is_logged_in", return_value=True)
    def test_send_flow_sends_once_after_exact_username_verification(
        self,
        _is_logged_in,
        load_contacts,
        _message,
        _active_profile,
        _conversation_id,
        send_message,
        _telegram,
        _save_contacts,
        _delivery_history,
        _sleep,
    ):
        load_contacts.return_value = [
            {
                "username": "right_user",
                "display_name": "Right User",
                "aliases": [],
                "enabled": True,
            }
        ]

        result = utils.send_messages_flow(Mock(), Mock())

        send_message.assert_called_once()
        self.assertEqual(result["sent_count"], 1)
        self.assertEqual(result["status"], "success")

    @patch("utils.time.sleep")
    @patch("utils.time.monotonic", side_effect=[0, 0, 2])
    @patch("utils._load_delivery_history", return_value={})
    @patch("utils.save_contacts")
    @patch("utils.send_telegram_summary")
    @patch("utils.send_and_verify_message", return_value=(True, "success"))
    @patch("utils.extract_conversation_id", return_value=None)
    @patch(
        "utils.extract_active_chat_profile",
        return_value=("https://www.tiktok.com/@first_user", "first_user"),
    )
    @patch("utils.get_message_for_today", return_value="hello")
    @patch("utils.load_contacts")
    @patch("utils.is_logged_in", return_value=True)
    def test_send_flow_deadline_leaves_remaining_contacts_for_catchup(
        self,
        _is_logged_in,
        load_contacts,
        _message,
        _active_profile,
        _conversation_id,
        send_message,
        _telegram,
        _save_contacts,
        _delivery_history,
        _monotonic,
        _sleep,
    ):
        load_contacts.return_value = [
            {
                "username": "first_user",
                "display_name": "First User",
                "aliases": [],
                "enabled": True,
            },
            {
                "username": "second_user",
                "display_name": "Second User",
                "aliases": [],
                "enabled": True,
            },
        ]

        with patch("config.SEND_FLOW_MAX_SECONDS", 1):
            result = utils.send_messages_flow(Mock(), Mock())

        send_message.assert_called_once()
        self.assertEqual(result["sent_count"], 1)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["details"][1]["reason"], "run_deadline_exceeded")

    def test_delivery_history_prevents_duplicate_send_on_catch_up_run(self):
        now = datetime(2026, 6, 13, 6, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        contact = {
            "username": "right_user",
            "last_sent": None,
            "last_sent_at": None,
        }
        history = {"2026-06-13": ["right_user"]}

        self.assertTrue(utils.contact_was_sent_today(contact, history, now))

    def test_historical_naive_runner_timestamp_is_treated_as_utc(self):
        now = datetime(2026, 6, 13, 6, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        contact = {
            "username": "right_user",
            "last_sent": "success",
            "last_sent_at": "2026-06-12T22:30:00",
        }

        self.assertTrue(utils.contact_was_sent_today(contact, {}, now))

    def test_mark_contact_sent_today_persists_vietnam_date(self):
        now = datetime(2026, 6, 13, 4, 5, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        contact = {"username": "right_user"}
        with TemporaryDirectory() as temp_dir:
            history_path = Path(temp_dir) / "delivery_history.json"
            with patch("utils.DELIVERY_HISTORY_FILE", str(history_path)):
                utils.mark_contact_sent_today(contact, {}, now)
                saved = utils._load_delivery_history()

        self.assertEqual(saved, {"2026-06-13": ["right_user"]})
        self.assertEqual(contact["last_sent"], "success")
        self.assertEqual(contact["last_sent_at"], now.isoformat())

    @patch("utils.time.sleep")
    @patch("utils.dismiss_blocking_overlays")
    @patch(
        "utils.wait_for_verified_recipient",
        return_value=(True, (None, "right_user", None)),
    )
    @patch(
        "utils.send_and_verify_message",
        side_effect=[(False, "click_intercepted"), (True, "success")],
    )
    def test_retry_reverifies_recipient_before_second_attempt(
        self,
        send_message,
        verify_recipient,
        dismiss_overlay,
        _sleep,
    ):
        contact = {"username": "right_user"}
        with patch("config.MAX_RETRIES_PER_CONTACT", 2):
            result = utils.send_to_verified_contact(
                Mock(), Mock(), contact, "hello"
            )

        self.assertEqual(result, (True, "success"))
        self.assertEqual(send_message.call_count, 2)
        self.assertEqual(verify_recipient.call_count, 4)
        self.assertGreaterEqual(dismiss_overlay.call_count, 3)


if __name__ == "__main__":
    unittest.main()

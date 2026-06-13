import unittest
from unittest.mock import Mock, patch
import urllib.error

import utils


class RecipientSafetyTests(unittest.TestCase):
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
            result["details"][0]["reason"], "recipient_not_verified"
        )

    @patch("utils.time.sleep")
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


if __name__ == "__main__":
    unittest.main()

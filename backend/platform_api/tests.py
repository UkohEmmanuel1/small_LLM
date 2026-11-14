from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import APIKey, Conversation


class PlatformAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="tester", password="a-secure-test-password-123"
        )
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.client = APIClient()

    def test_health_is_public(self):
        self.assertEqual(self.client.get("/api/health/").status_code, 200)

    def test_api_key_authentication(self):
        _, raw = APIKey.issue(self.user)
        response = self.client.get("/v1/models", HTTP_AUTHORIZATION=f"Bearer {raw}")
        self.assertEqual(response.status_code, 200)

    def test_revoked_api_key_is_rejected(self):
        key, raw = APIKey.issue(self.user)
        key.revoked_at = timezone.now()
        key.save(update_fields=["revoked_at"])
        response = self.client.get("/v1/models", HTTP_AUTHORIZATION=f"Bearer {raw}")
        self.assertEqual(response.status_code, 401)

    def test_conversations_are_private(self):
        Conversation.objects.create(user=self.user, title="Private")
        other = get_user_model().objects.create_user(
            username="other", password="another-secure-password-123"
        )
        other_token, _ = Token.objects.get_or_create(user=other)
        response = self.client.get(
            "/api/conversations/", HTTP_AUTHORIZATION=f"Token {other_token.key}"
        )
        self.assertEqual(len(response.data["results"]), 0)

    def test_api_key_cannot_manage_account_credentials(self):
        _, raw = APIKey.issue(self.user)
        response = self.client.get("/api/keys/", HTTP_AUTHORIZATION=f"Bearer {raw}")
        self.assertEqual(response.status_code, 403)

    def test_registration_rejects_short_password(self):
        response = self.client.post(
            "/api/auth/register/",
            {"username": "newuser", "password": "short"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_registration_rejects_non_string_username_and_invalid_email(self):
        bad_username = self.client.post(
            "/api/auth/register/",
            {"username": ["not", "a", "username"], "password": "a-secure-password-123"},
            format="json",
        )
        bad_email = self.client.post(
            "/api/auth/register/",
            {"username": "newuser", "email": "not-an-email", "password": "a-secure-password-123"},
            format="json",
        )
        self.assertEqual(bad_username.status_code, 400)
        self.assertEqual(bad_email.status_code, 400)

    def test_registration_creates_account_and_token(self):
        response = self.client.post(
            "/api/auth/register/",
            {"username": "newuser", "email": "NEW@EXAMPLE.COM", "password": "a-secure-password-123"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["token"])
        self.assertEqual(response.data["user"]["email"], "new@example.com")

    def test_chat_rejects_invalid_parameters_before_inference(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/v1/chat/completions",
            {"messages": [{"role": "user", "content": "hello"}], "temperature": 99},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("platform_api.views.httpx.Client")
    def test_chat_rejects_unknown_model_before_inference(self, client):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/v1/chat/completions",
            {"model": "some-other-model", "messages": [{"role": "user", "content": "hello"}]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        client.assert_not_called()

    @patch("platform_api.views.httpx.Client")
    def test_chat_checks_conversation_ownership_before_inference(self, client):
        owner = get_user_model().objects.create_user(
            username="owner", password="another-secure-password-123"
        )
        conversation = Conversation.objects.create(user=owner)
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/v1/chat/completions",
            {"messages": [{"role": "user", "content": "hello"}], "conversation_id": conversation.id},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        client.assert_not_called()

    @patch("platform_api.views.httpx.Client")
    def test_continuing_conversation_updates_activity_timestamp(self, client_class):
        conversation = Conversation.objects.create(user=self.user)
        old_timestamp = timezone.now() - timedelta(days=2)
        Conversation.objects.filter(pk=conversation.pk).update(updated_at=old_timestamp)
        self.client.force_authenticate(self.user)

        client = MagicMock()
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "id": "chatcmpl-test",
            "choices": [{"message": {"role": "assistant", "content": "Hello back"}}],
        }
        client.__enter__.return_value = client
        client.post.return_value = response
        client_class.return_value = client

        result = self.client.post(
            "/v1/chat/completions",
            {
                "messages": [{"role": "user", "content": "hello"}],
                "conversation_id": conversation.pk,
            },
            format="json",
        )
        conversation.refresh_from_db()
        self.assertEqual(result.status_code, 200)
        self.assertGreater(conversation.updated_at, old_timestamp)

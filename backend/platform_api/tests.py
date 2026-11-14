from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from .models import APIKey, Conversation

class PlatformAPITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="a-secure-test-password-123")
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
        other = get_user_model().objects.create_user(username="other", password="another-secure-password-123")
        other_token, _ = Token.objects.get_or_create(user=other)
        response = self.client.get("/api/conversations/", HTTP_AUTHORIZATION=f"Token {other_token.key}")
        self.assertEqual(len(response.data["results"]), 0)

    def test_api_key_cannot_manage_account_credentials(self):
        _, raw = APIKey.issue(self.user)
        response = self.client.get("/api/keys/", HTTP_AUTHORIZATION=f"Bearer {raw}")
        self.assertEqual(response.status_code, 403)

    def test_registration_rejects_short_password(self):
        response = self.client.post("/api/auth/register/", {"username": "newuser", "password": "short"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_chat_rejects_invalid_parameters_before_inference(self):
        self.client.force_authenticate(self.user)
        response = self.client.post("/v1/chat/completions", {
            "messages": [{"role": "user", "content": "hello"}], "temperature": 99
        }, format="json")
        self.assertEqual(response.status_code, 400)

    @patch("platform_api.views.httpx.Client")
    def test_chat_checks_conversation_ownership_before_inference(self, client):
        owner = get_user_model().objects.create_user(username="owner", password="another-secure-password-123")
        conversation = Conversation.objects.create(user=owner)
        self.client.force_authenticate(self.user)
        response = self.client.post("/v1/chat/completions", {
            "messages": [{"role": "user", "content": "hello"}], "conversation_id": conversation.id
        }, format="json")
        self.assertEqual(response.status_code, 404)
        client.assert_not_called()

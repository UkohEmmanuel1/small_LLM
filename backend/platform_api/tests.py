from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from .models import APIKey, Conversation

class PlatformAPITests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='tester',password='test-password-123')
        self.client=APIClient()
    def test_health_is_public(self):
        self.assertEqual(self.client.get('/api/health/').status_code,200)
    def test_api_key_authentication(self):
        key,raw=APIKey.issue(self.user)
        response=self.client.get('/v1/models',HTTP_AUTHORIZATION=f'Bearer {raw}')
        self.assertEqual(response.status_code,200)
    def test_conversations_are_private(self):
        Conversation.objects.create(user=self.user,title='Private')
        other=get_user_model().objects.create_user(username='other',password='test-password-123')
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get('/api/conversations/').data['count'] if isinstance(self.client.get('/api/conversations/').data,dict) else len(self.client.get('/api/conversations/').data),0)

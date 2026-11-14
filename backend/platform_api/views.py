import httpx
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from .models import Conversation, Message
from .serializers import ConversationSerializer, ChatCompletionInputSerializer
from .permissions import IsAccountTokenUser

class HealthView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = []
    def get(self, request):
        return Response({"status": "ok", "service": "small_LLM Django API"})

class ModelsView(APIView):
    def get(self, request):
        return Response({"object": "list", "data": [{"id": settings.INFERENCE_MODEL, "object": "model", "owned_by": "small_LLM"}]})

class ChatCompletionsView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "inference"

    def post(self, request):
        serializer = ChatCompletionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        conversation = None
        conversation_id = data.get("conversation_id")
        if conversation_id is not None:
            if not request.user.is_authenticated:
                return Response({"error": {"message": "Authentication is required for saved conversations."}}, status=401)
            conversation = get_object_or_404(Conversation, pk=conversation_id, user=request.user)

        prompt = data["messages"]
        if sum(len(item["content"]) for item in prompt) > settings.MAX_PROMPT_CHARS:
            return Response({"error": {"message": "Prompt exceeds the configured size limit."}}, status=413)
        payload = {
            "model": settings.INFERENCE_MODEL, "messages": prompt,
            "temperature": data["temperature"],
            "max_tokens": min(data["max_tokens"], settings.MAX_OUTPUT_TOKENS), "stream": False,
        }
        try:
            with httpx.Client(timeout=httpx.Timeout(settings.INFERENCE_TIMEOUT_SECONDS, connect=10)) as client:
                upstream = client.post(settings.INFERENCE_URL, json=payload)
            upstream.raise_for_status()
            result = upstream.json()
            answer = result["choices"][0]["message"]["content"]
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Empty model response")
        except httpx.TimeoutException:
            return Response({"error": {"message": "Inference timed out. Please retry."}}, status=504)
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            return Response({"error": {"message": "The inference service is unavailable or returned an invalid response."}}, status=503)

        if conversation is not None:
            last_user = next((m for m in reversed(prompt) if m["role"] == "user"), None)
            if last_user:
                Message.objects.create(conversation=conversation, role="user", content=last_user["content"])
            Message.objects.create(conversation=conversation, role="assistant", content=answer)
            if conversation.title == "New conversation" and last_user:
                conversation.title = last_user["content"][:157] + ("..." if len(last_user["content"]) > 157 else "")
                conversation.save(update_fields=["title", "updated_at"])
        return Response(result)

class ConversationListCreateView(generics.ListCreateAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAccountTokenUser]
    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user).prefetch_related("messages")
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class ConversationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAccountTokenUser]
    http_method_names = ["get", "delete", "head", "options"]
    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user).prefetch_related("messages")

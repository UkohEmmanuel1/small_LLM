from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import APIKey
from .permissions import IsAccountTokenUser

class APIKeyListCreateView(APIView):
    permission_classes = [IsAccountTokenUser]
    def get(self, request):
        rows = APIKey.objects.filter(user=request.user).order_by("-created_at")
        return Response([{
            "id": key.id, "name": key.name, "prefix": key.prefix,
            "created_at": key.created_at, "last_used_at": key.last_used_at,
            "revoked": bool(key.revoked_at),
        } for key in rows])
    def post(self, request):
        name = str(request.data.get("name", "Default key")).strip()[:80] or "Default key"
        key, raw = APIKey.issue(request.user, name)
        return Response({
            "id": key.id, "name": key.name, "key": raw,
            "warning": "Copy this key now. It will not be shown again.",
        }, status=status.HTTP_201_CREATED)

class APIKeyRevokeView(APIView):
    permission_classes = [IsAccountTokenUser]
    def delete(self, request, pk):
        key = get_object_or_404(APIKey, user=request.user, pk=pk)
        if not key.revoked_at:
            key.revoked_at = timezone.now()
            key.save(update_fields=["revoked_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

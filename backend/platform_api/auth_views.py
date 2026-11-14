from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

class RegistrationThrottle(AnonRateThrottle):
    scope = "registration"

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [RegistrationThrottle]

    def post(self, request):
        username = str(request.data.get("username", "")).strip()
        email = str(request.data.get("email", "")).strip().lower()
        password = request.data.get("password", "")
        if len(username) < 3 or len(username) > 150:
            return Response({"detail": "Username must be between 3 and 150 characters."}, status=400)
        if not isinstance(password, str):
            return Response({"detail": "A valid password is required."}, status=400)
        User = get_user_model()
        if User.objects.filter(username__iexact=username).exists():
            return Response({"detail": "That username is already taken."}, status=400)
        if email and User.objects.filter(email__iexact=email).exists():
            return Response({"detail": "That email is already registered."}, status=400)
        user = User(username=username, email=email)
        try:
            validate_password(password, user=user)
        except ValidationError as exc:
            return Response({"detail": list(exc.messages)}, status=400)
        user.set_password(password)
        user.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": {"id": user.id, "username": user.username, "email": user.email}}, status=status.HTTP_201_CREATED)

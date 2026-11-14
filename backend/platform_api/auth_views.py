from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
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
        username = request.data.get("username", "")
        email = request.data.get("email", "")
        password = request.data.get("password", "")
        if not isinstance(username, str):
            return Response({"detail": "A valid username is required."}, status=400)
        username = username.strip()
        if len(username) < 3 or len(username) > 150:
            return Response({"detail": "Username must be between 3 and 150 characters."}, status=400)
        if email is None:
            email = ""
        if not isinstance(email, str):
            return Response({"detail": "A valid email address is required."}, status=400)
        email = email.strip().lower()
        if len(email) > 254:
            return Response({"detail": "Email address must be 254 characters or fewer."}, status=400)
        if email:
            try:
                validate_email(email)
            except ValidationError:
                return Response({"detail": "Enter a valid email address."}, status=400)
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
        try:
            with transaction.atomic():
                user.set_password(password)
                user.save()
                token = Token.objects.create(user=user)
        except IntegrityError:
            return Response({"detail": "That username or email is already registered."}, status=400)
        return Response({"token": token.key, "user": {"id": user.id, "username": user.username, "email": user.email}}, status=status.HTTP_201_CREATED)

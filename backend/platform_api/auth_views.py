from django.contrib.auth import get_user_model
from rest_framework import permissions,status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

class RegisterView(APIView):
 permission_classes=[permissions.AllowAny]
 authentication_classes=[]
 def post(self,request):
  username=str(request.data.get('username','')).strip()
  email=str(request.data.get('email','')).strip().lower()
  password=request.data.get('password','')
  if len(username)<3 or len(username)>150: return Response({'detail':'Username must be between 3 and 150 characters.'},status=400)
  if not isinstance(password,str) or len(password)<12: return Response({'detail':'Password must contain at least 12 characters.'},status=400)
  User=get_user_model()
  if User.objects.filter(username=username).exists(): return Response({'detail':'That username is already taken.'},status=400)
  if email and User.objects.filter(email=email).exists(): return Response({'detail':'That email is already registered.'},status=400)
  user=User.objects.create_user(username=username,email=email,password=password)
  token,_=Token.objects.get_or_create(user=user)
  return Response({'token':token.key,'user':{'id':user.id,'username':user.username,'email':user.email}},status=status.HTTP_201_CREATED)

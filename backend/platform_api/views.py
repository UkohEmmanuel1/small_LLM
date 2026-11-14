import httpx
from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Conversation, Message
from .serializers import ConversationSerializer

class HealthView(APIView):
    permission_classes=[permissions.AllowAny]
    authentication_classes=[]
    def get(self,request): return Response({'status':'ok','service':'small_LLM Django API','inference':'self-hosted'})

class ModelsView(APIView):
    def get(self,request): return Response({'object':'list','data':[{'id':settings.INFERENCE_MODEL,'object':'model','owned_by':'small_LLM'}]})

class ChatCompletionsView(APIView):
    throttle_scope='inference'
    def post(self,request):
        messages=request.data.get('messages')
        if not isinstance(messages,list) or not messages or len(messages)>40:
            return Response({'error':{'message':'messages must be a non-empty array of at most 40 items'}},status=400)
        for item in messages:
            if not isinstance(item,dict) or item.get('role') not in ('system','user','assistant') or not isinstance(item.get('content'),str) or not item['content'].strip():
                return Response({'error':{'message':'Each message needs a supported role and non-empty content'}},status=400)
        max_tokens=min(int(request.data.get('max_tokens',512)),settings.MAX_OUTPUT_TOKENS)
        payload={'model':settings.INFERENCE_MODEL,'messages':messages,'temperature':float(request.data.get('temperature',0.7)),'max_tokens':max_tokens,'stream':False}
        try:
            with httpx.Client(timeout=httpx.Timeout(180,connect=15)) as client:
                upstream=client.post(settings.INFERENCE_URL,json=payload)
            upstream.raise_for_status()
            result=upstream.json()
        except httpx.TimeoutException:
            return Response({'error':{'message':'Inference timed out; retry shortly.'}},status=504)
        except (httpx.HTTPError,ValueError):
            return Response({'error':{'message':'Self-hosted inference is unavailable or returned an invalid response.'}},status=503)
        conversation_id=request.data.get('conversation_id')
        if request.user.is_authenticated and conversation_id:
            conversation=get_object_or_404(Conversation,pk=conversation_id,user=request.user)
            for item in messages[-2:]:
                Message.objects.create(conversation=conversation,role=item['role'],content=item['content'])
            answer=result.get('choices',[{}])[0].get('message',{}).get('content','')
            if answer: Message.objects.create(conversation=conversation,role='assistant',content=answer)
        return Response(result)

class ConversationListCreateView(generics.ListCreateAPIView):
    serializer_class=ConversationSerializer
    permission_classes=[permissions.IsAuthenticated]
    def get_queryset(self): return Conversation.objects.filter(user=self.request.user).prefetch_related('messages')
    def perform_create(self,serializer): serializer.save(user=self.request.user)

class ConversationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class=ConversationSerializer
    permission_classes=[permissions.IsAuthenticated]
    def get_queryset(self): return Conversation.objects.filter(user=self.request.user).prefetch_related('messages')

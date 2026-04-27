from django.urls import re_path
from .consumers import QueueConsumer

websocket_urlpatterns = [
    re_path(r'ws/queue/(?P<department>\w+)/$', QueueConsumer.as_asgi()),
]

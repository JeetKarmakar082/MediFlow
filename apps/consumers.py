import json
from channels.generic.websocket import AsyncWebsocketConsumer


class QueueConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.department = self.scope['url_route']['kwargs']['department']
        self.group_name = f"queue_{self.department}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connected', 'department': self.department,
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get('type') == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))

    async def queue_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'queue_update',
            'current_token': event.get('current_token'),
            'waiting_count': event.get('waiting_count'),
            'department': event.get('department'),
        }))

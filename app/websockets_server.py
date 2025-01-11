import socketio
import uuid
from app.models import create_user

# Create a Socket.IO server
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = socketio.ASGIApp(sio)

# Dictionary to store active connections
active_connections = {}


@sio.event
async def connect(sid, environ):
    headers = environ.get('headers', {})
    id = headers.get(b'id', b'').decode('utf-8')
    email = headers.get(b'email', b'').decode('utf-8')
    first_name = headers.get(b'first_name', b'').decode('utf-8')
    last_name = headers.get(b'last_name', b'').decode('utf-8')

    # Generate a random ID
    random_id = str(uuid.uuid4())

    # Store connection details
    active_connections[id] = {
        'sid': sid,
        'email': email,
        'first_name': first_name,
        'last_name': last_name
    }

    # Create the user in the database
    response = await create_user(id, email, first_name, last_name)
    if not response:
        await sio.disconnect(sid)
        return

    # Send confirmation message
    await sio.emit('socket-connected', {'id': random_id}, room=sid)


@sio.event
async def disconnect(sid):
    # Find and remove the disconnected user
    for user_id, conn in list(active_connections.items()):
        if conn['sid'] == sid:
            del active_connections[user_id]
            break
    await sio.emit('user-disconnected', {'sid': sid})


@sio.event
async def message(sid, data):
    # Broadcast the received message to all clients
    print(f'Message received from {sid}: {data}')
    await sio.emit('message', {'message': data})

# Broadcast messages to all active connections


async def send_message_to_all(message: str):
    await sio.emit('broadcast', {'message': message})

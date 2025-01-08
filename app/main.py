import socketio
from app.models import create_user, get_tasks, fetch_active_tasks_by_user, create_task, toggle_task, edit_task, complete_task, delete_task, init_db_conns, close_db_conns
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json

# Create FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create a Socket.IO server
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app.mount("/ws/taskbar", socketio.ASGIApp(sio, socketio_path=""))
""" Different server potentially for another app.
sio2 = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*', logger=True, engineio_logger=True)
app.mount("/ws/test", socketio.ASGIApp(sio2, socketio_path=""))
"""

# Dictionary to store active connections
active_connections = {}


def search_associated_sid_by_id(sid: str):
    related_sids = []
    for c in active_connections:
        if c != sid and active_connections[sid]["id"] == active_connections[c]["id"]:
            related_sids.append(c)

    return related_sids


async def emitter_to_associated_sids(ev: str, sid_lst: list[str], data: dict):
    for sid in sid_lst:
        await sio.emit(ev, data, to=sid)


@app.get("/api/tasks")
async def tasks():
    was_fetched, data = await get_tasks()
    if was_fetched:
        return json.dumps(data)
    else:
        return {"message": "Could not fetch"}


@app.get("/api/tasks/by_id/{id}")
async def tasks_by_id(id: str):
    was_fetched, data = await fetch_active_tasks_by_user(id)
    if was_fetched:
        return data
    else:
        return {"error": data}


@sio.event
async def connect(sid, environ):
    query_string = environ.get("QUERY_STRING", "")

    import urllib.parse
    params = urllib.parse.parse_qs(query_string)

    id = params["id"][0]
    email = params["email"][0]
    first_name = params["first_name"][0]
    last_name = params["last_name"][0]

    # Store connection details
    active_connections[sid] = {
        'sid': sid,
        "id": id,
        'email': email,
        'first_name': first_name,
        'last_name': last_name
    }
    # Create the user in the database
    response = await create_user(id, email, first_name, last_name)
    if not response:
        await sio.disconnect(sid)
        return

    was_fetched, tasks_list = await fetch_active_tasks_by_user(id)

    if was_fetched:
        print("issuing refresher")
        await sio.emit('socket-connected', {
            'id': sid,
            "tasks": tasks_list
        }, to=sid)
    else:
        await sio.emit('socket-connected', {
            'id': sid,
            "tasks": []
        }, to=sid)


@sio.event
async def disconnect(sid):
    # Find and remove the disconnected user
    for user_id, conn in list(active_connections.items()):
        if conn['sid'] == sid:
            del active_connections[user_id]
            break
    await sio.emit('user-disconnected', {'sid': sid})


@sio.event
async def task_completed(sid, data):
    was_updated, err = await complete_task(json.loads(data))
    response = {"was_updated": was_updated, "message": err}

    if was_updated:
        await emitter_to_associated_sids(
            "related_task_deleted",
            search_associated_sid_by_id(sid),
            data
        )
    return response


@sio.event
async def task_create(sid, data):
    was_added, err = await create_task(active_connections[sid]["id"], json.loads(data))
    response = {"was_addded": was_added, "message": err}
    print("Creating new task")

    if was_added:
        await emitter_to_associated_sids(
            "new_task_created",
            search_associated_sid_by_id(sid),
            data
        )

    return response


@sio.event
async def task_toggle(sid, data):
    was_toggled, err = await toggle_task(json.loads(data))
    response = {"was_toggled": was_toggled, "message": err}
    if was_toggled:
        await emitter_to_associated_sids(
            "related_task_toggled",
            search_associated_sid_by_id(sid),
            data
        )

    return response


@sio.event
async def task_edit(sid, data):
    was_edited, err = await edit_task(json.loads(data))
    response = {"was_edited": was_edited, "message": err}

    if was_edited:

        await emitter_to_associated_sids(
            "related_task_edited",
            search_associated_sid_by_id(sid),
            data
        )

    return response


@sio.event
async def task_delete(sid, data):
    id = (json.loads(data))["id"]
    was_deleted, err = await delete_task(id)
    response = {"was_deleted": was_deleted, "message": err}

    if was_deleted:
        await emitter_to_associated_sids(
            "related_task_deleted",
            search_associated_sid_by_id(sid),
            data
        )
    return response


@app.on_event("startup")
async def startup():
    await init_db_conns()


@app.on_event("shutdown")
async def shutdown():
    await close_db_conns()

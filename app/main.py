import socketio
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import uuid4
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.models import create_user, get_non_completed_tasks, get_completed_tasks_by_uid, fetch_active_tasks_by_user, create_task, toggle_task, edit_task, complete_task, delete_task, init_db_conns, close_db_conns
from app.utility import duration_str_to_int, duration_int_to_str

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

async def midnight_task_refresh():
    user_ids = []
    timezone = ZoneInfo("Europe/Bucharest")
    now = datetime.now(timezone)
    now_datetime_formated = now.strftime("%Y-%m-%d %H:%M:%S")

    # get all the tasks that are not completed from db
    was_fetched, non_completed_tasks = await get_non_completed_tasks()

    # get last epoch time
    last_epoch_t = int(time.time() * 1000)

    # for each task:
    for t in non_completed_tasks:
        # save the id of the user we must try to send a refresher to.
        user_ids.append(t[11])

        # calculate duration int
        dur_int = duration_str_to_int(t[5])

        # exclude tasks that with total duration 0
        if dur_int == 0 and t[8] == 0:
            continue

        # update current task to new duration, completed status, last_modified_at, completed_at
        was_updated, err = await complete_task({
            "duration": duration_int_to_str(int((dur_int + last_epoch_t - t[8])/1000)),
            "completed_at": now_datetime_formated,
            "id": t[0],
            "last_modified_at": last_epoch_t
        })

        # insert a new task with the same properties with the exception of:
        was_created, err = await create_task(t[11], {
            "id": str(uuid4()),
            "title": t[1],
            "description": t[2],
            "created_at": now_datetime_formated,
            "completed_at": now_datetime_formated,
            "duration": "00:00:00",
            "category": t[6],
            "tags": t[7],
            "toggled_at": last_epoch_t if t[9] == 1 else 0,
            "is_active": t[9],
            "is_completed": 0,
            "last_modified_at": last_epoch_t,
        })

    # emit a refresher to all conected devices
    for sid in active_connections:
        uid = active_connections[sid]["id"]
        if (uid in user_ids):
            was_fetched, tasks_list = await fetch_active_tasks_by_user(uid)

            if was_fetched:
                print(f"issuing refresher to user id {uid}")
                await sio.emit("tasks_refresher", {
                    "id": sid,
                    "tasks": tasks_list
                }, to=sid)
            else:
                await sio.emit("tasks_refresher", {
                    "id": sid,
                    "tasks": []
                }, to=sid)



romania_tz = ZoneInfo("Europe/Bucharest")
scheduler = AsyncIOScheduler(timezone=romania_tz)
scheduler.add_job(midnight_task_refresh, "cron", hour="0", minute="0")
scheduler.start()


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
    was_fetched, data = await get_non_completed_tasks()
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
        "sid": sid,
        "id": id,
        "email": email,
        "first_name": first_name,
        "last_name": last_name
    }
    # Create the user in the database
    response = await create_user(id, email, first_name, last_name)
    if not response:
        await sio.disconnect(sid)
        return

    was_fetched, tasks_list = await fetch_active_tasks_by_user(id)

    if was_fetched:
        print("issuing refresher for reconnect")
        await sio.emit("socket_connected", {
            "id": sid,
            "tasks": tasks_list
        }, to=sid)
    else:
        await sio.emit("socket_connected", {
            "id": sid,
            "tasks": []
        }, to=sid)


@sio.event
async def disconnect(sid):
    # Find and remove the disconnected user
    for user_id, conn in list(active_connections.items()):
        if conn['sid'] == sid:
            del active_connections[user_id]
            break
    print(f"{sid} - disconnected")
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


@sio.event
async def get_completed_tasks(sid, data):
    now = datetime.now()
    now_formatted_start = now.strftime("%Y-%m-%d 00:00:00")
    now_formatted_end = now.strftime("%Y-%m-%d 23:59:59")
    dates = json.loads(data)

    if dates["start_date"]:
        year, month, day = dates["start_date"].split("-")
        date_start = datetime(year=int(year), month=int(month), day=int(day))
        now_formatted_start = date_start.strftime("%Y-%m-%d 00:00:00")
    if dates["end_date"]:
        year, month, day = dates["end_date"].split("-")
        date_end = datetime(year=int(year), month=int(month), day=int(day))
        now_formatted_end = date_end.strftime("%Y-%m-%d 23:59:59")

    was_fetched, data = await get_completed_tasks_by_uid(
        active_connections[sid]["id"], now_formatted_start, now_formatted_end)
    return data


@app.on_event("startup")
async def startup():
    await init_db_conns()


@app.on_event("shutdown")
async def shutdown():
    await close_db_conns()

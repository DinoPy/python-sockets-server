import aiosqlite
import asyncio

db_path = "app/db.db"
db_conns = []


async def init_db_conns(db_path="app/db.db", count=10):
    """
    Will start a pool of dabases saved in a global list

    :param db_path: string -  Takes the path to the database
    :param count: int -  Takes the number of connections to initialize, default 10
    """
    for i in range(count):
        db_conns.append({
            "in_use": False,
            "conn": await aiosqlite.connect(db_path),
        })


async def close_db_conns():
    """
    Will close all open connections in global db_conns list
    """
    for db in db_conns:
        await db["conn"].close()


def get_unused_db():
    """
    Will loop the list of db connections and return one that's labeled as unused.

    returns:
        tuple({in_use: bool, conn: db_connection}, index: int)
    """
    for i in range(len(db_conns)):
        if not db_conns[i]["in_use"]:
            db_conns[i]["in_use"] = True
            return (db_conns[i], i)
    asyncio.sleep(0.01)
    return get_unused_db()


def free_db(index: int):
    db_conns[index]["in_use"] = False


async def create_user(id: str, email: str, first_name: str, last_name: str):
    """
    Inserts a new user into the users table.

    :param user_id: User's unique ID (TEXT).
    :param first_name: User's first name (TEXT).
    :param last_name: User's last name (TEXT).
    :param email: User's email (TEXT).
    """

    db_obj, db_index = get_unused_db()

    try:
        async with db_obj["conn"].execute("""
            INSERT INTO users (id, first_name, last_name, email)
            VALUES (?, ?, ?, ?)
          """, (id, first_name, last_name, email)) as cursor:
            await db_obj["conn"].commit()
            return {id, email, first_name, last_name}

    except aiosqlite.IntegrityError as e:
        print(e.sqlite_errorname)
        if e.sqlite_errorname == "SQLITE_CONSTRAINT_PRIMARYKEY":
            return True
        print(f"Error: {
              e}. This might be due to a duplicate ID or other constraint violations.")
        return False

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

    finally:
        free_db(db_index)


async def get_tasks():
    """
    Will return all the tasks in the database

    return list
    """

    db_conn, db_index = get_unused_db()

    try:
        async with db_conn["conn"].execute("""
                SELECT * FROM tasks
            """) as cursor:
            data = await cursor.fetchall()
            return (True, data)
    except Exception as e:
        return (False, str(e))

    finally:
        free_db(db_index)


async def create_task(user_id, obj):
    """
    Insert a new task into the tasks table.

    :params - id - string.
    :params - dictionary: {
        title: string
        description: string
        created_at: string
        completed_at: string
        duration: string
        duration: string
        category: string - one of the categories saved
        tags: string - comma delimiated list of tags
        toggled_at: number - IAT time
        is_active: boolean
        is_completed: boolean
    }
    """

    db_obj, db_index = get_unused_db()

    try:
        async with db_obj["conn"].execute("""
        INSERT INTO tasks (
        	id,
            title,
            description,
            created_at,
            completed_at,
            duration,
            category,
            tags,
            toggled_at,
            is_active,
            is_completed,
            user_id
        ) VALUES (
                :id,
                :title,
                :description,
                :created_at,
                :completed_at,
                :duration,
                :category,
                :tags,
                :toggled_at,
                :is_active,
                :is_completed,
                :user_id
            )
        """, {
            "user_id": user_id,
            **obj
        }) as cursor:
            await db_obj["conn"].commit()
            return (True, "")

    except aiosqlite.IntegrityError as e:
        print(e)
        return (False, str(e))

    except Exception as e:
        print(e)
        return (False, str(e))

    finally:
        free_db(db_index)


async def toggle_task(obj):
    """
    Will toggle the given task to active

    params: dictionary - {
        uuid: string,
        toggled_at: integer
        is_active: boolean
        duration: string
    }
    """

    db_conn, db_index = get_unused_db()

    try:
        async with db_conn["conn"].execute("""
                UPDATE tasks SET
                is_active = :is_active,
                toggled_at =  :toggled_at,
                duration = :duration
                WHERE id = :uuid
            """, obj
                                           ) as cursor:
            await db_conn["conn"].commit()
            print(f"task id: {obj["uuid"]} was now toggled to {
                  obj["is_active"]}")
            return (True, "")
    except aiosqlite.IntegrityError as e:
        print(e)
        return (False, str(e))

    except Exception as e:
        print(e)
        return (False, str(e))
    finally:
        free_db(db_index)


async def fetch_active_tasks_by_user(id):
    """
    Queries the database and returns all active tasks of a given user.

    :params - id: string

    :returns - list of tasks
    """

    db_conn, db_index = get_unused_db()

    try:
        async with db_conn["conn"].execute("""
            SELECT *
            FROM tasks
            WHERE user_id = :id AND is_completed = 0
            """, {"id": id}
        ) as cursor:
            data = await cursor.fetchall()
            return (True, data)

    except Exception as e:
        print(e)
        return (False, str(e))
    finally:
        free_db(db_index)


async def complete_task(obj):
    """
    Will mark the given task as completed and

    :params - dict - {
        duration: string,
        completed_at: string,
        id: string
    }
    """

    db_conn, db_index = get_unused_db()

    try:
        async with db_conn["conn"].execute("""
            UPDATE tasks SET
            is_active = 0,
            is_completed = 1,
            duration = :duration,
            completed_at = :completed_at
            WHERE id = :id
            """, obj) as cursor:
            await db_conn["conn"].commit()
            return (True, "")
    except Exception as e:
        print(e)
        return (False, str(e))

    finally:
        free_db(db_index)


async def edit_task(obj):
    print(f"Object received on edit \n {obj}")
    """
    Will update the given task to given parameters

    :params - dictionary - {
        title: string,
        description: string,
        category: string,
        tags: string
    }
    """

    db_conn, db_index = get_unused_db()

    try:
        async with db_conn["conn"].execute("""
            UPDATE tasks SET
                title = :title,
                description = :description,
                category = :category,
                tags = :tags
            WHERE id = :id
            """, obj) as cursor:
            await db_conn["conn"].commit()
            return (True, "")

    except Exception as e:
        print(e)
        return (False, str(e))

    finally:
        free_db(db_index)


async def delete_task(uuid: str):
    """
    Delete the given task by id

    param: uuid: string
    """

    db_conn, db_index = get_unused_db()
    try:
        async with db_conn["conn"].execute("""
            DELETE FROM tasks
            WHERE id = :uuid
            """, {"uuid": uuid}) as cursor:
            await db_conn["conn"].commit()
            return (True, "")

    except Exception as e:
        print(e)
        return (False, str(e))

    finally:
        free_db(db_index)

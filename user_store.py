import json
import bcrypt
from pathlib import Path

FILE = Path("users.json")


def load_users():
    if not FILE.exists():
        return {}

    with open(FILE, "r") as f:
        return json.load(f)


def save_users(users):
    with open(FILE, "w") as f:
        json.dump(users, f, indent=4)


def user_exists(username):
    users = load_users()
    return username in users


def create_user(username, name, password):
    users = load_users()

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    users[username] = {
        "name": name,
        "password": hashed.decode()
    }

    save_users(users)

def authenticate(username, password):
    users = load_users()

    if username not in users:
        return False, None

    stored_hash = users[username]["password"].encode()

    if bcrypt.checkpw(password.encode(), stored_hash):
        return True, users[username]["name"]

    return False, None

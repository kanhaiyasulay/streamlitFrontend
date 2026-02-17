import uuid
from user_store import load_users

SESSION_FILE = "sessions.json"


def load_sessions():
    try:
        import json
        with open(SESSION_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_sessions(data):
    import json
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f, indent=4)


def create_session(username):
    sessions = load_sessions()

    token = str(uuid.uuid4())
    sessions[token] = username

    save_sessions(sessions)
    return token


def get_user_from_token(token):
    sessions = load_sessions()
    return sessions.get(token)


def delete_session(token):
    sessions = load_sessions()
    if token in sessions:
        del sessions[token]
        save_sessions(sessions)

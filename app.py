import warnings

warnings.filterwarnings(
    "ignore",
    message="st.cache is deprecated",
)


import streamlit as st
from user_store import authenticate, create_user, user_exists

from streamlit_cookies_manager import EncryptedCookieManager
from session_manager import create_session, get_user_from_token, delete_session
from user_store import load_users

cookies = EncryptedCookieManager(
    prefix="finops_",
    password="very-secret-demo-key"  # any random string
)

if not cookies.ready():
    st.stop()


st.set_page_config(page_title="FinOps Demo", layout="centered")

# ---------------- SESSION STATE ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user" not in st.session_state:
    st.session_state.user = None

if "register_mode" not in st.session_state:
    st.session_state.register_mode = False

if "pending_username" not in st.session_state:
    st.session_state.pending_username = ""


# ---------------- LOGIN PAGE ----------------
def login_page():
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Continue"):

        if not username or not password:
            st.warning("Please enter username and password")
            return

        # If user exists → authenticate
        if user_exists(username):
            ok, name = authenticate(username, password)

            if ok:
                st.session_state.logged_in = True
                st.session_state.user = name
                st.session_state.username = username

                token = create_session(username)
                cookies["session_token"] = token
                cookies.save()

                st.rerun()

            else:
                st.error("❌ Wrong password")

        # If user does NOT exist → go to registration
        else:
            st.session_state.register_mode = True
            st.session_state.pending_username = username
            st.rerun()


# ---------------- REGISTER PAGE ----------------
def register_page():
    st.title("🆕 Create New Account")

    username = st.session_state.pending_username
    st.write(f"Creating account for: **{username}**")

    full_name = st.text_input("Full Name")
    new_password = st.text_input("Create Password", type="password")

    if st.button("Create Account"):

        if not full_name or not new_password:
            st.warning("All fields are required")
            return

        # Save user to JSON
        create_user(username, full_name, new_password)
        token = create_session(username)
        cookies["session_token"] = token
        cookies.save()

        st.success("✅ User created successfully!")

        # Auto-login after creation
        st.session_state.logged_in = True
        st.session_state.user = full_name
        st.session_state.register_mode = False

        st.rerun()

    if st.button("⬅ Back to Login"):
        st.session_state.register_mode = False
        st.rerun()


# ---------------- MAIN APP ----------------
def main_app():
    st.sidebar.write(f"👋 Welcome, **{st.session_state.user}**")

    if st.sidebar.button("Logout"):
        # Get token stored in browser
        token = cookies.get("session_token")

        # Remove session from sessions.json
        if token:
            delete_session(token)

        # Clear cookie in browser
        cookies["session_token"] = ""
        cookies.save()

        # Clear Streamlit session
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.register_mode = False

        st.rerun()


    st.title("💰 FinOps Dashboard")
    st.write("Your demo content goes here.")
    st.info("You are successfully authenticated.")

# ---- AUTO LOGIN USING COOKIE ----
if not st.session_state.logged_in:
    token = cookies.get("session_token")

    if token:
        username = get_user_from_token(token)

        if username:
            users = load_users()
            st.session_state.logged_in = True
            st.session_state.user = users[username]["name"]
            st.session_state.username = username



# ---------------- ROUTING ----------------
if st.session_state.logged_in:
    main_app()
elif st.session_state.register_mode:
    register_page()
else:
    login_page()

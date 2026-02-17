import streamlit as st
import time


def run_chat_ui():

    # -----------------------------
    # Helpers (must be inside function)
    # -----------------------------
    def init_state():
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "assistant", "content": "Hi! I'm your Streamlit chatbot. Start chatting 😊"}
            ]

    def add_message(role, content):
        st.session_state.messages.append({"role": role, "content": content})

    def bubble_html(role: str, content: str) -> str:
        side = "right" if role == "user" else "left"
        who  = "user" if role == "user" else "assistant"
        return f'''
        <div class="msg-row {side}">
            <div class="bubble {who}">{content}</div>
        </div>
        '''

    def render_messages(container):
        with container:
            st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
            for msg in st.session_state.messages:
                st.markdown(bubble_html(msg["role"], msg["content"]), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    def simple_bot_reply(user_text, temperature):
        return f"**Temperature:** `{temperature}`\n\nYou said: {user_text}"


    # -----------------------------
    # CSS (must be inside function!)
    # -----------------------------
    st.markdown("""<style>
        .chat-wrap { display: flex; flex-direction: column; gap: 1.2rem; }
        .msg-row { display: flex; width: 100%; }
        .msg-row.left  { justify-content: flex-start; }
        .msg-row.right { justify-content: flex-end; }
        .bubble { max-width: 78%; padding: 8px 12px; border-radius: 14px; }
        .bubble.user { background: #d7eaff; }
        .bubble.assistant { background: #f0f0f0; }
    </style>""", unsafe_allow_html=True)


    # -----------------------------
    # Actual UI
    # -----------------------------
    init_state()

    st.title("💬 Chatbot")

    temperature = st.sidebar.slider(
        "Temperature", 0.0, 2.0, 0.7, 0.05
    )

    if st.sidebar.button("🧹 Clear chat"):
        st.session_state.messages = [
            {"role": "assistant", "content": "Chat cleared ✅"}
        ]
        st.rerun()

    chat_container = st.container()
    render_messages(chat_container)

    user_input = st.chat_input("Type your message...")

    if user_input:
        add_message("user", user_input)

        reply = simple_bot_reply(user_input, temperature)

        add_message("assistant", reply)

        st.rerun()
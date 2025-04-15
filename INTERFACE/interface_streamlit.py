import streamlit as st
import os
import sys

# Add ENGINE/ to path
engine_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ENGINE'))
sys.path.append(engine_path)

from chat_core import reply, load_memory

st.set_page_config(page_title="DragonZpyder Chat", layout="centered")

# Custom CSS for styling
st.markdown("""
<style>
body {
    background-color: #1e1e1e;
    color: #ffffff;
    font-family: 'Inter', sans-serif;
}
.chat-container {
    max-width: 800px;
    margin: auto;
    padding: 2rem 1rem 6rem;
}
.chat-bubble {
    padding: 1rem 1.2rem;
    border-radius: 1rem;
    margin: 0.5rem 0;
    max-width: 75%;
    line-height: 1.6;
    font-size: 16px;
    word-wrap: break-word;
}
.user {
    background-color: #2a2a2a;
    margin-left: auto;
    text-align: right;
}
.bot {
    background-color: #333333;
    margin-right: auto;
    text-align: left;
}
.input-container {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background-color: #1e1e1e;
    padding: 1rem 2rem;
    box-shadow: 0 -5px 15px rgba(0,0,0,0.2);
}
input[type="text"] {
    padding: 0.75rem 1rem;
    border-radius: 10px;
    border: 1px solid #444;
    width: 100%;
    background-color: #2a2a2a;
    color: #ffffff;
}
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("<h2 style='text-align: center;'>🧠 DragonZpyder Assistant</h2>", unsafe_allow_html=True)

# Load or initialize memory
if "memory" not in st.session_state:
    st.session_state.memory = load_memory()

# Display chat history
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

for i in range(0, len(st.session_state.memory), 2):
    user_msg = st.session_state.memory[i]["content"]
    bot_msg = st.session_state.memory[i+1]["content"] if i+1 < len(st.session_state.memory) else ""

    st.markdown(f'<div class="chat-bubble user"><strong>You:</strong><br>{user_msg}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="chat-bubble bot"><strong>DragonZpyder:</strong><br>{bot_msg}</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# Input box
with st.container():
    st.markdown('<div class="input-container">', unsafe_allow_html=True)
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input("Message", "", label_visibility="collapsed", placeholder="Type your message...")
        submitted = st.form_submit_button("Send")
        if submitted and user_input.strip():
            with st.spinner("DragonZpyder is thinking..."):
                bot_response = reply(user_input.strip())
                st.session_state.memory.append({"role": "user", "content": user_input.strip()})
                st.session_state.memory.append({"role": "assistant", "content": bot_response})
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

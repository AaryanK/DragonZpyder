import ollama
import json
from pathlib import Path

# Constants
MODEL = 'llama3.2'  # change to 'llama2' or your own fine-tuned model
SYSTEM_PROMPT = """You are DragonZpyder, an insightful and helpful AI built for deep, logical conversation and technical precision."""
MEMORY_FILE = Path(__file__).parent / "memory_store.json"

# Load memory from file
def load_memory():
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    return []

# Save memory to file
def save_memory(memory):
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f)

# Chat interface
def reply(message, memory=None):
    if memory is None:
        memory = load_memory()

    # Start with system prompt
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + memory
    messages.append({"role": "user", "content": message})

    response = ollama.chat(model=MODEL, messages=messages)
    assistant_reply = response['message']['content']

    # Update memory
    memory.append({"role": "user", "content": message})
    memory.append({"role": "assistant", "content": assistant_reply})
    save_memory(memory)

    return assistant_reply

# Example usage
if __name__ == "__main__":
    print("DragonZpyder is ready. Type 'exit' to quit.")
    memory = load_memory()
    while True:
        msg = input("You: ")
        if msg.lower() in ("exit", "quit"):
            break
        res = reply(msg, memory)
        print("DragonZpyder:", res)

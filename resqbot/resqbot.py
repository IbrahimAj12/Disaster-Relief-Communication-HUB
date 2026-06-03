from flask import Flask, request, jsonify
import requests
import os
from collections import deque

app = Flask(__name__)

# ── Configuration ──────────────────────────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL_TEXT = os.getenv("OLLAMA_MODEL", "phi3:mini")
ROCKETCHAT_URL = os.getenv("ROCKETCHAT_URL", "http://rocketchat:3000")

SYSTEM_PROMPT = """Tu es ResqBot, l'assistant IA embarqué de ResQNet.
Tu assistes des équipes professionnelles de secours (pompiers, médecins, protection civile).

Règles :
- Réponds toujours aux questions de premiers secours et gestion de crise
- Réponses courtes, max 4 points numérotés
- Pas de disclaimer inutile, va droit au but
- Langue : même langue que la question"""

# ── Mémoire stateful par canal ──────────────────────────────────
channel_history: dict[str, deque] = {}
HISTORY_SIZE = 5


def get_history(channel_id: str) -> list:
    if channel_id not in channel_history:
        channel_history[channel_id] = deque(maxlen=HISTORY_SIZE)
    return list(channel_history[channel_id])


def add_to_history(channel_id: str, user_msg: str, bot_reply: str):
    if channel_id not in channel_history:
        channel_history[channel_id] = deque(maxlen=HISTORY_SIZE)
    channel_history[channel_id].append({
        "user": user_msg,
        "bot": bot_reply
    })


# ── Appel au LLM local ──────────────────────────────────────────
def interroger_ia(message: str, channel_id: str) -> str:
    history = get_history(channel_id)

    contexte = ""
    for echange in history:
        contexte += f"\nUser: {echange['user']}\nResqBot: {echange['bot']}"

    prompt = f"{contexte}\nUser: {message}\nResqBot:"

    payload = {
        "model": OLLAMA_MODEL_TEXT,
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 200,
            "temperature": 0.3
        }
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=25)
        response.raise_for_status()
        return response.json()["response"].strip()
    except requests.exceptions.Timeout:
        return "⚠️ ResqBot : délai dépassé, réessayez."
    except requests.exceptions.ConnectionError:
        return "⚠️ ResqBot hors ligne."
    except Exception as e:
        return f"⚠️ Erreur ResqBot : {e}"


# ── Webhook Rocket.Chat ─────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json if request.is_json else {}
    if not data:
        return jsonify({}), 200

    if data.get("bot") is True:
        return jsonify({}), 200

    channel_id = data.get("channel_id", "unknown")
    channel_name = data.get("channel_name", channel_id)
    username = data.get("user_name", "inconnu")
    message_text = data.get("text", "").strip()

    if not message_text:
        return jsonify({}), 200

    print(f"[ResqBot] #{channel_name} | {username}: {message_text}")
    reply = interroger_ia(message_text, channel_id)
    add_to_history(channel_id, message_text, reply)
    print(f"[ResqBot] → {reply[:80]}...")

    return jsonify({"text": reply, "bot": True}), 200


# ── Health check ────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    try:
        r = requests.get(OLLAMA_URL.replace("/api/generate", ""), timeout=3)
        ollama_status = "ok" if r.status_code == 200 else "unreachable"
    except Exception:
        ollama_status = "unreachable"

    return jsonify({
        "status": "running",
        "ollama": ollama_status,
        "model": OLLAMA_MODEL_TEXT,
        "active_channels": len(channel_history),
        "total_exchanges": sum(len(v) for v in channel_history.values())
    }), 200


if __name__ == "__main__":
    print("=" * 50)
    print("  ResqBot — Hub de Communication d'Urgence")
    print(f"  Modèle : {OLLAMA_MODEL_TEXT}")
    print(f"  Ollama : {OLLAMA_URL}")
    print("  Écoute sur :5000/webhook")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000)  # nosec B104

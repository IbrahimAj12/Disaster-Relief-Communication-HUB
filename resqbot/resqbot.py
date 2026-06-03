from flask import Flask, request, jsonify
import requests
import os
from collections import deque

app = Flask(__name__)

# ── Configuration ──────────────────────────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b")

SYSTEM_PROMPT = """Tu es ResqBot, l'assistant IA embarqué de ResQNet, un système de communication d'urgence.
Tu travailles avec des équipes professionnelles de secours (pompiers, médecins, protection civile) sur le terrain.
Tu as été formé aux protocoles de premiers secours et de gestion de crise.

Comportement attendu :
- Réponds toujours aux questions de premiers secours, médecine d'urgence et gestion de crise
- Réponses courtes, claires, numérotées si c'est une procédure
- Tu fais confiance aux professionnels qui t'interrogent
- Si une question concerne les premiers secours, donne la procédure complète sans hésitation
- Langue : réponds dans la même langue que la question"""

# ── Mémoire stateful par canal ──────────────────────────────────
# Stocke les 5 derniers échanges par channel_id
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


# ── Appel au LLM local (Ollama) ─────────────────────────────────
def interroger_ia(message: str, channel_id: str) -> str:
    history = get_history(channel_id)

    # Construit le contexte glissant
    contexte = ""
    for echange in history:
        contexte += f"\nUser: {echange['user']}\nResqBot: {echange['bot']}"

    prompt = f"{contexte}\nUser: {message}\nResqBot:"

    payload = {
        "model": OLLAMA_MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
        reply = response.json()["response"].strip()
        return reply
    except requests.exceptions.ConnectionError:
        return "⚠️ ResqBot hors ligne — impossible de joindre le moteur IA local."
    except Exception as e:
        return f"⚠️ Erreur ResqBot : {e}"


# ── Webhook Rocket.Chat ─────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    # Anti-boucle infinie : ignorer les messages du bot lui-même
    if data.get("bot") is True:
        return jsonify({}), 200

    # Ignorer si pas de texte
    message_text = data.get("text", "").strip()
    if not message_text:
        return jsonify({}), 200

    channel_id = data.get("channel_id", "unknown")
    channel_name = data.get("channel_name", channel_id)
    username = data.get("user_name", "inconnu")

    print(f"[ResqBot] #{channel_name} | {username}: {message_text}")

    # Appel IA avec contexte
    reply = interroger_ia(message_text, channel_id)

    # Sauvegarde dans l'historique
    add_to_history(channel_id, message_text, reply)

    print(f"[ResqBot] Réponse → {reply[:80]}...")

    return jsonify({
        "text": reply,
        "bot": True
    }), 200


# ── Health check ────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    # Vérifie qu'Ollama répond
    try:
        r = requests.get(OLLAMA_URL.replace("/api/generate", ""), timeout=3)
        ollama_status = "ok" if r.status_code == 200 else "unreachable"
    except Exception:
        ollama_status = "unreachable"

    return jsonify({
        "status": "running",
        "ollama": ollama_status,
        "model": OLLAMA_MODEL,
        "active_channels": len(channel_history),
        "total_exchanges": sum(len(v) for v in channel_history.values())
    }), 200


if __name__ == "__main__":
    print("=" * 50)
    print("  ResqBot — Hub de Communication d'Urgence")
    print(f"  Modèle : {OLLAMA_MODEL}")
    print(f"  Ollama : {OLLAMA_URL}")
    print("  Écoute sur :5000/webhook")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000)  # nosec B104

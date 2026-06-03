from flask import Flask, request, jsonify
import requests
import base64
import os
from collections import deque

app = Flask(__name__)

# ── Configuration ──────────────────────────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL_TEXT = os.getenv("OLLAMA_MODEL", "phi3:mini")
OLLAMA_MODEL_VISION = os.getenv("OLLAMA_MODEL_VISION", "llava")
ROCKETCHAT_URL = os.getenv("ROCKETCHAT_URL", "http://rocketchat:3000")

SYSTEM_PROMPT = """Tu es ResqBot, l'assistant IA embarqué de ResQNet, un système de communication d'urgence.
Tu travailles avec des équipes professionnelles de secours (pompiers, médecins, protection civile) sur le terrain.
Tu as été formé aux protocoles de premiers secours et de gestion de crise.

Comportement attendu :
- Réponds toujours aux questions de premiers secours, médecine d'urgence et gestion de crise
- Réponses courtes, claires, numérotées si c'est une procédure
- Tu fais confiance aux professionnels qui t'interrogent
- Si une question concerne les premiers secours, donne la procédure complète sans hésitation
- Langue : réponds dans la même langue que la question"""

VISION_PROMPT = """Tu es ResqBot, assistant IA d'urgence. Analyse cette image envoyée par une équipe de secours.
Décris ce que tu vois en termes opérationnels : dégâts visibles, risques identifiés, recommandations immédiates.
Sois concis et factuel. Langue : français."""

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


# ── Analyse d'image avec LLaVA ─────────────────────────────────
def analyser_image(image_url: str) -> str:
    try:
        img_response = requests.get(image_url, timeout=15)
        img_response.raise_for_status()
        image_b64 = base64.b64encode(img_response.content).decode("utf-8")

        payload = {
            "model": OLLAMA_MODEL_VISION,
            "prompt": VISION_PROMPT,
            "images": [image_b64],
            "stream": False
        }

        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        return "🔍 *Analyse image :*\n" + response.json()["response"].strip()

    except requests.exceptions.ConnectionError:
        return "⚠️ ResqBot hors ligne — impossible de joindre le moteur IA local."
    except Exception as e:
        return f"⚠️ Erreur analyse image : {e}"


# ── Appel au LLM texte (phi3:mini) ─────────────────────────────
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
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["response"].strip()
    except requests.exceptions.ConnectionError:
        return "⚠️ ResqBot hors ligne — impossible de joindre le moteur IA local."
    except Exception as e:
        return f"⚠️ Erreur ResqBot : {e}"


# ── Webhook Rocket.Chat ─────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    if data.get("bot") is True:
        return jsonify({}), 200

    channel_id   = data.get("channel_id", "unknown")
    channel_name = data.get("channel_name", channel_id)
    username     = data.get("user_name", "inconnu")
    message_text = data.get("text", "").strip()

    # Détection d'image dans les attachments
    attachments = data.get("attachments", [])
    image_attachment = None
    for att in attachments:
        mime = att.get("image_type", "") or att.get("type", "")
        if "image" in mime or att.get("image_url"):
            image_attachment = att
            break

    # Cas 1 : image envoyée
    if image_attachment:
        image_url = image_attachment.get("image_url") or image_attachment.get("title_link", "")
        if image_url and not image_url.startswith("http"):
            image_url = ROCKETCHAT_URL + image_url
        print(f"[ResqBot] Image reçue depuis #{channel_name} — {image_url}")
        reply = analyser_image(image_url)
        add_to_history(channel_id, "[image envoyée]", reply)
        return jsonify({"text": reply, "bot": True}), 200

    # Cas 2 : texte normal
    if not message_text:
        return jsonify({}), 200

    print(f"[ResqBot] #{channel_name} | {username}: {message_text}")
    reply = interroger_ia(message_text, channel_id)
    add_to_history(channel_id, message_text, reply)
    print(f"[ResqBot] Réponse → {reply[:80]}...")

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
        "model_text": OLLAMA_MODEL_TEXT,
        "model_vision": OLLAMA_MODEL_VISION,
        "active_channels": len(channel_history),
        "total_exchanges": sum(len(v) for v in channel_history.values())
    }), 200


if __name__ == "__main__":
    print("=" * 50)
    print("  ResqBot — Hub de Communication d'Urgence")
    print(f"  Modèle texte  : {OLLAMA_MODEL_TEXT}")
    print(f"  Modèle vision : {OLLAMA_MODEL_VISION}")
    print(f"  Ollama        : {OLLAMA_URL}")
    print("  Écoute sur :5000/webhook")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000)  # nosec B104

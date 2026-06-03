# ResQNet — Hub de Communication d'Urgence

> Plateforme de communication **100% hors ligne** pour équipes de secours,
> avec assistant IA local intégré.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Machine locale                     │
│                                                     │
│  ┌─────────────┐    ┌──────────────┐                │
│  │ Rocket.Chat │───▶│   ResqBot    │                │
│  │  :3000      │    │  Flask :5000 │                │
│  └─────────────┘    └──────┬───────┘                │
│         │                  │ HTTP                   │
│  ┌─────────────┐    ┌──────▼───────┐                │
│  │   MongoDB   │    │    Ollama    │                │
│  │  (replica)  │    │ llama3.2:1b  │                │
│  └─────────────┘    └─────────────┘                │
│                                                     │
│  Réseau LAN uniquement — 0 dépendance Internet      │
└─────────────────────────────────────────────────────┘
```

## Stack

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| Messagerie | Rocket.Chat 6.3 | Communication temps réel |
| Base de données | MongoDB 6.0 | Persistance des messages |
| IA locale | LLaMA 3.2 1B via Ollama | Assistant urgence hors ligne |
| Middleware | Python Flask | Pont Rocket.Chat ↔ Ollama |
| Conteneurisation | Docker + Compose | Déploiement reproductible |
| CI/CD | GitHub Actions | Lint, build, health check |

## Démarrage rapide

```bash
# 1. Prérequis : Ollama installé et modèle disponible
ollama pull llama3.2:1b

# 2. Lancer toute la stack
docker compose up -d

# 3. Accéder à Rocket.Chat
# http://localhost:3000
# Créer un compte admin au premier lancement

# 4. Vérifier ResqBot
curl http://localhost:5000/health
```

## Configuration du Webhook dans Rocket.Chat

1. Administration → Intégrations → Nouveau webhook **sortant**
2. Canal : `#general` (ou tous les canaux publics)
3. Trigger Words : `SOS`
4. URL : `http://resqbot:5000/webhook`
5. Activer → Sauvegarder

## Fonctionnalité IA Stateful

ResqBot maintient un **historique glissant des 5 derniers échanges** par canal.
L'IA peut ainsi suivre l'évolution d'une situation complexe sans perdre le contexte.

```
User:    SOS comment faire un garrot ?
ResqBot: [instructions détaillées]

User:    et si le saignement continue ?
ResqBot: [réponse contextuelle — sait qu'on parle d'un garrot]
```

## Canaux pré-configurés

| Canal | Usage |
|-------|-------|
| `#alertes-generales` | Diffusion annonces critiques (read-only) |
| `#ops-secours` | Coordination équipes terrain |
| `#medical-triage` | Urgences sanitaires |
| `#logistique-vivres` | Stocks et convois |
| `#infra-sinistres` | Routes, bâtiments, dégâts |

## CI/CD Pipeline

```
push → lint (flake8 + bandit) → docker build → health check smoke test
```

Le pipeline valide que le code est propre et que le service démarre correctement
à chaque commit. Le déploiement en production reste **manuel et local** pour
garantir l'autonomie en zone sinistrée.

## Perspectives futures

- [ ] Vision multimodale (LLaMA 3.2 Vision) — analyse photos de dégâts
- [ ] Intégration IoT — capteurs déclenchant des alertes automatiques
- [ ] Migration vers Kubernetes (haute disponibilité multi-nœuds)
- [ ] RAG local — interrogation de protocoles d'urgence PDF

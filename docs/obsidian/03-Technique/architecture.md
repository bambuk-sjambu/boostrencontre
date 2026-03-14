# Architecture

#boostrencontre #architecture #technique #code

---

## Stack technique

| Composant | Technologie | Version | Role |
|-----------|-------------|---------|------|
| Langage | Python | 3.12 | Logique metier, serveur, automatisation |
| Framework web | FastAPI | derniere | API REST, pages HTML, websocket |
| Base de donnees | SQLite | via aiosqlite | Stockage async (comptes, logs, profil, settings) |
| Navigateur | Playwright + Chromium | derniere | Automatisation web, sessions persistantes |
| IA | OpenAI API | gpt-4o-mini | Generation de messages personnalises |
| Templates HTML | Jinja2 | derniere | Dashboard et page profil |
| Serveur ASGI | Uvicorn | derniere | Serveur HTTP sur port 8888 |

---

## Arborescence du code

```
boostrencontre/
├── main.py                         # Entrypoint uvicorn :8888
├── src/
│   ├── app.py                      # FastAPI : lifespan, middlewares, montage routes (~200L)
│   ├── bot_engine.py               # Re-exports pour compatibilite (~63L)
│   ├── database.py                 # SQLite async (tables, migrations, init)
│   ├── explorer.py                 # Agent explorateur : mappe les selecteurs
│   ├── session_manager.py          # Gestion sessions navigateur + profils persistants
│   ├── browser_utils.py            # Utilitaires Playwright (TipTap, send, editor, safe_goto)
│   ├── conversation_utils.py       # Rejection, filtrage UI, detection dernier message, delais
│   ├── chat_utils.py               # Detection du dernier expediteur dans un chat
│   ├── constants.py                # Constantes (OPENAI_MODEL, DESIRES, DESIRE_KEYWORDS)
│   ├── rate_limiter.py             # Limites journalieres (likes, messages, replies)
│   ├── scoring.py                  # Score de compatibilite profils (/100, 5 criteres)
│   ├── campaign_manager.py         # Gestion campagnes (CRUD, contacts, funnel, stats)
│   ├── routes/
│   │   ├── browser.py              # Routes navigateur (open, close, login, screenshot)
│   │   ├── actions.py              # Routes likes, messages, replies, auto-reply, job-status
│   │   ├── profile.py              # Routes profil IA (lecture, modification, enrichissement)
│   │   ├── templates.py            # Routes templates CRUD
│   │   ├── stats.py                # Route statistiques (par jour, par style, taux)
│   │   ├── conversations.py        # Routes conversation multi-tour
│   │   ├── campaigns.py            # Routes mode campagne
│   │   └── debug.py                # Routes debug (protegees par DEBUG=true)
│   ├── actions/
│   │   ├── likes.py                # Logique likes (orchestration follow/crush)
│   │   ├── messages.py             # Logique messages (run, discussions, recherche)
│   │   ├── replies.py              # Logique reponses (inbox, sidebar, unread, anti-doublon)
│   │   └── auto_reply.py           # Boucle veille auto-reply
│   ├── messaging/
│   │   ├── ai_messages.py          # Generation messages via OpenAI + prompts adaptatifs
│   │   ├── prompt_builder.py       # Construction prompts (recipient, desirs, base, system)
│   │   ├── approach_templates.py   # 13 templates d'approche par desir
│   │   └── conversation_manager.py # Conversation multi-tour (4 etapes, historique, transitions)
│   ├── models/
│   │   └── profile_schema.py       # 10 categories profil + validation
│   ├── metrics/
│   │   └── tracker.py              # Suivi metriques
│   ├── platforms/
│   │   ├── base.py                 # BasePlatform (ABC) : interface commune
│   │   ├── tinder.py               # TinderPlatform
│   │   ├── meetic.py               # MeeticPlatform
│   │   ├── selectors/
│   │   │   └── wyylde.py           # Selecteurs CSS Wyylde (module partage)
│   │   └── wyylde/
│   │       ├── __init__.py         # Exports du package
│   │       ├── platform.py         # WyyldePlatform (composition des mixins)
│   │       ├── profile.py          # WyyldeProfileMixin : lecture profil, bio, navigation
│   │       ├── messaging.py        # WyyldeMessagingMixin : envoi messages, "Lui ecrire"
│   │       ├── search.py           # WyyldeSearchMixin : filtres, resultats, navigation
│   │       ├── sidebar.py          # WyyldeSidebarMixin : sidebar chat, discussions
│   │       └── selectors.py        # Constantes CSS centralisees
│   ├── messaging/
│   │   ├── ai_messages.py          # Generation messages via OpenAI + MY_PROFILE + STYLES
│   │   ├── approach_templates.py   # 13 templates d'approche + gestion personnalisee
│   │   └── prompt_builder.py       # Construction des prompts (system + user)
│   ├── templates/
│   │   ├── index.html              # Dashboard principal
│   │   ├── profile.html            # Page profil IA utilisateur
│   │   ├── home.html               # Page d'accueil
│   │   └── bmc.html                # Page Business Model Canvas
│   └── static/                     # Fichiers statiques (CSS, JS, images)
├── docs/
│   ├── obsidian/                   # Documentation Obsidian (ce vault)
│   ├── wyylde_selectors.md         # Reference selecteurs Wyylde (auto-genere)
│   └── wyylde_raw.json             # Donnees brutes exploration
├── tests/
│   ├── test_app.py                 # Tests routes et API
│   ├── test_messaging.py           # Tests generation messages, reply, styles, profil
│   ├── test_platforms.py           # Tests heritage, URLs, methodes requises
│   ├── test_scoring.py             # Tests scoring de profils
│   ├── test_conversations.py       # Tests conversation multi-tour
│   ├── test_campaigns.py           # Tests mode campagne
│   └── ...                         # 366 tests au total
├── boostrencontre.db               # Base SQLite
├── requirements.txt                # Dependances Python
├── .env                            # Variables d'environnement (non commite)
└── venv/                           # Environnement virtuel Python
```

---

## Conventions de code

### Fichiers

- Chaque fichier fait moins de 500 lignes
- Un fichier = une responsabilite (routes, logique metier, plateforme, etc.)
- Les imports sont regroupes : stdlib, puis dependances externes, puis modules internes

### Async partout

- Toutes les operations I/O sont asynchrones (aiosqlite, Playwright async API)
- Les jobs longs sont lances via `asyncio.create_task()` avec polling du statut
- Les delais utilisent `asyncio.sleep()` (jamais `time.sleep()`)

### Nommage

- Fonctions et variables : `snake_case`
- Classes : `PascalCase`
- Constantes : `UPPER_SNAKE_CASE`
- Fichiers : `snake_case.py`

### Tests

- Lancer les tests apres chaque changement : `venv/bin/python -m pytest tests/ -v`
- 366 tests couvrent les routes, l'API, les messages IA, le profil, les styles et les plateformes
- Les tests utilisent des mocks pour Playwright et OpenAI (pas d'appels reels)

---

## Modules et interactions

### Diagramme simplifie

```
Dashboard (navigateur utilisateur)
    |
    v
FastAPI (app.py)
    |
    +-- routes/*.py          <-- Endpoints HTTP
    |       |
    |       v
    +-- actions/*.py         <-- Logique metier
    |       |
    |       +-- messaging/   <-- Generation IA (prompts, templates, OpenAI)
    |       |
    |       +-- platforms/   <-- Interactions avec les sites
    |       |       |
    |       |       v
    |       |   Playwright   <-- Navigateur Chromium
    |       |
    |       +-- scoring.py   <-- Calcul compatibilite
    |       +-- campaigns.py <-- Gestion campagnes
    |
    +-- database.py          <-- SQLite async
    +-- session_manager.py   <-- Profils navigateur
    +-- rate_limiter.py      <-- Limites journalieres
```

### Flux d'un message IA

1. L'utilisateur clique "Messages IA" dans le dashboard
2. La route `POST /api/messages/{platform}` recoit la requete
3. `actions/messages.py` lance un job async via `asyncio.create_task()`
4. Pour chaque profil du sidebar :
   a. `platforms/wyylde/sidebar.py` extrait le profil du sidebar
   b. `platforms/wyylde/profile.py` lit le profil complet (bio, infos, desirs)
   c. `actions/scoring.py` calcule le score de compatibilite
   d. `messaging/prompt_builder.py` construit le prompt avec profil utilisateur + destinataire + style
   e. `messaging/ai_messages.py` appelle OpenAI et filtre le resultat
   f. `platforms/wyylde/messaging.py` saisit et envoie le message
   g. `database.py` enregistre l'action dans `activity_log`
5. La route `GET /api/job-status/messages/{platform}` renvoie la progression

---

## Pattern mixin pour Wyylde

Le code Wyylde est organise en mixins pour eviter un fichier monolithique :

```python
class WyyldePlatform(
    WyyldeProfileMixin,
    WyyldeMessagingMixin,
    WyyldeSearchMixin,
    WyyldeSidebarMixin,
    BasePlatform
):
    """Composition des mixins pour la plateforme Wyylde."""
    pass
```

Chaque mixin apporte un groupe de methodes :
- `WyyldeProfileMixin` : lecture de profil, extraction bio, navigation
- `WyyldeMessagingMixin` : envoi de messages, "Lui ecrire", reply dans le chat
- `WyyldeSearchMixin` : filtres de recherche, resultats, navigation
- `WyyldeSidebarMixin` : sidebar chat, discussions, profils en ligne

Les selecteurs CSS sont centralises dans `selectors.py` pour faciliter la maintenance.

---

## bot_engine.py comme re-exports

Le fichier `bot_engine.py` sert de facade : il re-exporte les fonctions des modules `actions/` pour maintenir la compatibilite avec le code existant. Il ne contient pas de logique propre.

```python
# bot_engine.py (63 lignes)
from src.actions.likes import run_likes
from src.actions.messages import run_messages, message_discussions, message_from_search
from src.actions.replies import reply_to_inbox, reply_to_sidebar, reply_to_unread_sidebar
from src.actions.auto_reply import start_auto_reply, stop_auto_reply
# ... etc.
```

---

## Profils navigateur

Les profils navigateur sont stockes localement :

```
~/.boostrencontre/browser_profiles/{platform}/
```

Chaque plateforme a son propre repertoire contenant les cookies, le localStorage et les donnees de cache du navigateur Chromium. Cela permet de conserver les sessions entre les redemarrages.

Le repertoire est cree avec des permissions restrictives (`mode=0o700`).

---

Voir aussi : [[03-Technique/api-reference|Reference API]], [[03-Technique/securite-anti-ban|Securite et anti-ban]], [[01-Produit/vue-ensemble|Vue d'ensemble]]

#architecture #technique

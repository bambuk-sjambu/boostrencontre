# BoostRencontre

Bot d'automatisation pour sites de rencontre (likes, follow, crush, messages IA, reponses auto).

## Stack

- Python 3.12, FastAPI, Playwright (Chromium headless=false), aiosqlite, Jinja2
- Messages IA via OpenAI API (gpt-4o-mini)
- Dashboard web sur port 8888

## Architecture

```
boostrencontre/
├── main.py                          # Entrypoint uvicorn :8888
├── src/
│   ├── app.py                       # FastAPI config + middlewares + routers (~200 lignes)
│   ├── routes/
│   │   ├── browser.py               # Routes navigateur (open/close/login/screenshot)
│   │   ├── actions.py               # Routes likes/messages/replies/auto-reply/daily-stats
│   │   ├── profile.py               # Routes profil IA utilisateur
│   │   ├── templates.py             # Routes templates CRUD
│   │   ├── stats.py                 # Routes statistiques (par jour, par style, taux)
│   │   ├── conversations.py         # Routes conversation multi-tour
│   │   ├── campaigns.py             # Routes mode campagne
│   │   └── debug.py                 # Routes debug (uniquement si DEBUG=true)
│   ├── session_manager.py           # Gestion sessions navigateur + profils persistants
│   ├── browser_utils.py             # Utilitaires Playwright (TipTap, send, editor, safe_goto)
│   ├── conversation_utils.py        # Rejection, UI filter, detect last message, delais
│   ├── chat_utils.py                # Detect last sender
│   ├── constants.py                 # Constantes (OPENAI_MODEL, DESIRES, DESIRE_KEYWORDS)
│   ├── rate_limiter.py              # Limites journalieres (likes, messages, replies)
│   ├── scoring.py                   # Score de compatibilite profils (/100, 5 criteres)
│   ├── campaign_manager.py          # Gestion campagnes (CRUD, contacts, funnel, stats)
│   ├── actions/
│   │   ├── likes.py                 # run_likes (avec scoring + rate limiting)
│   │   ├── messages.py              # run_messages, message_discussions, message_from_search
│   │   ├── replies.py               # reply_to_inbox/sidebar, check_and_reply_unread
│   │   └── auto_reply.py            # auto_reply_loop, start/stop
│   ├── bot_engine.py                # Re-exports pour compatibilite (~63 lignes)
│   ├── database.py                  # SQLite async (10+ tables, migrations)
│   ├── explorer.py                  # Agent explorateur : mappe les selecteurs
│   ├── messaging/
│   │   ├── ai_messages.py           # Generation messages via OpenAI + prompts adaptatifs
│   │   ├── prompt_builder.py        # Construction prompts (recipient, desirs, system msg)
│   │   ├── approach_templates.py    # 13 templates d'approche par desir
│   │   └── conversation_manager.py  # Conversation multi-tour (4 etapes, historique)
│   ├── models/
│   │   └── profile_schema.py        # 10 categories profil + validation
│   ├── metrics/
│   │   └── tracker.py               # Suivi metriques
│   ├── platforms/
│   │   ├── base.py                  # BasePlatform (ABC)
│   │   ├── tinder.py                # TinderPlatform
│   │   ├── meetic.py                # MeeticPlatform
│   │   ├── selectors/
│   │   │   └── wyylde.py            # Selecteurs CSS Wyylde (module partage)
│   │   └── wyylde/                  # Package Wyylde (6 modules)
│   │       ├── __init__.py          # Re-export WyyldePlatform
│   │       ├── platform.py          # Classe principale (mixins + core)
│   │       ├── profile.py           # Extraction profil
│   │       ├── messaging.py         # Envoi messages
│   │       ├── search.py            # Recherche + filtres
│   │       ├── sidebar.py           # Chat sidebar
│   │       └── selectors.py         # Selecteurs CSS centralises
│   ├── templates/
│   │   ├── index.html               # Dashboard principal (stats, campagnes, conversations)
│   │   ├── profile.html             # Page profil IA
│   │   ├── home.html                # Page home
│   │   └── bmc.html                 # Page BMC
│   └── static/
├── docs/
│   ├── wyylde_selectors.md          # Reference selecteurs Wyylde (auto-genere)
│   ├── wyylde_raw.json              # Donnees brutes exploration
│   └── obsidian/                    # Documentation Obsidian (38 fichiers)
│       ├── 01-Produit/              # Presentation, plateformes, guide
│       ├── 02-Fonctionnalites/      # 9 features documentees
│       ├── 03-Technique/            # Architecture, API, securite
│       ├── 04-Tests/                # 22 cas de test + rapports
│       ├── 05-Suivi/                # Roadmap, changelog, decisions
│       └── 06-Communication/        # Pitch, features cles, FAQ
├── tests/
│   ├── test_app.py                  # 53 tests (routes, API, profil, settings)
│   ├── test_messaging.py            # 27 tests (generation messages, reply, styles)
│   ├── test_platforms.py            # 21 tests (heritage, URLs, methodes)
│   ├── test_bot_engine.py           # 18 tests (re-exports, orchestration)
│   ├── test_database.py             # 16 tests (SQLite async, CRUD)
│   ├── test_adaptive_messages.py    # 46 tests (prompts adaptatifs, desirs, recipient)
│   ├── test_scoring.py              # 36 tests (scoring /100, grades, styles)
│   ├── test_conversation_manager.py # 27 tests (multi-tour, etapes, transitions)
│   ├── test_conversation_utils.py   # 34 tests (rejection, UI filter, delais)
│   ├── test_campaigns.py            # 37 tests (campagnes, contacts, funnel)
│   ├── test_browser_utils.py        # 11 tests (MockPage, TipTap, send, safe_goto)
│   ├── test_session_manager.py      # 8 tests (sessions, check_login, close)
│   ├── test_rate_limiter.py         # 8 tests (limites journalieres)
│   ├── test_stats.py                # 11 tests (stats par style, par jour)
│   ├── test_no_double_reply.py      # 9 tests (anti-doublon reponses)
│   └── test_chat_utils.py           # 8 tests (detect last sender)
├── boostrencontre.db                # SQLite
├── requirements.txt
└── venv/
```

## Profils navigateur

- Stockes sur disque local : `~/.boostrencontre/browser_profiles/{platform}/`
- Persistent context Playwright = cookies + localStorage conserves entre sessions
- NE PLUS utiliser le disque externe (NTFS = problemes de locking)

## Plateformes supportees

| Plateforme | Statut | Fonctionnalites |
|------------|--------|-----------------|
| Wyylde     | Actif  | Follow + Crush + Messages IA via "Lui ecrire" + Reponses inbox |
| Tinder     | Base   | Like via bouton/clavier, matches, messages |
| Meetic     | Base   | Like shuffle, matches, messages |

## Securite

- `DASHBOARD_TOKEN` auto-genere au demarrage si non defini dans les variables d'environnement
- Routes debug (`/api/debug-*`, `/api/reload`, etc.) protegees par `DEBUG=true`
- Header `Content-Security-Policy` actif sur toutes les reponses

## Messages IA

### Profil utilisateur (`MY_PROFILE` dans ai_messages.py)
- Pseudo, type, age, location, description
- Sauvegarde en DB (`user_profile` table) et editable via `/profile`
- Utilise dans TOUS les prompts pour personnaliser les messages

### Styles de communication (8 styles)
- `auto` (IA choisit), `romantique`, `direct_sexe`, `humoristique`, `intellectuel`, `aventurier`, `mystérieux`, `complice`
- Selectionnable dans le dashboard via dropdown

### Generation
- Premier message : `generate_first_message(profile_info, style)` — personnalise selon bio du destinataire
- Reponse : `generate_reply_message(sender_name, conversation_text, style)` — rebondit sur la conversation
- Model : `gpt-4o-mini`, max_tokens=300

## Wyylde — Selecteurs cles (source: docs/wyylde_selectors.md)

### Navigation
- Dashboard : `https://app.wyylde.com/fr-fr` (redirige vers /dashboard/wall)
- Mailbox : `https://app.wyylde.com/fr-fr/mailbox/inbox`
- Chat sidebar : toujours visible a droite (x > 1000)

### Profils chat sidebar
- Selecteur : `button[class*="bg-neutral-lowest"][class*="cursor-pointer"]`
- Contient : pseudo + type (Homme/Femme/Couple) + age

### Page profil membre
- Suivre : `button:has(svg[data-icon="user-plus"])` (x > 300)
- Lui ecrire : `button:has(svg[data-icon="paper-plane"])` texte "Lui ecrire" (x > 300)
- Crush : `button:has(svg[data-icon="wyylde-crush"])` (x > 300)
- Nom : `button.max-w-full.font-poppins.text-base`

### Envoi de message (flow "Lui ecrire")
1. Cliquer "Lui ecrire" sur le profil → popup modale s'ouvre
2. **2 editeurs TipTap** sur la page : modale (512px wide) + chat sidebar (222px wide)
3. Cibler le plus large avec `page.mouse.click(center_x, center_y)` (PAS JS focus)
4. Taper avec `keyboard.type(message, delay=25)`
5. Bouton envoi : `svg[data-icon="paper-plane-top"]` (PAS "paper-plane")
6. Le bouton est disabled tant que l'editeur est vide, enabled apres saisie

### Discussions non lues (sidebar droit)
- Section "N Discussions non lues" : bouton jaune-vert `BG=rgb(236,255,107)` a x~1006, w~259
- Section repliee par defaut — cliquer le bouton jaune pour deplier
- Une fois depliee, les pseudos non lus apparaissent comme petits boutons (~152x22) a x~1022
- Entre le header "non lues" et le header "Discussions en cours" (BG fonce)
- Chaque pseudo non lu est accompagne d'un tag "NOUVEAUX"
- Cliquer un pseudo ouvre le chat popup (editeur TipTap + contenu conversation)
- Le panneau tout a droite (x~1265) a aussi un bouton `#headerOpenedTalks` "Discussions non lues" — c'est le header du panneau, pas celui du chat sidebar
- Fonction : `reply_to_unread_sidebar()` dans actions/replies.py

### Reponse chat sidebar
- Editeur chat sidebar : TipTap a x > 600, plus petit (222px)
- Bouton envoi chat : `svg[data-icon="paper-plane-top"]` a x > 900

## API Endpoints

### Navigateur
- `POST /api/browser/{platform}` — Ouvrir navigateur + login manuel
- `GET /api/check-login/{platform}` — Verifier connexion
- `GET /api/screenshot/{platform}` — Screenshot page courante
- `POST /api/close/{platform}` — Fermer navigateur

### Actions
- `POST /api/likes/{platform}` — Lancer likes (body: `{profile_filter}`)
- `POST /api/messages/{platform}` — Envoyer messages IA (body: `{style}`)
- `POST /api/message-discussions/{platform}` — Envoyer messages aux discussions existantes
- `POST /api/message-search/{platform}` — Envoyer messages depuis la recherche
- `POST /api/replies/{platform}` — Repondre aux discussions non lues du sidebar (body: `{style}`)
- `POST /api/check-replies/{platform}` — Idem, synchrone (sans job async)
- `POST /api/auto-reply/{platform}` — Demarrer/arreter la boucle de reponse automatique
- `GET /api/job-status/{job_type}/{platform}` — Polling statut job async

### Profil IA
- `GET /profile` — Page web profil IA
- `GET /api/user-profile` — Lire profil IA utilisateur
- `POST /api/user-profile` — Modifier profil IA
- `POST /api/user-profile/enrich` — Enrichir profil via IA
- `GET /api/my-profile/{platform}` — Extraire profil depuis le site

### Templates
- `GET /api/templates` — Lister les templates d'approche
- `POST /api/templates` — Creer un template
- `DELETE /api/templates/{id}` — Supprimer un template

### Autres
- `POST /api/settings` — Sauvegarder parametres

### Debug (DEBUG=true uniquement)
- `POST /api/explore/{platform}` — Lancer l'agent explorateur
- `POST /api/reload` — Recharger les modules Python
- `GET /api/debug/{platform}` — Debug general
- `GET /api/debug-sidebar/{platform}` — Debug sidebar
- `GET /api/debug-chat/{platform}` — Debug chat
- `GET /api/debug-mailbox/{platform}` — Debug mailbox
- `GET /api/debug-unread-sidebar/{platform}` — Debug sidebar non lues
- `GET /api/debug-profile/{platform}` — Debug profil
- `POST /api/test-message/{platform}` — Test envoi message
- `POST /api/test-click/{platform}` — Test clic element
- `GET /api/test-sidebar-buttons/{platform}` — Test boutons sidebar

## Tests

```bash
venv/bin/python -m pytest tests/ -v
# 153 tests couvrant : routes, API, messages IA, profil, styles, plateformes, anti-doublon, chat utils
```

## Lancement

```bash
cd /media/stef/Photos\ -\ Sauv/DEV-JAMBU/boostrencontre
venv/bin/python main.py
# Dashboard : http://127.0.0.1:8888
```

## Variables d'environnement (.env)

- `OPENAI_API_KEY` — Cle API pour generation messages IA (gpt-4o-mini)
- `ANTHROPIC_API_KEY` — Cle API Anthropic (backup)
- `DASHBOARD_TOKEN` — Token d'acces au dashboard (auto-genere si non defini)
- `DEBUG` — Active les routes debug (default: false)
- `WYYLDE_MEMBER_ID` — ID membre Wyylde pour extraction profil propre

## Agent Swarm (7 agents paralleles)

Au debut de chaque session, proposer le lancement de ces 7 agents en parallele (audit/plan d'abord, puis implementation).

| # | Agent | Type | Scope |
|---|-------|------|-------|
| 1 | backend-dev | coder | API FastAPI, endpoints, DB SQLite, OpenAI, sessions Playwright |
| 2 | coder | coder | Modules plateformes, selecteurs CSS, DOM, chat popup, TipTap, sidebar, explorer |
| 3 | sparc-coord | planner | Orchestration SPARC, sprints, dependances inter-agents, coherence globale |
| 4 | researcher | researcher | Contenu & strategie — 13 templates messages/desirs, 8 styles, 10 categories profil |
| 5 | tester | tester | QA — tests routes, messaging, platforms, flux complets, non-regression CSS |
| 6 | security-manager | security-manager | Credentials, anti-ban, sanitisation inputs/outputs IA |
| 7 | reviewer | reviewer | Review croise, coherence templates/styles/prompts, validation dashboard |

### Organisation parallele
```
sparc-coord (orchestrateur)
    ├── backend-dev + coder     → dev en parallele
    ├── researcher              → contenu independant du code
    ├── security-manager        → audit continu
    └── tester + reviewer       → validation apres chaque sprint
```

### Workflow
1. **Phase 1 (audit)** : Tous en mode plan, audit code existant — aucune modification
2. **Phase 2 (implementation)** : Appliquer recommandations par sprint, coordonnes par sparc-coord
3. **Phase 3 (validation)** : tester + reviewer valident chaque sprint

## Conventions

- Fichiers < 500 lignes
- Async partout (aiosqlite, playwright async API)
- Jobs longs via asyncio.create_task avec polling
- Toujours lancer `POST /api/explore/{platform}` avant de coder de nouveaux selecteurs
- Lire `docs/{platform}_selectors.md` pour les selecteurs a jour
- Lancer les tests apres chaque changement
- Pas de secrets dans le code
- **JAMAIS `kill` sur un port** — ne jamais faire `lsof -ti:PORT | xargs kill` (risque de tuer Firefox ou d'autres apps)
- Proposer le lancement des 7 agents au debut de chaque session

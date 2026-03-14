# Reference API

#boostrencontre #api #endpoints #reference

---

## Authentification

Toutes les routes `/api/*` requierent un header d'authentification :

```
Authorization: Bearer {DASHBOARD_TOKEN}
```

Le token est genere automatiquement au demarrage ou peut etre defini via la variable d'environnement `DASHBOARD_TOKEN`.

---

## Gestion du navigateur

### Ouvrir un navigateur

```
POST /api/browser/{platform}
```

Ouvre un navigateur Chromium avec profil persistant et navigue vers la page de connexion de la plateforme.

**Parametres URL** : `platform` = tinder | meetic | wyylde

**Reponse** :
```json
{"status": "opening", "message": "Ouverture de wyylde... Le navigateur va s'ouvrir."}
```
ou
```json
{"status": "already_open", "platform": "wyylde"}
```

---

### Verifier la connexion

```
GET /api/check-login/{platform}
```

Verifie si l'utilisateur est connecte sur la plateforme. Si connecte, sauvegarde automatiquement les cookies de session.

**Reponse** :
```json
{"logged_in": true}
```

---

### Prendre un screenshot

```
GET /api/screenshot/{platform}
```

Capture un screenshot de la page courante du navigateur.

**Reponse** : image PNG (Content-Type: image/png)

---

### Fermer le navigateur

```
POST /api/close/{platform}
```

Ferme le navigateur et arrete l'auto-reply si actif.

**Reponse** :
```json
{"status": "closed"}
```

---

## Actions automatisees

### Lancer les likes

```
POST /api/likes/{platform}
```

Lance une session de likes (follow + crush sur Wyylde).

**Body** (optionnel) :
```json
{
    "profile_filter": "Couple F Bi"
}
```

**Reponse** :
```json
{"status": "started", "message": "Likes lances sur wyylde ! Regarde le navigateur."}
```

**Erreurs possibles** :
- `{"error": "not_connected", "message": "wyylde n'est pas connecte..."}` -- navigateur non ouvert
- `{"error": "not_logged_in", "message": "Tu n'es pas connecte sur wyylde..."}` -- non authentifie

---

### Envoyer des messages IA

```
POST /api/messages/{platform}
```

Envoie des premiers messages personnalises aux profils en ligne du sidebar.

**Body** (optionnel) :
```json
{
    "style": "humoristique"
}
```

**Styles disponibles** : auto, romantique, direct_sexe, humoristique, intellectuel, aventurier, mysterieux, complice

---

### Envoyer des messages aux discussions

```
POST /api/message-discussions/{platform}
```

Envoie des premiers messages aux contacts du sidebar "Discussions en cours".

**Body** (optionnel) :
```json
{
    "count": 5,
    "style": "auto"
}
```

---

### Envoyer des messages via recherche

```
POST /api/message-search/{platform}
```

Recherche des profils par filtres et envoie des premiers messages personnalises.

**Body** :
```json
{
    "count": 5,
    "style": "auto",
    "profile_type": "Couple F Bi",
    "desires": ["Gang bang", "Echangisme"],
    "approach_template": "On organise des soirees..."
}
```

| Champ | Type | Defaut | Description |
|-------|------|--------|-------------|
| `count` | int | 5 | Nombre de messages a envoyer |
| `style` | string | "auto" | Style de communication |
| `profile_type` | string | "" | Filtre par type de profil |
| `desires` | list | [] | Filtres par envies |
| `approach_template` | string | "" | Texte d'inspiration pour l'IA |

---

### Repondre aux non-lus (async)

```
POST /api/replies/{platform}
```

Lance une tache asynchrone pour repondre aux discussions non lues du sidebar.

**Body** (optionnel) :
```json
{
    "style": "complice"
}
```

---

### Repondre aux non-lus (synchrone)

```
POST /api/check-replies/{platform}
```

Execute les reponses aux non-lus de maniere synchrone (attend la fin avant de repondre).

**Reponse** :
```json
{
    "status": "done",
    "replied": [{"name": "PseudoX", "message": "..."}],
    "count": 2
}
```

---

### Auto-reply (veille)

```
POST /api/auto-reply/{platform}
```

Active ou desactive le mode veille auto-reply.

**Body** :
```json
{
    "action": "start",
    "interval": 60,
    "style": "auto"
}
```

| Champ | Type | Defaut | Description |
|-------|------|--------|-------------|
| `action` | string | "start" | "start" ou "stop" |
| `interval` | int | 60 | Secondes entre chaque scan |
| `style` | string | "auto" | Style de communication |

**Reponse (start)** :
```json
{"status": "started", "interval": 60}
```

**Reponse (stop)** :
```json
{"status": "stopped"}
```

---

### Statut des jobs

```
GET /api/job-status/{job_type}/{platform}
```

Polling du statut d'un job asynchrone.

**Types de jobs** : likes, messages, replies, discussion_msg, search_msg, browser

**Reponses possibles** :
```json
{"status": "running"}
```
```json
{"status": "idle"}
```
```json
{"status": "done", "count": 5, "sent": [...]}
```
```json
{"status": "error", "error": "message d'erreur"}
```

---

## Profil utilisateur

### Lire le profil IA

```
GET /api/user-profile
```

Retourne le profil IA et les 50 derniers messages envoyes.

**Reponse** :
```json
{
    "profile": {
        "pseudo": "MonPseudo",
        "type": "Couple hetero",
        "age": "35",
        "location": "Paris",
        "description": "...",
        "categories": {
            "passions": "voyages, photo...",
            "pratiques": "",
            "personnalite": "curieux, ouvert...",
            ...
        }
    },
    "messages_sent": [
        {
            "action": "message",
            "target_name": "PseudoX",
            "message_sent": "...",
            "created_at": "2026-03-10 14:32:00"
        }
    ]
}
```

---

### Modifier le profil IA

```
POST /api/user-profile
```

Met a jour le profil (identite + categories).

**Body** :
```json
{
    "pseudo": "MonPseudo",
    "type": "Couple hetero",
    "age": "35",
    "location": "Paris",
    "description": "Ma presentation...",
    "categories": {
        "passions": "voyages, photo...",
        "pratiques": "echangisme soft",
        "personnalite": "curieux, ouvert",
        "physique": "",
        "etudes_metier": "",
        "voyages": "Asie, Europe",
        "musique_culture": "",
        "sport": "running, yoga",
        "humour": "",
        "valeurs": "respect, authenticite"
    }
}
```

**Limites** : pseudo/type/age/location max 100 caracteres, description max 2000 caracteres.

---

### Enrichir le profil par IA

```
POST /api/user-profile/enrich
```

Utilise l'IA pour remplir automatiquement les categories vides a partir des messages envoyes.

**Body** : meme format que la modification de profil (optionnel, sinon utilise le profil courant)

**Reponse** :
```json
{
    "status": "enriched",
    "profile": { ... }
}
```

---

### Extraire son profil depuis le site

```
GET /api/my-profile/{platform}
```

Navigue vers le profil de l'utilisateur sur la plateforme et extrait les informations affichees.

Prerequis : variable `WYYLDE_MEMBER_ID` ou champ `member_id` dans le profil en base.

---

## Templates de message

### Lire les templates

```
GET /api/templates?desire=Gang%20bang
```

**Parametre** : `desire` (optionnel) -- filtre par categorie de desir

**Reponse** :
```json
{
    "templates": [
        {
            "id": 1,
            "desire": "Gang bang",
            "label": "Organisateur",
            "content": "On organise regulierement..."
        }
    ]
}
```

---

### Creer ou modifier un template

```
POST /api/templates
```

**Body** :
```json
{
    "desire": "Gang bang",
    "label": "Mon template",
    "content": "Contenu du template...",
    "id": null
}
```

Si `id` est fourni, le template existant est modifie. Sinon, un nouveau est cree.

**Limites** : desire max 100 caracteres, label max 200, content max 2000.

---

### Supprimer un template

```
DELETE /api/templates/{template_id}
```

---

## Statistiques

### Obtenir les statistiques

```
GET /api/stats/{platform}?days=7
```

**Parametre** : `days` (optionnel, defaut 7, max 90)

**Reponse** :
```json
{
    "today": {
        "messages_sent": 3,
        "replies_sent": 5,
        "likes": 15,
        "follows": 12,
        "crushes": 8
    },
    "period": {
        "messages_sent": 20,
        "replies_received": 8,
        "response_rate": 40.0
    },
    "by_style": [
        {"style": "humoristique", "sent": 5, "responses": 3, "rate": 60.0},
        {"style": "auto", "sent": 10, "responses": 3, "rate": 30.0}
    ],
    "by_day": [
        {"date": "2026-03-10", "messages": 3, "replies": 5, "likes": 15}
    ],
    "recent_conversations": [
        {
            "name": "PseudoX",
            "last_message": "Ton profil...",
            "timestamp": "2026-03-10 14:32:00",
            "replied": true
        }
    ]
}
```

---

## Parametres

### Sauvegarder les parametres

```
POST /api/settings
```

**Body** :
```json
{
    "likes_per_session": 50,
    "messages_per_session": 3,
    "delay_min": 3,
    "delay_max": 8
}
```

**Limites serveur** :
- likes_per_session : 1 - 500
- messages_per_session : 1 - 50
- delay_min : 0 - 60
- delay_max : 1 - 120

---

## Pages HTML

| URL | Description |
|-----|-------------|
| `GET /` | Dashboard principal |
| `GET /profile` | Page profil IA |
| `GET /home` | Page d'accueil |
| `GET /bmc` | Page Business Model Canvas |

---

## Routes debug (DEBUG=true uniquement)

| Route | Description |
|-------|-------------|
| `GET /api/debug/{platform}` | Capture les liens, boutons, images, cartes de la page |
| `GET /api/debug-sidebar/{platform}` | Inspecte le sidebar chat |
| `GET /api/debug-chat/{platform}?name=...` | Ouvre une discussion et inspecte le DOM |
| `GET /api/debug-mailbox/{platform}` | Inspecte la premiere conversation de la mailbox |
| `GET /api/debug-unread-sidebar/{platform}` | Inspecte les indicateurs non-lus du sidebar |
| `GET /api/test-sidebar-buttons/{platform}` | Teste la detection des boutons de discussion |
| `GET /api/debug-profile/{platform}` | Navigue vers un profil et capture les boutons/icones |
| `POST /api/test-click/{platform}` | Explore les resultats de recherche |
| `POST /api/test-message/{platform}` | Test pas a pas du flow d'envoi de message |
| `POST /api/explore/{platform}` | Lance l'agent explorateur complet |
| `POST /api/reload` | Hot-reload des modules Python sans redemarrage |

---

Voir aussi : [[02-Fonctionnalites/dashboard|Dashboard]], [[01-Produit/guide-utilisation|Guide d'utilisation]]

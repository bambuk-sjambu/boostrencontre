# Mode campagne

#boostrencontre #campagne #ciblage #funnel #feature

---

## Principe

Le mode campagne permet de creer des campagnes de prospection ciblees. Chaque campagne definit des criteres de ciblage (type de profil, tranche d'age, ville, desirs) et gere une file d'attente de contacts a travers un funnel de conversion.

---

## Creation d'une campagne

Une campagne est definie par :

| Champ | Type | Description |
|-------|------|-------------|
| `name` | string | Nom de la campagne (ex: "Couples Paris mars") |
| `platform` | string | Plateforme cible (wyylde, tinder, meetic) |
| `profile_type` | string | Type de profil cible (ex: "Couple F Bi") |
| `age_min` | int | Age minimum |
| `age_max` | int | Age maximum |
| `location` | string | Ville ou region ciblee |
| `desires` | list | Liste des desirs cibles (ex: ["Echangisme", "Gang bang"]) |
| `style` | string | Style de communication pour les messages |
| `max_contacts` | int | Nombre maximum de contacts dans la file (defaut: 50) |

---

## Statuts de campagne

| Statut | Description |
|--------|-------------|
| `draft` | Campagne creee mais pas encore lancee |
| `active` | Campagne en cours, les contacts sont traites |
| `paused` | Campagne mise en pause, reprend ou elle s'est arretee |
| `completed` | Tous les contacts ont ete traites ou le maximum est atteint |

---

## Funnel de contacts

Chaque contact dans une campagne passe par un funnel de statuts :

```
pending --> contacted --> replied --> conversation --> met / rejected / skipped
```

| Statut | Description |
|--------|-------------|
| `pending` | Contact identifie, en attente de premier message |
| `contacted` | Premier message envoye |
| `replied` | Le contact a repondu au moins une fois |
| `conversation` | Conversation active (plusieurs echanges) |
| `met` | Rencontre effectuee (marque manuellement) |
| `rejected` | Contact ayant exprime un refus ou detection de rejet |
| `skipped` | Contact ignore (score trop bas, profil incomplet, etc.) |

### Transitions automatiques

- `pending` vers `contacted` : apres envoi du premier message
- `contacted` vers `replied` : quand une reponse est detectee dans le sidebar ou la mailbox
- `replied` vers `conversation` : apres 3 echanges bidirectionnels
- `contacted` vers `rejected` : si detection de pattern de rejet
- Tout statut vers `skipped` : si le score du profil est inferieur a 40 (grade D)

### Transitions manuelles

- `conversation` vers `met` : l'utilisateur marque le contact comme rencontre
- Tout statut vers `skipped` : l'utilisateur decide d'ignorer le contact

---

## Statistiques de campagne

Chaque campagne dispose de statistiques detaillees :

| Metrique | Calcul |
|----------|--------|
| Taux de reponse | `replied / contacted * 100` |
| Taux de conversion | `conversation / contacted * 100` |
| Taux de rencontre | `met / contacted * 100` |
| Funnel complet | Repartition des contacts par statut |

---

## Execution d'une campagne

### Etape par etape

1. **Recherche de profils** : le bot applique les filtres de la campagne sur la page de recherche de la plateforme
2. **Scoring** : chaque profil trouve est score. Les profils de grade D sont marques `skipped`
3. **Ajout a la file** : les profils eligibles (grade A, B ou C) sont ajoutes a la file avec le statut `pending`
4. **Envoi de messages** : le bot traite les contacts `pending` un par un, genere un message personnalise et l'envoie
5. **Suivi** : les reponses sont detectees automatiquement et les statuts sont mis a jour

### Limites

- Le nombre de contacts par campagne est plafonne par `max_contacts`
- Les limites journalieres de la plateforme s'appliquent (messages, likes, etc.)
- Une campagne peut etre mise en pause et reprise a tout moment

---

## Endpoints API

### Creer une campagne

```
POST /api/campaigns
```

**Body** :
```json
{
    "name": "Couples Paris mars",
    "platform": "wyylde",
    "profile_type": "Couple F Bi",
    "age_min": 25,
    "age_max": 45,
    "location": "Paris",
    "desires": ["Echangisme", "Gang bang"],
    "style": "auto",
    "max_contacts": 50
}
```

### Lister les campagnes

```
GET /api/campaigns/{platform}
```

**Reponse** :
```json
{
    "campaigns": [
        {
            "id": 1,
            "name": "Couples Paris mars",
            "status": "active",
            "contacts_total": 35,
            "contacts_by_status": {
                "pending": 10,
                "contacted": 12,
                "replied": 8,
                "conversation": 3,
                "met": 1,
                "rejected": 1,
                "skipped": 0
            },
            "response_rate": 40.0,
            "created_at": "2026-03-01"
        }
    ]
}
```

### Demarrer une campagne

```
POST /api/campaigns/{id}/start
```

Passe le statut de `draft` ou `paused` a `active` et lance le traitement des contacts `pending`.

### Mettre en pause

```
POST /api/campaigns/{id}/pause
```

### Executer une etape

```
POST /api/campaigns/{id}/step
```

Traite le prochain contact `pending` de la campagne (un seul contact par appel).

### Supprimer une campagne

```
DELETE /api/campaigns/{id}
```

---

Voir aussi : [[02-Fonctionnalites/scoring-profils|Scoring de profils]], [[02-Fonctionnalites/messages-ia|Messages IA]], [[02-Fonctionnalites/automatisation-likes|Automatisation des likes]]

#campagne #funnel #feature

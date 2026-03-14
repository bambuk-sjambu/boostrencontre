# Conversation multi-tour

#boostrencontre #conversation #multi-tour #feature

---

## Principe

Le systeme de conversation multi-tour structure les echanges en 4 etapes progressives. Chaque etape a un objectif, un nombre de tours recommande et un prompt adapte. Le systeme detecte les signaux d'interet ou de desinteret pour avancer ou rester a l'etape courante.

---

## Les 4 etapes

| Etape | Nom | Tours | Objectif |
|-------|-----|-------|----------|
| 1 | Accroche | 1 | Capter l'attention avec un premier message personnalise et engageant |
| 2 | Interet | 3 | Developper la conversation, trouver des points communs, creer de la complicite |
| 3 | Approfondissement | 4 | Approfondir la connexion, aborder les envies, construire la confiance |
| 4 | Proposition | 2 | Proposer un echange plus concret (numero, rendez-vous, soiree) |

### Detail par etape

**Etape 1 -- Accroche** : un seul message qui doit susciter une reponse. Reference a un element concret du profil, question ouverte ou commentaire engageant. Pas de presentation de soi. Le prompt utilise les regles habituelles de premier message (court, personnalise, pas de banalites).

**Etape 2 -- Interet** : 3 tours pour approfondir le contact. Le prompt demande de rebondir sur les reponses du destinataire, de poser des questions sur ses centres d'interet, de partager des anecdotes personnelles liees au profil utilisateur. Ton decontracte, pas de questions en rafale.

**Etape 3 -- Approfondissement** : 4 tours pour construire une vraie connexion. Le prompt integre l'historique complet de la conversation et demande d'aborder des sujets plus intimes ou plus concrets (envies, projets, experiences). Le ton s'adapte au niveau d'ouverture du destinataire.

**Etape 4 -- Proposition** : 2 tours pour concretiser. Le prompt suggere de proposer un echange de coordonnees, un appel, ou un rendez-vous. Le ton reste respectueux et sans pression. Si le destinataire hesite, le systeme reste a cette etape sans insister.

---

## Historique en base de donnees

Les conversations sont stockees dans la table `conversation_history` :

```sql
CREATE TABLE conversation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    contact_name TEXT NOT NULL,
    stage INTEGER DEFAULT 1,
    turn_count INTEGER DEFAULT 0,
    last_message_sent TEXT,
    last_message_received TEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

| Champ | Description |
|-------|-------------|
| `stage` | Etape courante (1 a 4) |
| `turn_count` | Nombre de tours dans l'etape courante |
| `summary` | Resume de la conversation genere par l'IA |
| `last_message_sent` | Dernier message envoye par le bot |
| `last_message_received` | Dernier message recu du destinataire |

---

## Prompt adaptatif

Chaque etape ajoute un `prompt_addon` au prompt de base :

| Etape | Instructions ajoutees |
|-------|----------------------|
| 1 | "Premier contact. Accroche courte et percutante. Une seule question ou un commentaire engageant." |
| 2 | "Conversation en cours. Rebondis sur ce que l'autre dit. Pose des questions sur ses centres d'interet. Partage une anecdote personnelle. Pas de questions en rafale." |
| 3 | "Conversation avancee. Approfondis les sujets abordes. Aborde les envies si le contexte s'y prete. Montre de l'authenticite et de la confiance." |
| 4 | "Conversation mature. Si le contexte est favorable, propose un echange de coordonnees ou un rendez-vous. Reste naturel et sans pression." |

---

## Detection de signaux

### Signaux d'interet (avancer d'etape)

Le systeme detecte les signaux suivants pour avancer a l'etape suivante :

- Reponses longues (plus de 30 mots)
- Questions posees par le destinataire
- Emojis positifs ou rires
- References a des sujets intimes ou personnels
- Propositions d'activites ou de rencontres
- Compliments ou expressions d'interet explicites

### Signaux de desinteret (rester a l'etape)

- Reponses courtes (moins de 10 mots) sans question
- Delai long entre les reponses (plus de 24h)
- Reponses monosyllabiques ("ok", "ah", "ouais")
- Absence de question ou de relance
- Ton distant ou poli mais froid

Si des signaux de desinteret sont detectes pendant 2 tours consecutifs, le systeme passe en mode passif : il attend un message du destinataire avant de relancer.

---

## Resume de conversation

Un resume de la conversation est genere par l'IA et stocke dans le champ `summary`. Ce resume est injecte dans le prompt pour que l'IA garde le contexte sans avoir besoin de relire tout l'historique.

Le resume est mis a jour a chaque tour et contient :
- Les sujets abordes
- Le ton general de la conversation
- Les points communs identifies
- Le niveau d'ouverture du destinataire

---

## Endpoints API

### Lister les conversations

```
GET /api/conversations/{platform}
```

Retourne toutes les conversations actives avec leur etape et leur nombre de tours.

**Reponse** :
```json
{
    "conversations": [
        {
            "contact_name": "PseudoX",
            "stage": 2,
            "turn_count": 2,
            "summary": "Discussion sur les voyages en Asie...",
            "updated_at": "2026-03-10 14:32:00"
        }
    ]
}
```

### Detail d'une conversation

```
GET /api/conversations/{platform}/{contact}
```

Retourne le detail complet d'une conversation avec l'historique.

### Statistiques de conversation

```
GET /api/conversation-stats/{platform}
```

Retourne les statistiques globales.

**Reponse** :
```json
{
    "total_conversations": 45,
    "by_stage": {
        "1": 10,
        "2": 20,
        "3": 12,
        "4": 3
    },
    "average_turns": 4.2,
    "conversion_rate": 6.7
}
```

---

Voir aussi : [[02-Fonctionnalites/messages-ia|Messages IA]], [[02-Fonctionnalites/reponses-automatiques|Reponses automatiques]], [[02-Fonctionnalites/scoring-profils|Scoring de profils]]

#conversation #multi-tour #feature

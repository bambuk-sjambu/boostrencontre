# Scoring de profils

#boostrencontre #scoring #compatibilite #feature

---

## Principe

Le scoring de profils attribue un score de compatibilite sur 100 points a chaque profil visite. Ce score permet de prioriser les interactions : envoyer un message personnalise aux profils les plus compatibles, un simple like aux profils moyens, et ignorer les profils peu pertinents.

---

## Les 5 criteres de scoring

| Critere | Points max | Description |
|---------|------------|-------------|
| Desirs communs | 30 | Correspondance entre les envies du destinataire et celles de l'utilisateur |
| Completude du profil | 20 | Nombre de champs remplis dans le profil du destinataire (bio, infos, preferences) |
| Activite recente | 15 | Date de derniere connexion ou derniere activite visible |
| Compatibilite de type | 20 | Correspondance entre le type du destinataire et les preferences de l'utilisateur |
| Geographie | 15 | Proximite geographique entre les deux profils |

### Detail du calcul

**Desirs communs (30 pts)** : chaque desir commun entre l'utilisateur et le destinataire rapporte des points. Les desirs sont extraits des tags du profil et de la detection dans la bio. Le score est proportionnel au nombre de correspondances.

**Completude du profil (20 pts)** : un profil avec bio, photo, preferences et onglet Infos rempli obtient le maximum. Un profil minimal (photo seule, pas de bio) obtient peu de points. Les profils incomplets sont moins interessants pour generer un message personnalise.

**Activite recente (15 pts)** : un profil connecte dans l'heure obtient 15 points. Les points diminuent avec le temps ecoulé depuis la derniere connexion. Un profil inactif depuis plus de 7 jours obtient 0.

**Compatibilite de type (20 pts)** : verifie que le type du destinataire correspond aux preferences de l'utilisateur. Par exemple, si l'utilisateur cherche des couples, les profils de couples obtiennent le maximum.

**Geographie (15 pts)** : calcul base sur la distance entre les localisations declarees. Meme ville = 15 pts, meme region = 10 pts, meme pays = 5 pts, etranger = 0.

---

## Grades

Le score total determine un grade qui oriente l'action recommandee :

| Grade | Score | Action recommandee |
|-------|-------|--------------------|
| A | >= 80 | Envoyer un message IA personnalise |
| B | >= 60 | Envoyer un message IA ou un like |
| C | >= 40 | Like uniquement |
| D | < 40 | Ignorer (skip) |

---

## Suggestion automatique du style

En fonction du profil analyse, le scoring suggere le meilleur style de message :

- Profil explicite sur les desirs : `direct_sexe`
- Profil avec bio poetique ou emotionnelle : `romantique`
- Profil avec references culturelles : `intellectuel`
- Profil avec beaucoup de voyages/activites : `aventurier`
- Profil avec humour dans la bio : `humoristique`
- Profil discret ou minimaliste : `mysterieux`
- Profil chaleureux avec centres d'interet communs : `complice`
- Cas incertain : `auto` (l'IA choisit)

---

## Integration dans le flow

Le scoring est utilise a deux endroits :

**Lors des likes** : les profils avec un score D (< 40) sont ignores. Les profils A et B sont prioritaires pour le follow et le crush.

**Lors des messages** : seuls les profils A et B recoivent un message IA. Le style suggere est utilise si le mode `auto` est selectionne.

---

## Endpoints API

### Obtenir le score d'un profil

```
GET /api/profile-score/{platform}/{name}
```

Retourne le score detaille d'un profil.

**Reponse** :
```json
{
    "name": "PseudoX",
    "score": 75,
    "grade": "B",
    "details": {
        "desirs_communs": 25,
        "completude": 15,
        "activite": 15,
        "compatibilite_type": 10,
        "geographie": 10
    },
    "suggested_style": "complice",
    "action": "message"
}
```

### Statistiques de scoring

```
GET /api/scoring-stats/{platform}
```

Retourne les statistiques de scoring pour la plateforme.

**Reponse** :
```json
{
    "total_scored": 150,
    "by_grade": {
        "A": 12,
        "B": 35,
        "C": 68,
        "D": 35
    },
    "average_score": 52.3,
    "top_profiles": [
        {"name": "PseudoX", "score": 92, "grade": "A"}
    ]
}
```

---

Voir aussi : [[02-Fonctionnalites/automatisation-likes|Automatisation des likes]], [[02-Fonctionnalites/messages-ia|Messages IA]], [[02-Fonctionnalites/conversation-multi-tour|Conversation multi-tour]]

#scoring #feature

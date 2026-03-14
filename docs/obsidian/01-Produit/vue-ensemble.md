# Vue d'ensemble

#boostrencontre #presentation

---

## Qu'est-ce que BoostRencontre ?

BoostRencontre est un assistant d'automatisation pour sites de rencontres. Il permet de :

- **Automatiser les interactions** : likes, follows et crush sur les profils qui correspondent a vos criteres
- **Envoyer des messages personnalises par IA** : chaque message est genere sur mesure en fonction du profil du destinataire, de sa bio, de son type et de vos propres centres d'interet
- **Repondre automatiquement aux conversations** : detection des messages non lus et generation de reponses contextuelles qui rebondissent sur l'echange en cours
- **Piloter le tout depuis un dashboard web** : interface simple pour lancer les actions, suivre les resultats et ajuster les parametres

L'outil fonctionne en pilotant un navigateur Chromium reel (via Playwright), ce qui permet de conserver vos sessions de connexion et d'interagir avec les sites exactement comme un utilisateur humain.

---

## A qui ca s'adresse

BoostRencontre s'adresse aux utilisateurs de sites de rencontres qui souhaitent :

- Gagner du temps sur les interactions repetitives (likes, follows)
- Envoyer des premiers messages originaux et personnalises plutot que du copier-coller
- Ne pas rater de conversations en repondant rapidement aux messages recus
- Cibler un type de profil precis (couples, femmes, hommes) ou des envies specifiques
- Tester differentes approches de communication pour voir ce qui fonctionne le mieux

---

## Comment ca marche

### Flow simplifie

```
1. LANCEMENT
   Demarrer le serveur (port 8888)
   Ouvrir le dashboard dans votre navigateur

2. CONNEXION
   Cliquer sur la plateforme souhaitee (Wyylde, Tinder, Meetic)
   Un navigateur Chromium s'ouvre automatiquement
   Se connecter manuellement sur le site
   Le dashboard detecte la connexion

3. CONFIGURATION
   Renseigner son profil IA (pseudo, description, centres d'interet)
   Choisir le style de communication (8 styles disponibles)
   Ajuster les parametres (nombre d'actions, delais)
   Selectionner les filtres de profil si souhaite

4. ACTIONS
   Lancer les likes : visite des profils + follow + crush
   Lancer les messages IA : premiers messages personnalises
   Lancer les reponses : reponse aux messages non lus
   Activer la veille auto-reply : surveillance continue

5. SUIVI
   Consulter le log d'activite en temps reel
   Verifier les statistiques par style et par jour
   Ajuster les parametres selon les resultats
```

### Cycle d'un message IA

```
Profil destinataire (bio, type, age, envies)
       +
Profil utilisateur (MY_PROFILE, 10 categories)
       +
Style de communication choisi
       +
Template d'approche (optionnel)
       |
       v
  Prompt OpenAI (gpt-4o-mini)
       |
       v
  Filtre de securite (longueur, patterns interdits)
       |
       v
  Saisie dans l'editeur du site + envoi
```

---

## Stack technique (resume)

| Composant | Technologie | Role |
|-----------|-------------|------|
| Serveur web | FastAPI (Python 3.12) | API REST + pages HTML |
| Base de donnees | SQLite (aiosqlite) | Stockage comptes, logs, parametres, profil |
| Navigateur | Playwright + Chromium | Automatisation web, sessions persistantes |
| Intelligence artificielle | OpenAI API (gpt-4o-mini) | Generation de messages personnalises |
| Templates HTML | Jinja2 | Dashboard et page profil |
| Port par defaut | 8888 | Acces local au dashboard |

Tout le code est asynchrone (async/await) pour permettre les operations longues sans bloquer l'interface.

---

## Plateformes supportees

| Plateforme | Statut | Likes | Follow | Crush | Messages IA | Reponses auto | Recherche |
|------------|--------|-------|--------|-------|-------------|---------------|-----------|
| **Wyylde** | Operationnel | Oui | Oui | Oui | Oui | Oui | Oui |
| **Tinder** | Base implementee | Oui | -- | -- | Oui | Non | Non |
| **Meetic** | Base implementee | Oui | -- | -- | Oui | Non | Non |

**Wyylde** est la plateforme la plus aboutie avec l'ensemble des fonctionnalites : likes, follow, crush, messages IA personnalises depuis le profil ou la recherche, reponses automatiques aux conversations non lues du sidebar, et mode veille auto-reply.

**Tinder** et **Meetic** disposent de l'implementation de base : ouverture du navigateur, detection de connexion, likes automatiques et envoi de messages. Les fonctionnalites avancees (reponses automatiques, recherche filtree) ne sont pas encore implementees pour ces plateformes.

---

Voir aussi : [[02-Fonctionnalites/dashboard|Dashboard]], [[01-Produit/plateformes|Plateformes]], [[01-Produit/guide-utilisation|Guide d'utilisation]]

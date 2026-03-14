# Dashboard web

#boostrencontre #dashboard #interface #configuration

---

## Acces

Le dashboard est accessible a l'adresse `http://127.0.0.1:8888` apres le lancement du serveur. Il fonctionne exclusivement en local.

Deux pages sont disponibles :
- **`/`** : Dashboard principal (actions, parametres, logs)
- **`/profile`** : Page de gestion du profil IA

---

## Page principale (Dashboard)

### Bandeau d'instructions

En haut de page, un encadre resume les 3 etapes :
1. Cliquer sur une plateforme pour ouvrir le navigateur
2. Se connecter manuellement
3. Lancer les actions (Liker / Messages IA)

### Section Plateformes

Trois cartes cliquables representant les plateformes supportees :

| Plateforme | Icone | Comportement au clic |
|------------|-------|---------------------|
| Tinder | Flamme | Ouvre un navigateur Chromium sur tinder.com |
| Meetic | Coeur | Ouvre un navigateur Chromium sur meetic.fr |
| Wyylde | Interdit aux mineurs | Ouvre un navigateur Chromium sur app.wyylde.com |

Chaque carte affiche un statut :
- **Deconnecte** (rouge) : navigateur non ouvert ou non connecte
- **Ouverture...** (bleu) : navigateur en cours d'ouverture
- **En attente login...** (bleu) : navigateur ouvert, en attente de connexion manuelle
- **Connecte** (vert) : connexion detectee, pret pour les actions

La detection de connexion se fait par polling automatique toutes les 5 secondes pendant 5 minutes apres l'ouverture du navigateur.

### Section Filtre Wyylde

Controles de filtrage specifiques a Wyylde :

**Type de profil** : menu deroulant permettant de filtrer les profils cibles
- Tous (pas de filtre)
- Couple F Bi (selectionne par defaut)
- Couple hetero
- Couple M Bi
- Femme hetero / Femme Bi
- Homme hetero / Homme Bi
- Travesti

**Envies** : cases a cocher pour les categories de desirs
- Gang bang (coche par defaut)
- Echangisme, BDSM, Exhibition, Feeling, Fetichisme, Hard, Papouilles, Pluralite

**Templates de message** : section qui apparait quand au moins une envie est cochee
- Menu deroulant des templates existants pour les envies selectionnees
- Zone de texte affichant le contenu du template selectionne (editable)
- Boutons : Sauver (modifier un template), Supprimer, Ajouter un nouveau template

### Section Style de communication

Menu deroulant pour choisir le style de message IA :
- Auto (IA choisit) -- par defaut
- Romantique
- Direct sexe
- Humoristique
- Intellectuel
- Aventurier
- Mysterieux
- Complice

Le style selectionne s'applique a toutes les actions de messagerie (premiers messages, reponses, recherche).

### Section Actions

Boutons d'action organises en deux lignes :

**Ligne 1 -- Actions standard** :
| Bouton | Action |
|--------|--------|
| Liker - Tinder | Lance les likes sur Tinder |
| Liker - Meetic | Lance les likes sur Meetic |
| Liker - Wyylde | Lance les likes sur Wyylde (avec filtre si actif) |
| Messages IA - Tinder | Envoie des messages IA sur Tinder |
| Messages IA - Meetic | Envoie des messages IA sur Meetic |
| Messages IA - Wyylde | Envoie des messages IA sur Wyylde |

**Ligne 2 -- Actions avancees (Wyylde)** :
| Bouton | Action |
|--------|--------|
| Messages Recherche - Wyylde | Envoie des messages aux profils trouves par recherche filtree |
| Repondre Non-Lus Sidebar - Wyylde | Repond aux messages non lus du sidebar |
| Veille Auto-Reply - Wyylde | Active/desactive le mode veille auto-reply (toutes les 60s) |
| Mon Profil IA | Lien vers la page profil |

Le bouton "Veille Auto-Reply" change d'apparence quand il est actif :
- Inactif : vert, texte "Veille Auto-Reply - Wyylde"
- Actif : rouge, texte "STOP Veille - Wyylde"

### Section Parametres

Quatre champs numeriques ajustables :

| Parametre | Defaut | Min | Max | Description |
|-----------|--------|-----|-----|-------------|
| Likes par session | 50 | 1 | 200 | Nombre de profils a visiter |
| Messages par session | 3 | 1 | 20 | Nombre de messages a envoyer |
| Delai min (sec) | 3 | 1 | 30 | Delai minimum entre chaque action |
| Delai max (sec) | 8 | 2 | 60 | Delai maximum entre chaque action |

Un bouton "Sauvegarder" enregistre les parametres en base de donnees.

### Section Activite recente

Tableau des 50 derniers evenements avec les colonnes :
- **Date** : horodatage de l'action
- **Plateforme** : wyylde, tinder ou meetic
- **Action** : like, message, sidebar_msg, search_msg, reply, sidebar_reply, auto_reply, rejected
- **Profil** : pseudo du destinataire
- **Message** : apercu du message envoye (50 premiers caracteres)

---

## Page Profil IA (`/profile`)

### Section Identite

Formulaire avec 4 champs :
- Pseudo
- Age
- Type de profil
- Localisation

### Section Description generale

Zone de texte libre pour la presentation. Annotee : "visible dans tous les prompts IA".

### Section Categories de connaissance

10 zones de texte, chacune avec :
- Nom de la categorie (en rouge)
- Indicateur de statut : "rempli" (vert) ou "vide" (gris)
- Zone de texte avec placeholder indicatif

Les categories : Passions, Pratiques, Personnalite, Physique, Etudes/metier, Voyages, Musique/culture, Sport, Humour, Valeurs.

### Actions

- **Sauvegarder tout** : enregistre le profil complet
- **Enrichir avec l'IA** : analyse les messages envoyes pour remplir automatiquement les categories vides

### Historique

Tableau des derniers messages envoyes avec date, action, destinataire et apercu du message.

---

## Notifications et retours

Un bandeau de notification en haut du dashboard affiche les retours d'action :
- **Bleu (info)** : action en cours ("Likes lances sur wyylde...")
- **Vert (success)** : action terminee ("5 profils likes sur wyylde !")
- **Rouge (error)** : erreur ou prerequis manquant ("Tu n'es pas connecte sur wyylde")

Les notifications disparaissent automatiquement apres 5 secondes.

---

## Gestion des templates d'approche

Les templates de message sont geres directement depuis le dashboard :

### Consultation
- Cocher une ou plusieurs envies dans la section Filtre Wyylde
- Les templates correspondant aux envies cochees apparaissent dans le menu deroulant
- Cliquer sur un template affiche son contenu dans la zone de texte

### Modification
- Selectionner un template dans le menu deroulant
- Modifier le contenu dans la zone de texte
- Cliquer "Sauver" pour enregistrer les modifications

### Creation
- Ecrire le contenu du template dans la zone de texte
- Saisir un nom dans le champ "Nom du nouveau template"
- Cliquer "+ Ajouter"
- Le template est associe a la premiere envie cochee

### Suppression
- Selectionner un template dans le menu deroulant
- Cliquer "Suppr"

---

Voir aussi : [[02-Fonctionnalites/profil-ia|Profil IA]], [[01-Produit/guide-utilisation|Guide d'utilisation]], [[03-Technique/api-reference|Reference API]]

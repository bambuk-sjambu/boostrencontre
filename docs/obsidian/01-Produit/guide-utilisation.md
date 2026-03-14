# Guide d'utilisation

#boostrencontre #guide #installation #demarrage

---

## Prerequis

| Composant | Version | Usage |
|-----------|---------|-------|
| Python | 3.12+ | Serveur et logique |
| pip | Recent | Installation des dependances |
| Chromium | Installe par Playwright | Navigateur automatise |
| Cle API OpenAI | Valide | Generation de messages IA |

### Systeme d'exploitation

BoostRencontre fonctionne sur Linux. Certaines fonctionnalites utilisent des outils Linux (wmctrl, xdotool) pour minimiser la fenetre du navigateur.

---

## 1. Installation

### Cloner ou telecharger le projet

Placer les fichiers dans un dossier de travail.

### Creer l'environnement virtuel

```bash
cd /chemin/vers/boostrencontre
python3.12 -m venv venv
```

### Installer les dependances

```bash
venv/bin/pip install -r requirements.txt
```

### Installer le navigateur Playwright

```bash
venv/bin/playwright install chromium
```

### Configurer les variables d'environnement

Creer un fichier `.env` a la racine du projet :

```
OPENAI_API_KEY=sk-votre-cle-openai
```

Optionnel :
```
DASHBOARD_TOKEN=un-token-fixe-de-votre-choix
WYYLDE_MEMBER_ID=votre-id-membre-wyylde
DEBUG=true
```

Si `DASHBOARD_TOKEN` n'est pas defini, un token aleatoire est genere automatiquement a chaque demarrage et affiche dans les logs.

---

## 2. Premier lancement

```bash
cd /chemin/vers/boostrencontre
venv/bin/python main.py
```

Le serveur demarre sur le port 8888. Ouvrir le dashboard dans un navigateur :

```
http://127.0.0.1:8888
```

Le terminal affiche :
- Le token d'acces genere (si pas de `DASHBOARD_TOKEN` fixe)
- Les logs de demarrage (initialisation de la base, chargement du profil)

---

## 3. Connexion au site

### Etape 1 : Ouvrir le navigateur

Sur le dashboard, cliquer sur la carte de la plateforme souhaitee (Wyylde, Tinder ou Meetic). Un navigateur Chromium s'ouvre automatiquement et navigue vers le site.

Le statut de la carte passe a "Ouverture..." puis "En attente login...".

### Etape 2 : Se connecter manuellement

Dans le navigateur qui vient de s'ouvrir, se connecter au site avec ses identifiants habituels.

Important : la connexion est manuelle. BoostRencontre ne stocke pas les identifiants.

### Etape 3 : Attendre la detection

Le dashboard poll automatiquement toutes les 5 secondes pour verifier la connexion. Quand celle-ci est detectee, le statut passe a "Connecte" (vert).

Les cookies sont automatiquement sauvegardes. Au prochain lancement, la session sera conservee (pas besoin de se reconnecter tant que le site ne deconnecte pas).

---

## 4. Configuration du profil IA

Avant d'envoyer des messages, il est important de remplir son profil IA pour que les messages generes soient coherents avec sa personnalite.

### Acceder a la page profil

Cliquer sur "Mon Profil IA" dans la navigation du dashboard, ou aller directement sur `http://127.0.0.1:8888/profile`.

### Remplir l'identite

- **Pseudo** : le pseudo utilise sur le site (important pour l'anti-doublon et la detection du dernier expediteur)
- **Type** : Homme, Femme, Couple hetero, Couple F Bi, etc.
- **Age** : age reel ou age du couple (ex: "35" ou "35/32")
- **Localisation** : ville ou region

### Remplir la description

Ecrire une presentation libre qui sera utilisee dans tous les prompts IA. Decrire ce qu'on cherche, ce qui nous definit, nos envies.

### Remplir les categories

Les 10 categories permettent a l'IA de personnaliser les messages en profondeur :

1. **Passions et hobbies** : ce qui nous passionne en dehors du site
2. **Pratiques et experiences** : preferences libertines, experiences passees
3. **Personnalite** : traits de caractere dominants
4. **Physique** : description physique sommaire
5. **Etudes et metier** : formation, domaine professionnel
6. **Voyages** : destinations preferees, habitudes de voyage
7. **Musique et culture** : gouts musicaux, culturels
8. **Sport** : activites sportives, bien-etre
9. **Humour** : type d'humour, references
10. **Valeurs** : ce qui compte vraiment pour nous

Astuce : remplir les categories prioritaires d'abord, puis cliquer "Enrichir avec l'IA" pour completer les categories vides a partir des messages deja envoyes.

### Sauvegarder

Cliquer "Sauvegarder tout" pour enregistrer le profil. Il sera immediatement utilise dans les prochains messages generes.

---

## 5. Lancer les premieres actions

### Choisir le style de communication

Dans la section "Style de communication" du dashboard, selectionner le style souhaite :
- **Auto** (recommande pour commencer) : l'IA choisit le ton le plus adapte a chaque profil
- Ou un style specifique selon la strategie voulue

### Configurer les filtres (Wyylde)

Si on souhaite cibler un type de profil :
1. Selectionner le type dans le menu "Type de profil" (ex: "Couple F Bi")
2. Cocher les envies souhaitees (ex: "Gang bang", "Echangisme")
3. Optionnel : selectionner ou creer un template de message

### Lancer les likes

Cliquer sur "Liker - [plateforme]". Le bot commence a visiter les profils, follow et crush. Surveiller le navigateur ouvert pour voir les actions en cours.

Le dashboard affiche un message bleu pendant l'execution, puis vert avec le nombre de profils visites.

### Lancer les messages IA

Cliquer sur "Messages IA - [plateforme]". Le bot navigue vers les profils en ligne, lit chaque profil, genere un message personnalise et l'envoie.

Le nombre de messages envoyes est limite par le parametre "Messages par session" (defaut: 3).

### Lancer les messages via recherche (Wyylde)

Cliquer sur "Messages Recherche - Wyylde". Le bot applique les filtres de recherche, visite les profils des resultats et envoie des messages personnalises.

### Lancer les reponses aux non-lus

Cliquer sur "Repondre Non-Lus Sidebar - Wyylde". Le bot detecte les discussions non lues, lit la conversation et envoie une reponse contextuelle.

### Activer la veille auto-reply

Cliquer sur "Veille Auto-Reply - Wyylde". Le bot scanne les non-lus toutes les 60 secondes et repond automatiquement. Cliquer a nouveau pour arreter.

---

## 6. Surveiller les resultats

### Log d'activite

La section "Activite recente" en bas du dashboard affiche les 50 dernieres actions :
- **like** : profil visite (follow + crush)
- **message** : premier message envoye (depuis les matchs)
- **sidebar_msg** : premier message envoye (depuis les discussions)
- **search_msg** : premier message envoye (depuis la recherche)
- **reply** / **sidebar_reply** / **auto_reply** : reponse envoyee
- **rejected** : contact marque comme rejet (la personne a dit non)

### Statistiques

Les statistiques sont disponibles via l'API `GET /api/stats/{platform}?days=7` :
- Nombre de messages envoyes et reponses recues
- Taux de reponse global et par style
- Activite par jour
- Conversations recentes

---

## 7. Ajuster les parametres

### Parametres de session

Dans la section "Parametres" du dashboard :

- **Likes par session** : augmenter pour visiter plus de profils (attention aux limites journalieres)
- **Messages par session** : augmenter pour envoyer plus de messages (recommande : 3-5 pour rester naturel)
- **Delai min/max** : augmenter pour plus de securite, diminuer pour plus de rapidite

### Strategie de style

Tester differents styles et comparer les taux de reponse via les statistiques par style :
- Le style "auto" est un bon point de depart
- Le style "humoristique" fonctionne bien pour les premiers contacts
- Le style "direct_sexe" est adapte aux profils explicites sur leurs envies

### Templates d'approche

Creer des templates specifiques pour les envies les plus frequentes. L'IA les reformulera et les adaptera a chaque profil.

---

## Commandes utiles

### Demarrer le serveur
```bash
venv/bin/python main.py
```

### Demarrer en mode debug
```bash
DEBUG=true venv/bin/python main.py
```

### Lancer les tests
```bash
venv/bin/python -m pytest tests/ -v
```

### Verifier le nombre de tests
```bash
venv/bin/python -m pytest tests/ --co -q | tail -1
```

---

## Precautions

- **Ne jamais lancer le serveur sur un port expose a Internet** : le dashboard est concu pour un usage local uniquement
- **Respecter les conditions d'utilisation des sites** : l'automatisation peut entrainer la suspension du compte
- **Surveiller les limites journalieres** : elles sont la pour proteger le compte
- **Garder le navigateur accessible** : meme minimise, il doit rester ouvert pour que les actions fonctionnent
- **Sauvegarder regulierement le fichier `boostrencontre.db`** : il contient le profil, les parametres et l'historique

---

Voir aussi : [[01-Produit/vue-ensemble|Vue d'ensemble]], [[02-Fonctionnalites/dashboard|Dashboard]], [[03-Technique/securite-anti-ban|Securite et anti-ban]]

# Detail des plateformes

#boostrencontre #wyylde #tinder #meetic #plateformes

---

## Tableau comparatif

| Fonctionnalite | Wyylde | Tinder | Meetic |
|----------------|--------|--------|--------|
| **Statut** | Operationnel | Base implementee | Base implementee |
| Ouverture navigateur | Oui | Oui | Oui |
| Detection connexion | Oui | Oui | Oui |
| Profils navigateur persistants | Oui | Oui | Oui |
| Likes | Oui (sidebar) | Oui (swipe) | Oui (shuffle) |
| Follow | Oui | -- | -- |
| Crush | Oui | -- | -- |
| Filtre par type de profil | Oui | Non | Non |
| Filtre par envies/desirs | Oui | Non | Non |
| Premiers messages IA | Oui | Oui | Oui |
| Messages depuis recherche | Oui | Non | Non |
| Messages depuis discussions | Oui | Non | Non |
| Reponses inbox | Oui | Non | Non |
| Reponses sidebar | Oui | Non | Non |
| Auto-reply (veille) | Oui | Non | Non |
| Lecture profil complet | Oui (bio + Infos) | Basique | Basique |
| Detection de rejet | Oui | Non | Non |
| Anti-doublon | Oui | Oui | Oui |
| Exploration de profil (nouvel onglet) | Oui | Non | Non |
| Screenshot | Oui | Oui | Oui |
| Statistiques | Oui | Oui | Oui |

---

## Wyylde (operationnel)

### URL de login
```
https://app.wyylde.com/fr-fr
```

### Architecture du code

Le code Wyylde est organise en 6 fichiers via un systeme de mixins :

| Fichier | Contenu |
|---------|---------|
| `platform.py` | Classe principale `WyyldePlatform` (composition des mixins), likes, follow, crush |
| `profile.py` | Mixin `WyyldeProfileMixin` : lecture de profil, extraction bio, navigation |
| `messaging.py` | Mixin `WyyldeMessagingMixin` : envoi de messages, "Lui ecrire", reply chat |
| `search.py` | Mixin `WyyldeSearchMixin` : filtres de recherche, resultats, navigation |
| `sidebar.py` | Mixin `WyyldeSidebarMixin` : sidebar chat, discussions, profils en ligne |
| `selectors.py` | Constantes CSS : tous les selecteurs centralises |

### Navigation principale

| Page | URL | Utilisation |
|------|-----|-------------|
| Dashboard | `app.wyylde.com/fr-fr` (redirige vers /dashboard/wall) | Page d'accueil, sidebar chat visible |
| Recherche | `app.wyylde.com/fr-fr/search/user` | Recherche de profils avec filtres |
| Mailbox inbox | `app.wyylde.com/fr-fr/mailbox/inbox` | Boite de reception des messages |
| Mailbox sent | `app.wyylde.com/fr-fr/mailbox/sent` | Messages envoyes |
| Profil membre | `app.wyylde.com/fr-fr/member/{id}` | Page profil d'un membre |

### Selecteurs CSS cles

| Element | Selecteur |
|---------|-----------|
| Profil chat sidebar | `button[class*="bg-neutral-lowest"][class*="cursor-pointer"]` |
| Lien membre | `a[href*="/member/"]` |
| Nom profil | `button.max-w-full.font-poppins` |
| Bouton Follow | `button:has(svg[data-icon="user-plus"])` |
| Bouton Crush | `button:has(svg[data-icon="wyylde-crush"])` |
| Bouton "Lui ecrire" | `button:has(svg[data-icon="paper-plane"])` |
| Bouton envoi message | `svg[data-icon="paper-plane-top"]` |
| Editeur TipTap | `div.tiptap.ProseMirror[contenteditable="true"]` |
| Conversations inbox | `a[href*="/mailbox/inbox/"]` |
| Onglet "Tous" | `button[name="all"]` |

### Chat sidebar

Le sidebar droit du dashboard affiche :
- **Profils en ligne** : boutons cliquables avec pseudo, type et age
- **Discussions non lues** : section repliable avec bouton jaune-vert (`BG=rgb(236,255,107)`)
- **Discussions en cours** : liste des conversations actives

Position typique : x > 1000 pour les elements du sidebar.

### Editeur TipTap

Wyylde utilise l'editeur TipTap (base ProseMirror) pour la saisie des messages. Deux editeurs peuvent etre presents simultanement :
- **Editeur modal** : large (~512px), apparait quand on clique "Lui ecrire" sur un profil
- **Editeur chat sidebar** : petit (~222px), dans le popup de chat

Le bot cible l'editeur le plus large pour les premiers messages (modal) et l'editeur plus etroit pour les reponses dans le chat.

L'envoi se fait par :
1. Clic physique sur l'editeur (coordonnees x,y, pas de focus JavaScript)
2. Frappe au clavier caractere par caractere (delay=25ms)
3. Clic sur le bouton d'envoi (icone `paper-plane-top`)
4. Fallback : touche Entree si le bouton n'est pas trouve

### Lecture de profil complet

La lecture d'un profil Wyylde se fait en plusieurs etapes :
1. Clic sur "EN SAVOIR PLUS" / "LIRE LA SUITE" pour deplier la bio
2. Extraction du texte principal (bio, type, age, localisation)
3. Clic sur l'onglet "Infos" pour acceder aux preferences
4. Extraction des tags de desirs (BDSM, Echangisme, Exhibition, etc.)
5. Extraction des preferences (orientation, situation, silhouette, etc.)

### Recherche filtree

La page de recherche permet d'appliquer des filtres :
1. Navigation vers `app.wyylde.com/fr-fr/search/user`
2. Clic sur "Effacer" pour reinitialiser les filtres
3. Selection du type de profil dans "Criteres principaux"
4. Selection des envies dans l'onglet "Envies"
5. Soumission du formulaire de recherche
6. Fermeture du panneau de filtres (Escape)
7. Extraction des liens `/member/` dans les resultats

### Envies detectees sur les profils

```
BDSM, Echangisme, Exhibition, Extreme, Feeling,
Fetichisme, Gang bang, Hard, Papouilles, Pluralite,
Videos, Voyeurisme, Massage, Tantra, Domination,
Soumission, Candaulisme, Triolisme, Libertinage, Melanisme
```

---

## Tinder (base implementee)

### URL de login
```
https://tinder.com
```

### Detection de connexion

La connexion est detectee par la presence de l'un des selecteurs :
- `[class*="recsCardboard"]` (cartes de profils)
- `[class*="matchListItem"]` (liste de matchs)
- `a[href*="/app/recs"]` (lien vers les recommandations)

### Likes

Le bot like les profils affiches sur la page principale :
1. Extraction des informations du profil courant (nom, age, bio, interets)
2. Clic sur le bouton "Like" ou le raccourci clavier (fleche droite)
3. Gestion des popups de match

### Messages

1. Navigation vers `tinder.com/app/matches`
2. Pour chaque match : navigation vers la conversation, saisie du message, envoi
3. Anti-doublon en base de donnees

### Extraction de profil

| Information | Selecteur |
|-------------|-----------|
| Nom | `[class*="Typs(display-1-strong)"]`, `[itemprop="name"]` |
| Age | `[class*="Typs(display-2-regular)"]`, `span[class*="age"]` |
| Bio | `[class*="BreakWord"]`, `[class*="bio"]` |
| Interets | `[class*="pill"]`, `[class*="passion"]` |

### Limites

- Pas de follow ni de crush (n'existent pas sur Tinder)
- Pas de filtrage par type de profil
- Pas de reponses automatiques
- Pas de recherche filtree

---

## Meetic (base implementee)

### URL de login
```
https://www.meetic.fr
```

### Detection de connexion

La connexion est detectee par la presence de l'un des selecteurs :
- `[class*="profile-card"]`
- `[class*="js-shuffle"]`
- `a[href*="/app/search"]`
- `[data-test*="shuffle"]`

### Likes

Le bot like les profils sur la page Shuffle :
1. Navigation vers `meetic.fr/app/shuffle`
2. Extraction des informations du profil courant
3. Clic sur le bouton "J'aime" / "Like" / "Oui"
4. Fallback : clic sur l'icone coeur

### Messages

1. Navigation vers `meetic.fr/app/matches`
2. Pour chaque match : navigation vers la conversation, saisie du message, envoi
3. Anti-doublon en base de donnees

### Extraction de profil

| Information | Selecteur |
|-------------|-----------|
| Nom | `[class*="profile-card__name"]`, `[data-test*="name"]` |
| Age | `[class*="profile-card__age"]`, `[data-test*="age"]` |
| Bio | `[class*="profile-card__description"]`, `[data-test*="description"]` |
| Interets | `[class*="tag"]`, `[class*="hobby"]` |

### Limites

- Pas de follow ni de crush
- Pas de filtrage par type de profil
- Pas de reponses automatiques
- Pas de recherche filtree

---

## Architecture commune

Toutes les plateformes heritent de `BasePlatform` (classe abstraite) qui definit les methodes requises :

| Methode | Obligatoire | Description |
|---------|-------------|-------------|
| `open()` | Oui | Ouvrir la plateforme dans une nouvelle page |
| `login_url()` | Oui | Retourner l'URL de connexion |
| `is_logged_in()` | Oui | Verifier si connecte |
| `like_profiles(count, delay_range)` | Oui | Liker des profils |
| `send_message(match_id, message)` | Oui | Envoyer un message |
| `get_matches()` | Oui | Obtenir la liste des matchs/contacts |
| `get_profile_info(element)` | Oui | Extraire les infos d'un profil |
| `navigate_to_profile(match_id)` | Optionnel | Naviguer vers un profil |
| `read_full_profile()` | Optionnel | Lire le profil complet |
| `get_inbox_conversations()` | Optionnel | Obtenir les conversations inbox |
| `open_chat_and_read(conv)` | Optionnel | Ouvrir et lire une conversation |
| `reply_in_chat(message)` | Optionnel | Repondre dans un chat ouvert |

---

Voir aussi : [[02-Fonctionnalites/automatisation-likes|Automatisation des likes]], [[02-Fonctionnalites/messages-ia|Messages IA]], [[02-Fonctionnalites/reponses-automatiques|Reponses automatiques]]

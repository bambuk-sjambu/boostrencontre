# Profil IA

#boostrencontre #profil #categories #enrichissement

---

## Principe

Le profil IA est l'ensemble des informations qui definissent l'utilisateur dans les yeux de l'intelligence artificielle. Ces informations sont injectees dans chaque prompt de generation de message, ce qui permet a l'IA de :

- Se presenter comme l'utilisateur ("Tu es [pseudo], [type], [age] ans, [localisation]")
- Trouver des points communs avec les destinataires
- Creer des rebonds naturels bases sur les centres d'interet reels de l'utilisateur
- Adapter le ton et le contenu a la personnalite de l'utilisateur

---

## Structure du profil

Le profil se compose de deux blocs : l'identite (5 champs) et les categories de connaissance (10 champs).

### Champs d'identite

| Champ | Label | Max caracteres | Requis | Description |
|-------|-------|----------------|--------|-------------|
| `pseudo` | Pseudo | 50 | Oui | Pseudo utilise sur le site |
| `type` | Type | 50 | Oui | Type de profil : Homme, Femme, Couple, etc. |
| `age` | Age | 20 | Oui | Age (ex: "35" ou "35/32" pour un couple) |
| `location` | Localisation | 100 | Oui | Ville ou region (ex: "Paris", "Lyon") |
| `description` | Description generale | 1000 | Oui | Presentation libre, visible dans tous les prompts |

### Les 10 categories de connaissance

| Cle | Label | Max | Placeholder |
|-----|-------|-----|-------------|
| `passions` | Passions et hobbies | 500 | Lecture, cuisine, voyages... |
| `pratiques` | Pratiques et experiences | 500 | Echangisme, BDSM... |
| `personnalite` | Personnalite | 500 | Curieux, drole, attentionne... |
| `physique` | Description physique | 300 | Grand, brun, sportif... |
| `etudes_metier` | Etudes et metier | 300 | Ingenieur, artiste... |
| `voyages` | Voyages | 300 | Asie, Amerique du Sud... |
| `musique_culture` | Musique et culture | 300 | Jazz, cinema d'auteur... |
| `sport` | Sport et bien-etre | 300 | Yoga, course, natation... |
| `humour` | Humour et references | 300 | Humour noir, Kaamelott... |
| `valeurs` | Valeurs | 300 | Respect, liberte, authenticite... |

---

## Comment le profil influence les messages

### Injection dans le prompt

Le profil est transforme en texte structure par la fonction `build_profile_prompt_text()` :

```
Pseudo: MonPseudo
Type: Couple hetero
Age: 35/32
Localisation: Paris
Description generale: [texte libre]
Passions & hobbies: voyages, photo, cuisine
Pratiques & experiences: echangisme soft
Personnalite: curieux, ouvert, respectueux
...
```

Ce texte est place au debut du prompt sous le bloc "TON PROFIL", suivi d'une instruction :

> "Utilise ces infos pour creer des points communs ou des rebonds naturels avec le profil de la personne."

### Impact concret

- Si l'utilisateur a renseigne "voyages : Asie du Sud-Est" et que le destinataire mentionne "Bali" dans sa bio, l'IA pourra naturellement rebondir sur ce point commun
- Si l'utilisateur a renseigne "humour : humour noir", l'IA adaptera le ton
- Les pratiques renseignees permettent a l'IA de parler des memes centres d'interet sans inventer

---

## Edition via le dashboard

Le profil est editable via la page `/profile` accessible depuis le dashboard.

### Page profil (`/profile`)

La page est divisee en trois sections :

1. **Identite** : formulaire avec pseudo, age, type, localisation
2. **Description generale** : zone de texte libre
3. **Categories de connaissance** : 10 zones de texte, chacune avec un indicateur "rempli" (vert) ou "vide" (gris)

### Actions disponibles

- **Sauvegarder tout** : enregistre le profil complet en base de donnees (table `user_profile`, id=1) et met a jour le dictionnaire `MY_PROFILE` en memoire
- **Enrichir avec l'IA** : utilise l'IA pour completer automatiquement les categories vides

### Historique des messages

En bas de la page profil, un tableau affiche les 50 derniers messages envoyes (premiers messages et reponses) avec la date, l'action, le destinataire et un apercu du message.

---

## Enrichissement IA automatique

L'enrichissement IA (`POST /api/user-profile/enrich`) analyse les informations existantes du profil et les messages deja envoyes pour completer les categories vides.

### Fonctionnement

1. Lecture des 30 derniers messages envoyes depuis la base de donnees
2. Construction d'un prompt qui demande a l'IA d'analyser la personnalite, les gouts et les habitudes de l'utilisateur a partir de ses messages
3. L'IA renvoie un JSON avec les 10 categories remplies
4. Les categories vides sont completees avec les suggestions de l'IA
5. Les categories deja remplies ne sont mises a jour que si la suggestion de l'IA est plus longue (plus detaillee)
6. Le profil enrichi est sauvegarde en base

### Exemple de prompt d'enrichissement

L'IA recoit :
- Le profil actuel (pseudo, type, age, localisation, description)
- Les categories deja remplies
- Jusqu'a 3000 caracteres de messages envoyes par l'utilisateur

Et doit renvoyer un JSON avec exactement les 10 cles de categories.

---

## Extraction du profil depuis le site

L'endpoint `GET /api/my-profile/{platform}` permet d'extraire le profil de l'utilisateur directement depuis la plateforme.

### Fonctionnement (Wyylde)

1. Necessite que le `WYYLDE_MEMBER_ID` soit configure (variable d'environnement ou champ `member_id` dans le profil en base)
2. Navigation vers `app.wyylde.com/fr-fr/member/{member_id}`
3. Extraction du nom, du texte complet du profil et des blocs de texte de la bio
4. Navigation vers `app.wyylde.com/fr-fr/mailbox/sent` pour lire les messages envoyes
5. Retour des donnees brutes (profil + messages envoyes)

Cette fonctionnalite permet de recuperer le texte reel du profil tel qu'il est affiche sur le site.

---

## Stockage

Le profil est stocke dans la table `user_profile` de la base SQLite :

```sql
CREATE TABLE user_profile (
    id INTEGER PRIMARY KEY,
    data TEXT NOT NULL  -- JSON contenant tout le profil
)
```

Un seul enregistrement (id=1) contient le profil au format JSON. Il est charge en memoire au demarrage de l'application (`app.py lifespan`) et mis a jour a chaque sauvegarde.

---

## Securisation des donnees

Les champs du profil sont valides et nettoyes par le module `profile_schema.py` :

- **Longueur maximum** : chaque champ a une limite definie (50 a 1000 caracteres)
- **Nettoyage** : suppression des caracteres de controle, echappement HTML (prevention XSS)
- **Troncature** : les valeurs depassant la limite sont tronquees silencieusement
- **Validation stricte** (optionnelle) : verification que les champs requis sont remplis

---

Voir aussi : [[02-Fonctionnalites/messages-ia|Messages IA]], [[02-Fonctionnalites/dashboard|Dashboard]], [[01-Produit/guide-utilisation|Guide d'utilisation]]

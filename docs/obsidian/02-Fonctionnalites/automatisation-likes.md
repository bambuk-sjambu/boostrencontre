# Automatisation des likes, follows et crush

#boostrencontre #likes #follow #crush #automatisation

---

## Ce que ca fait

La fonctionnalite "Likes" visite automatiquement les profils en ligne et effectue trois types d'interactions :

1. **Follow** (Suivre) : s'abonner au profil de la personne
2. **Crush** (Coup de coeur) : envoyer un coup de coeur
3. **Navigation de profil** : visite du profil complet (ce qui apparait dans les notifications de la personne)

Sur Wyylde, ces actions sont effectuees en visitant les profils affiches dans le **chat sidebar** (panneau lateral droit du dashboard montrant les utilisateurs en ligne).

---

## Comportement detaille (Wyylde)

### Etape par etape

1. **Navigation vers le dashboard** : le bot se rend sur `app.wyylde.com/fr-fr` si ce n'est pas deja fait
2. **Lecture du sidebar** : extraction de la liste des profils en ligne via le selecteur des boutons de chat (`button[class*="bg-neutral-lowest"][class*="cursor-pointer"]`)
3. **Filtrage** (optionnel) : si un filtre de type de profil est actif, seuls les profils correspondants sont conserves
4. **Pour chaque profil** :
   - Clic sur le bouton du profil dans le sidebar pour ouvrir le chat popup
   - Clic sur le lien membre (`a[href*="/member/"]`) pour naviguer vers la page profil complete
   - Attente du chargement de la page (`/member/` dans l'URL)
   - Extraction des informations du profil (nom, type, age, bio)
   - **Variation aleatoire** : 10% du temps, le bot se contente de naviguer sur le profil sans aucune action (simulation de comportement humain)
   - **Follow** : clic sur le bouton avec l'icone `svg[data-icon="user-plus"]` -- skippe aleatoirement 20% du temps
   - **Crush** : clic sur le bouton avec l'icone `svg[data-icon="wyylde-crush"]` -- skippe aleatoirement 30% du temps
   - Fermeture des popups eventuelles
   - Retour au dashboard
   - **Delai** entre chaque profil (configurable, par defaut 3-8 secondes)

### Verification du follow existant

Avant de cliquer "Suivre", le bot verifie si le bouton affiche "Ne plus suivre" ou "plus suivre". Si c'est le cas, le follow est ignore (le profil est deja suivi).

---

## Parametres configurables

| Parametre | Valeur par defaut | Plage | Description |
|-----------|-------------------|-------|-------------|
| `likes_per_session` | 50 | 1 - 500 | Nombre maximum de profils a visiter par session |
| `delay_min` | 3 | 0 - 60 | Delai minimum entre chaque profil (secondes) |
| `delay_max` | 8 | 1 - 120 | Delai maximum entre chaque profil (secondes) |
| `profile_filter` | (vide) | texte libre | Filtre sur le type de profil (ex: "Couple F Bi") |

### Filtres de profil disponibles (Wyylde)

Les types de profil pouvant etre utilises comme filtre :

- Couple F Bi
- Couple hetero
- Couple M Bi
- Femme hetero
- Femme Bi
- Homme hetero
- Homme Bi
- Travesti

Le filtre fonctionne par correspondance textuelle dans le texte affiche sur le bouton du sidebar.

---

## Limites journalieres

Le systeme de rate limiting (fichier `rate_limiter.py`) impose des limites quotidiennes :

| Action | Limite par jour |
|--------|-----------------|
| Likes | 100 |
| Follows | 80 |
| Crush | 50 |

Si la limite est atteinte, l'action est interrompue pour la journee. Le compteur se reinitialise a minuit. Les compteurs de plus de 7 jours sont automatiquement purges.

---

## Comportement anti-detection

Plusieurs mecanismes simulent un comportement humain :

- **Variation aleatoire du delai** : le delai entre chaque profil est un nombre aleatoire entre `delay_min` et `delay_max`
- **Skip aleatoire des actions** : 20% des follows et 30% des crush sont aleatoirement ignores
- **Navigation sans action** : 10% du temps, le bot visite simplement le profil sans interagir
- **Pauses longues** : toutes les 5 a 10 actions, une pause plus longue (8 a 45 secondes) simule un utilisateur qui regarde autre chose

---

## Plateformes supportees

### Wyylde (operationnel)
Fonctionnement complet : visite des profils du sidebar, follow, crush, filtrage par type.

### Tinder (base)
Like des profils via le bouton coeur ou le raccourci clavier (fleche droite). Pas de follow ni de crush (ces concepts n'existent pas sur Tinder). Gestion des popups de match.

### Meetic (base)
Like des profils sur la page Shuffle. Pas de follow ni de crush. Detection du bouton "J'aime" ou du bouton "Oui".

---

## Endpoint API

```
POST /api/likes/{platform}
```

**Body** (optionnel) :
```json
{
    "profile_filter": "Couple F Bi"
}
```

**Reponse** :
```json
{
    "status": "started",
    "message": "Likes lances sur wyylde ! Regarde le navigateur."
}
```

Le job s'execute en arriere-plan. Suivre la progression via :
```
GET /api/job-status/likes/{platform}
```

---

Voir aussi : [[03-Technique/securite-anti-ban|Securite et anti-ban]], [[01-Produit/plateformes|Plateformes]], [[03-Technique/api-reference|Reference API]]

# Resume quotidien par email

#boostrencontre #email #resume #fonctionnalite

---

## Statut : Implementee

---

## Principe

Un email de resume est envoye automatiquement chaque jour a une heure configurable. Il contient un recapitulatif de l'activite de la journee ecoulee sur toutes les plateformes actives.

---

## Contenu du resume

### Statistiques du jour

- Nombre de likes, follows, crushes par plateforme
- Nombre de messages envoyes (premiers messages + reponses)
- Taux de reponse du jour

### Conversations

- Nouvelles conversations ouvertes dans la journee (contact, plateforme, premier message)
- Conversations actives : nombre de tours echanges, etape en cours (accroche, interet, approfondissement, proposition)

### Alertes

- Limites journalieres proches ou atteintes (> 80% du quota)
- Indique la plateforme, l'action concernee, le compteur et le pourcentage

### Campagnes

- Campagnes actives avec progression (contacts faits / objectif)
- Funnel detaille (contacted, replied, conversation, met)

---

## Configuration

| Parametre | Description | Valeur par defaut |
|-----------|-------------|-------------------|
| `email_enabled` | Activer/desactiver l'envoi | `false` |
| `email_recipient` | Adresse email de destination | (a configurer) |
| `email_time` | Heure d'envoi quotidien (HH:MM) | `22:00` |
| `smtp_host` | Serveur SMTP | (a configurer) |
| `smtp_port` | Port SMTP (587 TLS, 465 SSL) | `587` |
| `smtp_user` | Identifiant SMTP | (a configurer) |
| `smtp_password` | Mot de passe SMTP | (a configurer) |

### Exemples SMTP courants

| Fournisseur | Host | Port |
|-------------|------|------|
| Gmail | smtp.gmail.com | 587 |
| Outlook | smtp-mail.outlook.com | 587 |
| OVH | ssl0.ovh.net | 465 |

Pour Gmail : utiliser un "mot de passe d'application" (pas le mot de passe du compte).

---

## Endpoints API

| Methode | URL | Description |
|---------|-----|-------------|
| `GET` | `/api/email-settings` | Lire la configuration email |
| `POST` | `/api/email-settings` | Modifier la configuration |
| `POST` | `/api/email-send-now` | Envoyer le resume maintenant (test) |
| `GET` | `/api/email-preview` | Previsualiser le resume en HTML |

### Exemple de configuration

```json
POST /api/email-settings
{
  "email_enabled": true,
  "email_recipient": "mon@email.com",
  "email_time": "22:00",
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_user": "mon@gmail.com",
  "smtp_password": "abcd efgh ijkl mnop"
}
```

---

## Implementation technique

- **Module** : `src/email_summary.py` (~280 lignes)
- **Routes** : `src/routes/email_summary.py` (~70 lignes)
- **Table DB** : `email_settings` (id, data JSON)
- **Scheduler** : boucle `asyncio` en background, calcule le delai jusqu'a l'heure configuree, envoie, puis attend le lendemain
- **Envoi SMTP** : execute dans un `run_in_executor` pour ne pas bloquer l'event loop
- **Fallback** : si l'envoi echoue, le resume HTML est sauvegarde en fichier local (`summary_YYYY-MM-DD.html`)
- **19 tests unitaires** couvrant settings, collecte de donnees, rendu HTML, envoi, scheduler

---

## Securite

- Le mot de passe SMTP n'est jamais expose dans l'API GET (seul `smtp_password_set: true/false` est renvoye)
- Le mot de passe vide en POST ne remplace pas un mot de passe existant
- Le scheduler ne demarre que si `email_enabled` est `true`

---

Voir aussi : [[02-Fonctionnalites/dashboard|Dashboard]], [[02-Fonctionnalites/mode-campagne|Mode campagne]], [[03-Technique/api-reference|Reference API]]

#email #fonctionnalite

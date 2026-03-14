# BoostRencontre - Plan de Sprints

## Vue d'ensemble

Refactoring et amelioration du bot BoostRencontre en 4 sprints.
Chaque sprint dure 1-2 jours, avec validation par les tests avant passage au suivant.

---

## Sprint 1 : Fondations (en cours)

**Objectif** : Poser les bases pour les evolutions futures — schema profil structure,
selecteurs centralises, corrections securite, couverture de tests.

### Taches

| ID | Tache | Agent | Statut | Priorite |
|----|-------|-------|--------|----------|
| S1-01 | Creer `src/models/profile_schema.py` — schema 10 categories profil + validation | coordinator | En cours | Haute |
| S1-02 | Creer `src/metrics/tracker.py` — tracking messages envoyes/reponses | coordinator | En cours | Haute |
| S1-03 | Centraliser selecteurs Wyylde dans `src/platforms/selectors/wyylde.py` | refactor-agent | En cours | Haute |
| S1-04 | Migrer `MY_PROFILE` de ai_messages.py vers DB (table `user_profile` enrichie) | profile-agent | En cours | Haute |
| S1-05 | Ajouter validation/sanitization inputs API (XSS, injection) | security-agent | En cours | Haute |
| S1-06 | Etendre `tests/` — couvrir nouveaux modules (profile_schema, metrics, selectors) | test-agent | En cours | Moyenne |
| S1-07 | Creer `src/models/__init__.py` et `src/metrics/__init__.py` | coordinator | En cours | Haute |
| S1-08 | Documenter le plan de sprints (`docs/SPRINT_PLAN.md`) | coordinator | En cours | Moyenne |

### Criteres de succes Sprint 1

- [ ] `profile_schema.py` exporte PROFILE_CATEGORIES, IDENTITY_FIELDS, validate_profile()
- [ ] `tracker.py` fournit log_message_sent(), check_reply_received(), get_stats()
- [ ] Selecteurs Wyylde centralises dans un module dedie (plus de magic strings)
- [ ] Profil utilisateur avec 10 categories editable via `/profile`
- [ ] Inputs API valides et echappes
- [ ] `pytest tests/ -v` passe a 100% avec >= 50 tests

### Dependances

```
S1-01 (schema) ──> S1-04 (migration profil DB)
S1-01 (schema) ──> S1-06 (tests)
S1-02 (metrics) ──> S1-06 (tests)
S1-03 (selecteurs) ──> S1-06 (tests)
S1-05 (securite) ──> S1-06 (tests)
```

---

## Sprint 2 : Integration

**Objectif** : Exploiter le schema profil enrichi pour ameliorer la qualite des messages IA
et introduire le scoring de compatibilite.

### Taches

| ID | Tache | Agent | Priorite |
|----|-------|-------|----------|
| S2-01 | Creer `src/messaging/template_matcher.py` — templates de messages par categorie | messaging-agent | Haute |
| S2-02 | Scoring compatibilite profil visiteur vs MY_PROFILE | scoring-agent | Haute |
| S2-03 | Preview message avant envoi (dry-run mode) | ui-agent | Moyenne |
| S2-04 | Enrichir prompts IA avec les 10 categories du profil | messaging-agent | Haute |
| S2-05 | Ajouter filtre par score minimum dans le bot_engine | engine-agent | Moyenne |
| S2-06 | Tests template_matcher + scoring | test-agent | Haute |

### Criteres de succes Sprint 2

- [ ] `template_matcher.py` selectionne un template selon bio cible + profil utilisateur
- [ ] Score compatibilite 0-100 calcule pour chaque profil visite
- [ ] Preview message visible dans le dashboard avant envoi
- [ ] Prompts IA utilisent toutes les categories pertinentes du profil
- [ ] Filtre score minimum configurable dans settings
- [ ] Tests couvrent template_matcher et scoring

### Dependances

```
Sprint 1 complet ──> Sprint 2
S2-01 (templates) ──> S2-04 (prompts enrichis)
S2-02 (scoring) ──> S2-05 (filtre score)
S2-01 + S2-02 ──> S2-06 (tests)
```

---

## Sprint 3 : Dashboard

**Objectif** : Tableau de bord avec metriques visuelles et detection automatique
des reponses pour mesurer l'efficacite.

### Taches

| ID | Tache | Agent | Priorite |
|----|-------|-------|----------|
| S3-01 | Vue metriques dans le dashboard (graphiques sent/replied par style) | ui-agent | Haute |
| S3-02 | Detection automatique des reponses (match message envoye <-> reply recu) | engine-agent | Haute |
| S3-03 | Export CSV des statistiques | ui-agent | Basse |
| S3-04 | Historique conversations avec timeline | ui-agent | Moyenne |
| S3-05 | Notifications visuelles nouvelles reponses | ui-agent | Moyenne |
| S3-06 | Tests endpoints metriques + detection replies | test-agent | Haute |

### Criteres de succes Sprint 3

- [ ] Dashboard affiche taux de reponse par style et par template
- [ ] Detection auto des reponses avec mise a jour du tracker
- [ ] Export CSV fonctionnel
- [ ] Historique conversations navigable
- [ ] >= 60 tests passent

### Dependances

```
Sprint 2 complet ──> Sprint 3
S3-02 (detection) ──> S3-01 (metriques)
S3-01 (metriques) ──> S3-03 (export)
```

---

## Sprint 4 : Tinder/Meetic avances (optionnel)

**Objectif** : Etendre les fonctionnalites avancees (messages IA, scoring, templates)
aux plateformes Tinder et Meetic.

### Taches

| ID | Tache | Agent | Priorite |
|----|-------|-------|----------|
| S4-01 | Explorer et documenter selecteurs Tinder (via agent explorateur) | explorer-agent | Haute |
| S4-02 | Explorer et documenter selecteurs Meetic | explorer-agent | Haute |
| S4-03 | Implementer messages IA Tinder (matches -> messages) | platform-agent | Haute |
| S4-04 | Implementer messages IA Meetic | platform-agent | Haute |
| S4-05 | Centraliser selecteurs Tinder/Meetic (comme Wyylde Sprint 1) | refactor-agent | Moyenne |
| S4-06 | Tests multi-plateformes | test-agent | Haute |

### Criteres de succes Sprint 4

- [ ] Selecteurs Tinder et Meetic documentes dans `docs/`
- [ ] Messages IA fonctionnels sur Tinder et Meetic
- [ ] Scoring et templates appliques aux 3 plateformes
- [ ] Tests multi-plateformes passent

### Dependances

```
Sprint 2 complet ──> Sprint 4 (scoring + templates necessaires)
S4-01 (explore Tinder) ──> S4-03 (messages Tinder)
S4-02 (explore Meetic) ──> S4-04 (messages Meetic)
```

---

## Chemin critique

```
S1-01 (schema) -> S1-04 (migration) -> S2-04 (prompts enrichis) -> S3-01 (metriques)
S1-02 (metrics) -> S3-02 (detection replies) -> S3-01 (dashboard metriques)
S1-03 (selecteurs) -> S2-01 (templates) -> S2-04 (prompts)
```

## Risques

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Selecteurs Wyylde changent (mise a jour site) | Messages/likes ne fonctionnent plus | Agent explorateur + docs auto-generes |
| Rate limiting OpenAI API | Messages IA bloques | Retry avec backoff exponentiel, cache local |
| Profils navigateur corrompus (NTFS) | Sessions perdues | Stockage local uniquement (~/.boostrencontre/) |
| Tests flaky (Playwright) | CI instable | Mocks Playwright dans les tests unitaires |
| Changement structure DOM sidebar | reply_to_unread casse | Screenshots de reference + validation visuelle |

---

*Derniere mise a jour : 2026-03-09*

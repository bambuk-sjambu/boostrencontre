# GitHub Project & Issues

## Liens

- **Repository**: https://github.com/bambuk-sjambu/boostrencontre
- **Kanban Board**: https://github.com/users/bambuk-sjambu/projects/4
- **Issues**: https://github.com/bambuk-sjambu/boostrencontre/issues

## Workflow

1. Chaque tâche = 1 Issue avec label module
2. Issues dans le Kanban: Backlog → To Do → In Progress → Review → Done
3. Commit messages référencent l'Issue: `fix(api): ... fixes #1`

## Labels

| Label | Couleur | Usage |
|-------|---------|-------|
| `core` | Vert | API FastAPI, middleware |
| `platform` | Bleu | Wyylde, Tinder, Meetic |
| `messaging` | Violet | OpenAI, prompts, templates |
| `automation` | Orange | Likes, replies, auto-reply |
| `dashboard` | Jaune | UI, stats, templates HTML |
| `security` | Rouge | Anti-ban, credentials |
| `tests` | Bleu clair | QA, pytest |
| `database` | Bleu foncé | SQLite, migrations |
| `enhancement` | Cyan | Nouvelles features |
| `bug` | Rouge | Corrections |

## Issues par Module (12 créées le 2026-03-14)

### Core
| # | Titre | Status |
|---|-------|--------|
| 1 | [core/api] FastAPI routes & middleware | Backlog |

### Platforms
| # | Titre | Status |
|---|-------|--------|
| 2 | [platforms/wyylde] Full platform support | Backlog |
| 3 | [platforms/tinder] Base platform implementation | Backlog |
| 4 | [platforms/meetic] Base platform implementation | Backlog |

### Messaging
| # | Titre | Status |
|---|-------|--------|
| 5 | [messaging/ai] OpenAI integration & prompts | Backlog |
| 6 | [messaging/conversation] Multi-turn conversations | Backlog |

### Automation
| # | Titre | Status |
|---|-------|--------|
| 7 | [automation/likes] Like automation with scoring | Backlog |
| 8 | [automation/replies] Auto-reply system | Backlog |

### Dashboard
| # | Titre | Status |
|---|-------|--------|
| 9 | [dashboard] UI & statistics | Backlog |

### Security
| # | Titre | Status |
|---|-------|--------|
| 10 | [security] Anti-ban & credentials | Backlog |

### Tests
| # | Titre | Status |
|---|-------|--------|
| 11 | [tests] Test suite maintenance (386 tests) | Backlog |

### Database
| # | Titre | Status |
|---|-------|--------|
| 12 | [database] SQLite async & migrations | Backlog |

## Commandes GitHub CLI utiles

```bash
# Lister les issues
gh issue list --repo bambuk-sjambu/boostrencontre

# Créer une issue
gh issue create --repo bambuk-sjambu/boostrencontre --title "[module] Titre" --body "Description" --label "core"

# Voir le project
gh project view 4 --owner bambuk-sjambu

# Ajouter une issue au project
gh project item-add 4 --owner bambuk-sjambu --url https://github.com/bambuk-sjambu/boostrencontre/issues/N

# Changer le status dans le project
gh project item-edit --project-id PVT_kwHOBEIRts4BRtal --id ITEM_ID --field-id FIELD_ID --single-select-option-id OPTION_ID
```

## Convention de nommage Issues

Format: `[module/feature] Titre court`

Exemples:
- `[core/api] Add rate limiting`
- `[platforms/wyylde] Fix sidebar detection`
- `[messaging/ai] Improve prompt quality`
- `[security] Add proxy rotation`

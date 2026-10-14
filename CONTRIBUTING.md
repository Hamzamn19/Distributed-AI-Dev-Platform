# Contributing

## Branches
- `main` is always working. Nobody pushes to it directly.
- Create one short-lived branch per Trello card: `feat/s1-14-fastapi-skeleton`, `fix/s2-08-selection-bug`, `docs/s1-06-onboarding`.

## Commits
Short, present tense, with the card ID: `S1-14: add health check endpoint`.

## Pull requests
1. Push your branch and open a pull request into `main`. Fill in the template.
2. One teammate reviews it (your buddy for the card). Review within 2 days.
3. CI must be green (once S1-09 is done).
4. Merge, delete the branch, move the Trello card.

## Definition of Done (short version)
- It works and was tested by someone other than its author.
- A teammate reviewed it before merging into `main`.
- It meets the acceptance criteria on the card.
- It is shown in the sprint demo.
- The author can explain it at the Review.

## Secrets
Never commit passwords, tokens or API keys. Use `.env` (ignored by git) and keep `.env.example` up to date.

## Using AI tools
Welcome on every card. Rule: you must understand and be able to defend what you merge.

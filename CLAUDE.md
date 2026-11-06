# CLAUDE.md

## Git workflow: the owner makes all commits

- Never run `git commit`, `git push` or `git stash`, never create pull requests, and don't stage files (`git add`).
- Work in steps. After each step, stop and give:
  - the files changed
  - a 2–3 sentence explanation
  - a suggested conventional commit message (e.g. `docs: ...`, `ci: ...`, `fix: ...`)
  - the exact command, e.g. `git add <files> && git commit -m "..."`
- Wait for the owner to say "next" before starting the following step.
- Never commit or stage secrets: `.env`, `terraform/terraform.tfvars` and `terraform/terraform.tfstate*` stay untracked.

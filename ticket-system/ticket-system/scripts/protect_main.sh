#!/usr/bin/env bash
# Қолдану: ./scripts/protect_main.sh OWNER/REPO   (gh CLI авторизацияланған болуы керек)
set -euo pipefail
REPO="${1:?OWNER/REPO көрсетіңіз}"

gh api -X PUT "repos/${REPO}/branches/main/protection" --input - <<JSON
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["Линтер (flake8)", "Тесттер (Python 3.11)", "Тесттер (Python 3.12)",
                 "Осалдықтарды тексеру (Trivy + OSV)", "Құрастыру және артефакт"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "require_last_push_approval": true
  },
  "required_linear_history": true,
  "required_conversation_resolution": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "restrictions": null
}
JSON
echo "main ветка қорғалды: ${REPO}"

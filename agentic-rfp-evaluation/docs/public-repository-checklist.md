# Public GitHub Repository Checklist

## Before the first public push

- [ ] Create a new repository with a clear name such as `procureai-rfp-evaluator`.
- [ ] Add a README with purpose, setup, architecture, screenshots, limitations, and roadmap.
- [ ] Add `docs/architecture.md`, `docs/data-flow-diagrams.md`, and `docs/control-flow-diagram.md`.
- [ ] Add the actual dependency manifest (`requirements.txt` or `pyproject.toml`) from the project.
- [ ] Add a `.gitignore` before staging files.
- [ ] Include only synthetic sample proposals that you created or have permission to publish.
- [ ] Run the app from a clean environment and verify the setup instructions.
- [ ] Verify that no secrets, real supplier data, customer data, database records, or local vector-store files are staged.
- [ ] Add a LICENSE only if you have chosen the license terms.
- [ ] Add tests or clearly label the current test coverage and known limitations.

## Suggested `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyd
.venv/
venv/
env/

# Secrets
.env
.env.*
!.env.example
.streamlit/secrets.toml

# Local data and generated stores
 data/chroma_db/
data/rfp_evaluation.db
*.sqlite
*.sqlite3
*.db

# Local inputs: publish only deliberately selected synthetic samples
# If synthetic PDFs are intentionally committed, use a dedicated folder such as
# data/sample_proposals/ and explicitly allow only those reviewed files.
data/input/

# IDE and OS
.vscode/
.idea/
.DS_Store
Thumbs.db

# Logs and generated exports
*.log
rfp_evaluation_*.json
```

Review the ignore patterns against the actual folder structure before committing. If the ten proposals are synthetic and intended as public demo data, put the approved examples in a clearly named sample-data folder and selectively add them.

## Safe publishing commands (PowerShell)

Run these from the project root after adding and reviewing `.gitignore`:

```powershell
git init
git status --short
git add .gitignore README.md docs src app.py requirements.txt
git status --short
```

The `git add` command above is an example; adjust paths to match the real project. Review the staged files before committing. Do not use `git add .` until the ignore rules and staged file list have been inspected.

```powershell
git commit -m "Initial ProcureAI RFP evaluation prototype"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/procureai-rfp-evaluator.git
git push -u origin main
```

Replace the placeholder remote with the actual repository URL.

## Public repository: what evaluators can access

Yes. Anyone can browse a public repository without signing in, so an evaluator can inspect the source, README, diagrams, commit history, and permitted sample data. A public repo does **not** automatically make the Streamlit app runnable online; deployment is a separate step. Never publish secrets or private data, even temporarily—deleting a file later does not remove it from Git history in a reliable way.

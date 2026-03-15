# GitHub Migration Guide - Kitchen API

**Status**: Ready for GitHub Publication ✅  
**Date**: February 1, 2026  
**Current State**: iCloud → GitHub Migration

---

## Pre-Migration Checklist

- [x] `.gitignore` configured and tested
- [x] All 322 unit tests passing
- [x] Documentation organized (100+ docs)
- [x] Production code ready (200+ Python files)
- [ ] Create GitHub repository
- [ ] Initialize Git locally
- [ ] First push to GitHub

---

## Step 1: Create GitHub Repository

1. Go to [github.com/new](https://github.com/new)
2. **Repository Settings**:
   - **Name**: `kitchen-api` (or `kitchen-backend`)
   - **Description**: "Production-ready Kitchen API with ABAC, billing, and subscription management"
   - **Visibility**: 🔒 **Private** (recommended for business code)
   - **DO NOT** initialize with README, .gitignore, or license (you already have these)

---

## Step 2: Initialize Git Locally

```bash
# Navigate to your project
cd ~/Desktop/local/kitchen

# Initialize Git
git init

# Verify .gitignore is working
git status
# Should NOT show: venv/, .cursor/, *.log, __pycache__/, .pytest_cache/

# Add all files
git add .

# Check what will be committed
git status

# Create initial commit
git commit -m "Initial commit: Production-ready Kitchen API

- 322 passing unit tests
- Comprehensive ABAC authorization
- Billing and subscription management
- Archival system with automated cron jobs
- E2E Postman test collection
- Complete API documentation
"
```

---

## Step 3: Connect to GitHub

```bash
# Add GitHub remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/kitchen-api.git

# Rename branch to main (if needed)
git branch -M main

# Push to GitHub
git push -u origin main
```

---

## Step 4: Verify Upload

1. Go to your GitHub repository
2. **Check these are present**:
   - ✅ `app/` folder with all Python code
   - ✅ `docs/` folder with documentation
   - ✅ `requirements.txt`
   - ✅ `pytest.ini`
   - ✅ `app/db/seed.sql` and other SQL files

3. **Check these are NOT present**:
   - ❌ `venv/` folder
   - ❌ `.cursor/` folder
   - ❌ `__pycache__/` folders
   - ❌ `*.log` files
   - ❌ `.pytest_cache/` folder

---

## Step 5: Set Up Branch Protection (Recommended)

1. Go to **Settings** → **Branches**
2. Add rule for `main` branch:
   - ✅ Require pull request before merging
   - ✅ Require status checks to pass (add after Step 6)
   - ✅ Require conversation resolution before merging

---

## Step 6: Set Up GitHub Actions (Optional but Recommended)

Create `.github/workflows/tests.yml`:

```yaml
name: Run Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python 3.9
      uses: actions/setup-python@v4
      with:
        python-version: 3.9
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-test.txt
    
    - name: Run tests
      run: |
        pytest app/tests/ -v --tb=short
```

---

## Post-Migration Workflow

### Daily Development
```bash
# Check status
git status

# Add changes
git add .

# Commit with meaningful message
git commit -m "Fix: Corrected credit validation logic for edge cases"

# Push to GitHub
git push
```

### Feature Development
```bash
# Create feature branch
git checkout -b feature/fastapi-upgrade

# Make changes, test them
# ... make changes ...
pytest app/tests/

# Commit changes
git add .
git commit -m "Upgrade FastAPI to 0.109.0"

# Push feature branch
git push -u origin feature/fastapi-upgrade

# Create Pull Request on GitHub
# Merge when ready
# Delete feature branch after merge
```

### Bug Fixes
```bash
# Create hotfix branch
git checkout -b hotfix/credit-calculation-bug

# Fix the bug
# ... make changes ...

# Test
pytest app/tests/

# Commit and push
git add .
git commit -m "Fix: Credit calculation rounding error"
git push -u origin hotfix/credit-calculation-bug

# Create PR, merge, delete branch
```

---

## Common Git Commands Reference

```bash
# View commit history
git log --oneline

# See what changed
git diff

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Discard all local changes
git reset --hard HEAD

# Create and switch to new branch
git checkout -b branch-name

# Switch branches
git checkout main

# Pull latest changes
git pull

# View all branches
git branch -a

# Delete local branch
git branch -d branch-name

# Delete remote branch
git push origin --delete branch-name
```

---

## Troubleshooting

### Problem: Large files being rejected
**Solution**: Check `.gitignore` is working
```bash
git rm --cached large-file.ext
git commit -m "Remove large file from tracking"
```

### Problem: Accidentally committed secrets
**Solution**: Remove from history (BEFORE pushing)
```bash
git rm --cached .env
git commit -m "Remove .env from tracking"
```

If already pushed, consider rotating credentials and using git-filter-branch or BFG Repo-Cleaner.

### Problem: Merge conflicts
**Solution**:
```bash
git status  # See conflicted files
# Edit files to resolve conflicts
git add .
git commit -m "Resolve merge conflicts"
```

---

## What to Include vs Exclude

### ✅ INCLUDE in Git
- All Python source code (`app/`, `scripts/`)
- Configuration files (`pytest.ini`, `requirements.txt`)
- Database schemas and seed files (`app/db/*.sql`)
- Documentation (`docs/`)
- Static assets for testing (`static/placeholders/`)
- Postman collections (`docs/postman/collections/*.json`)
- CI/CD workflows (`.github/workflows/`)

### ❌ EXCLUDE from Git (in `.gitignore`)
- Virtual environments (`venv/`, `kenv/`)
- Environment variables (`.env`)
- Generated files (`__pycache__/`, `*.pyc`)
- IDE folders (`.cursor/`, `.idea/`, `.vscode/`)
- Log files (`*.log`, `server.log`)
- Test cache (`.pytest_cache/`)
- Database files (`*.db`, `*.sqlite`)
- Production backups (`*_backup.sql`, `*_dump.sql`)
- Credentials and secrets (`docs/local/`)

---

## Next Steps After Migration

1. **Update README.md** with:
   - Repository badges (tests passing, etc.)
   - Quick start guide
   - Installation instructions
   - Link to documentation

2. **Set up CI/CD** for automated testing

3. **Configure deployment** pipeline

4. **Invite collaborators** (if team project)

5. **Create first issue** for FastAPI upgrade

6. **Consider adding**:
   - LICENSE file (if open source)
   - CONTRIBUTING.md guidelines
   - CODE_OF_CONDUCT.md

---

## Benefits You'll Gain

- ✅ **Safe experimentation** with branches
- ✅ **Time travel** - revert any change
- ✅ **Collaboration** - multiple developers
- ✅ **Code review** - PR workflow
- ✅ **Audit trail** - who changed what, when, why
- ✅ **Automated testing** - CI/CD
- ✅ **Professional portfolio** - showcase your work
- ✅ **Disaster recovery** - never lose code again

---

**Questions?** Check GitHub documentation: https://docs.github.com

**Ready to migrate?** Follow Step 2 above! 🚀

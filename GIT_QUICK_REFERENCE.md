# Git Quick Reference - Kitchen API

**For**: Daily development workflow  
**Audience**: Developers migrating from iCloud to GitHub

---

## 🚀 Quick Start (First Time Only)

```bash
# 1. Initialize Git
cd "/Users/cdeachaval/Library/Mobile Documents/com~apple~CloudDocs/Desktop/local/kitchen"
git init

# 2. Add all files
git add .

# 3. First commit
git commit -m "Initial commit: Production-ready Kitchen API"

# 4. Connect to GitHub
git remote add origin https://github.com/YOUR_USERNAME/kitchen-api.git
git branch -M main
git push -u origin main
```

---

## 📝 Daily Development (Most Common)

### Save Your Work
```bash
# See what changed
git status

# Add all changes
git add .

# Commit with message
git commit -m "Fix: Credit validation bug"

# Push to GitHub
git push
```

### Get Latest Code
```bash
# Pull changes from GitHub
git pull
```

---

## 🌿 Working with Branches

### Create Feature Branch
```bash
# Create and switch to new branch
git checkout -b feature/fastapi-upgrade

# Make changes, then commit
git add .
git commit -m "Upgrade FastAPI to 0.109.0"

# Push branch to GitHub
git push -u origin feature/fastapi-upgrade
```

### Switch Between Branches
```bash
# Switch to main
git checkout main

# Switch to feature branch
git checkout feature/fastapi-upgrade

# See all branches
git branch -a
```

### Merge Branch (After Testing)
```bash
# Switch to main
git checkout main

# Merge feature branch
git merge feature/fastapi-upgrade

# Push to GitHub
git push

# Delete branch (optional)
git branch -d feature/fastapi-upgrade
git push origin --delete feature/fastapi-upgrade
```

---

## ↩️ Undo Changes

### Undo Uncommitted Changes
```bash
# Discard changes in one file
git checkout -- filename.py

# Discard ALL uncommitted changes
git reset --hard HEAD
```

### Undo Last Commit (Keep Changes)
```bash
# Undo commit, keep changes in working directory
git reset --soft HEAD~1
```

### Undo Last Commit (Discard Changes)
```bash
# WARNING: This deletes your changes!
git reset --hard HEAD~1
```

### Undo a Pushed Commit
```bash
# Create a new commit that undoes the changes
git revert COMMIT_HASH

# Push the revert
git push
```

---

## 🔍 View History & Changes

### View Commit History
```bash
# Simple one-line format
git log --oneline

# Last 5 commits
git log --oneline -5

# Detailed history
git log
```

### See What Changed
```bash
# See uncommitted changes
git diff

# See changes in a specific file
git diff filename.py

# See changes in last commit
git show
```

### Find Who Changed What
```bash
# See who last modified each line
git blame filename.py
```

---

## 🚨 Emergency Fixes

### Hotfix on Production
```bash
# Create hotfix branch from main
git checkout main
git checkout -b hotfix/critical-bug

# Fix the bug, test it
pytest app/tests/

# Commit and push
git add .
git commit -m "Hotfix: Fix critical credit calculation bug"
git push -u origin hotfix/critical-bug

# Merge to main (or create PR on GitHub)
git checkout main
git merge hotfix/critical-bug
git push

# Delete hotfix branch
git branch -d hotfix/critical-bug
```

---

## 🔧 Configuration

### Set Your Identity (First Time)
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### View Configuration
```bash
git config --list
```

---

## 📦 Handling .gitignore

### Check if File is Ignored
```bash
git check-ignore -v filename
```

### Remove File from Tracking (Already Committed)
```bash
# Remove from Git but keep locally
git rm --cached filename

# Commit the removal
git commit -m "Remove filename from tracking"
```

---

## 🤝 Working with Remotes

### View Remotes
```bash
git remote -v
```

### Update Remote URL
```bash
git remote set-url origin https://github.com/NEW_USERNAME/kitchen-api.git
```

---

## 🎯 Common Workflows

### Workflow 1: Quick Fix
```bash
git pull                  # Get latest
# ... make changes ...
pytest app/tests/         # Test
git add .                 # Stage changes
git commit -m "Fix: ..."  # Commit
git push                  # Push to GitHub
```

### Workflow 2: New Feature
```bash
git checkout main                    # Start from main
git pull                             # Get latest
git checkout -b feature/new-thing    # Create branch
# ... develop feature ...
pytest app/tests/                    # Test
git add .                            # Stage
git commit -m "Add: new feature"     # Commit
git push -u origin feature/new-thing # Push
# Create PR on GitHub, review, merge
```

### Workflow 3: Code Review
```bash
# On GitHub: Create Pull Request
# Team reviews code
# Address feedback with new commits
git add .
git commit -m "Address review feedback"
git push
# Merge PR on GitHub when approved
```

---

## ⚠️ Common Mistakes & Fixes

### Mistake: Committed Sensitive Data
```bash
# BEFORE pushing to GitHub
git rm --cached .env
git commit -m "Remove .env from tracking"

# AFTER pushing to GitHub
# Rotate credentials immediately!
# Use git-filter-branch or BFG Repo-Cleaner
```

### Mistake: Committed to Wrong Branch
```bash
# Reset current branch
git reset --soft HEAD~1

# Switch to correct branch
git checkout correct-branch

# Commit there
git add .
git commit -m "Correct commit message"
```

### Mistake: Large Files Rejected
```bash
# Remove large file
git rm --cached large-file.zip

# Add to .gitignore
echo "*.zip" >> .gitignore

# Commit
git add .gitignore
git commit -m "Remove large file and ignore zips"
```

---

## 📊 Useful Aliases

Add these to your `~/.gitconfig`:

```ini
[alias]
    st = status
    co = checkout
    br = branch
    ci = commit
    unstage = reset HEAD --
    last = log -1 HEAD
    visual = log --oneline --graph --all --decorate
```

Then use:
```bash
git st           # Instead of git status
git co main      # Instead of git checkout main
git br           # Instead of git branch
git visual       # Pretty branch visualization
```

---

## 🎓 Learning Path

### Week 1: Master These
- `git status`
- `git add .`
- `git commit -m "message"`
- `git push`
- `git pull`

### Week 2: Add These
- `git checkout -b branch-name`
- `git merge`
- `git log --oneline`
- `git diff`

### Week 3: Add These
- `git reset`
- `git revert`
- `git blame`
- `git stash`

### Month 2+: Advanced
- Rebasing
- Cherry-picking
- Interactive rebase
- Submodules

---

## 🆘 When Things Go Wrong

### "Everything is broken!"
```bash
# See what's different from last commit
git status
git diff

# If you want to start over
git reset --hard HEAD

# Get back to clean main branch
git checkout main
git reset --hard origin/main
```

### "I can't push!"
```bash
# Someone else pushed first
git pull --rebase
git push

# If still fails
git pull
# Resolve conflicts if any
git push
```

### "I lost my changes!"
```bash
# Check reflog (Git saves everything for ~30 days)
git reflog

# Restore from reflog
git checkout HEAD@{1}
```

---

## 💡 Pro Tips

1. **Commit often**: Small, frequent commits are better than large ones
2. **Write good messages**: "Fix bug" is bad, "Fix credit calculation rounding error" is good
3. **Pull before push**: Always `git pull` before `git push`
4. **Test before commit**: Run `pytest` before committing
5. **Use branches**: Never commit directly to `main` for features
6. **Read the output**: Git tells you what to do in most error messages

---

## 📚 Further Reading

- [Git Documentation](https://git-scm.com/doc)
- [GitHub Guides](https://guides.github.com)
- [Pro Git Book (Free)](https://git-scm.com/book/en/v2)
- [Oh Shit, Git!?!](https://ohshitgit.com/) - Fixes for common mistakes

---

## 🎯 Your Most Important Commands

For daily work, you'll use these 80% of the time:

```bash
git status      # What changed?
git add .       # Stage everything
git commit -m   # Save changes
git push        # Upload to GitHub
git pull        # Download from GitHub
git checkout -b # New branch
git checkout    # Switch branch
git log         # View history
```

---

**Print this page and keep it by your desk!** 📄

*Last Updated: February 1, 2026*

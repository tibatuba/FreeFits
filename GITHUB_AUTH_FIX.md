# Fix GitHub Authentication on EC2

## Problem
GitHub no longer accepts passwords for HTTPS Git operations. You'll see:
```
remote: Invalid username or token. Password authentication is not supported for Git operations.
```

## Solution 1: Use Personal Access Token (Recommended)

### Step 1: Create Token on GitHub
1. Go to: https://github.com/settings/tokens
2. Click **"Generate new token"** → **"Generate new token (classic)"**
3. Name: `EC2-Deployment`
4. Expiration: Choose 90 days or "No expiration" (for capstone)
5. Select scopes: Check **`repo`** (gives full access to repositories)
6. Click **"Generate token"**
7. **COPY THE TOKEN** - you won't see it again!

### Step 2: Use Token on EC2
```bash
git clone https://github.com/tibatuba/FreeFits.git
```
When prompted:
- **Username:** `tibatuba`
- **Password:** Paste your Personal Access Token (NOT your GitHub password)

## Solution 2: Make Repository Public (Easiest)

1. Go to: https://github.com/tibatuba/FreeFits/settings
2. Scroll to **"Danger Zone"**
3. Click **"Change visibility"** → **"Make public"**
4. Confirm

Then clone without authentication:
```bash
git clone https://github.com/tibatuba/FreeFits.git
```

## Solution 3: Use SSH (Advanced)

### On Your Windows Machine:
```powershell
# Generate SSH key (if you don't have one)
ssh-keygen -t ed25519 -C "your_email@example.com"

# Copy public key
cat ~/.ssh/id_ed25519.pub
```

### Add to GitHub:
1. Go to: https://github.com/settings/keys
2. Click **"New SSH key"**
3. Paste your public key
4. Save

### On EC2:
```bash
# Copy your private key to EC2 (use scp from Windows)
# Then:
git clone git@github.com:tibatuba/FreeFits.git
```

## Recommendation
For a capstone project, **Solution 2 (Make Public)** is the easiest and fastest.




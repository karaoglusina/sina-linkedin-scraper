# GitHub SSH Setup Guide

A step-by-step guide to set up SSH authentication with GitHub on macOS.

---

## Why SSH?

SSH (Secure Shell) provides a secure way to authenticate with GitHub without entering your username and password every time. Once set up, Git operations like `push` and `pull` work seamlessly.

---

## Step 1: Check for Existing SSH Keys

```bash
ls -la ~/.ssh
```

Look for files named `id_ed25519` and `id_ed25519.pub` (or `id_rsa` and `id_rsa.pub` for older keys).

---

## Step 2: Generate a New SSH Key

If no keys exist, generate one:

```bash
ssh-keygen -t ed25519 -C "your_email@example.com" -f ~/.ssh/id_ed25519 -N ""
```

**Flags explained:**
- `-t ed25519`: Use the Ed25519 algorithm (modern, secure, fast)
- `-C "email"`: Add a comment/label to identify the key
- `-f ~/.ssh/id_ed25519`: Specify the file location
- `-N ""`: Empty passphrase (or remove this flag to be prompted)

**Interactive alternative:**
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```
Then press Enter to accept defaults.

---

## Step 3: Start the SSH Agent

The SSH agent manages your keys in memory:

```bash
eval "$(ssh-agent -s)"
```

You should see: `Agent pid 12345`

---

## Step 4: Add Your Key to the Agent

```bash
ssh-add ~/.ssh/id_ed25519
```

You should see: `Identity added: /Users/you/.ssh/id_ed25519`

---

## Step 5: Copy Your Public Key

Display the public key:

```bash
cat ~/.ssh/id_ed25519.pub
```

Copy the entire output (starts with `ssh-ed25519` and ends with your email).

**Quick copy to clipboard (macOS):**
```bash
pbcopy < ~/.ssh/id_ed25519.pub
```

---

## Step 6: Add the Key to GitHub

1. Go to [github.com/settings/keys](https://github.com/settings/keys)
2. Click **"New SSH key"**
3. Fill in the form:
   - **Title**: A descriptive name (e.g., "MacBook Pro", "Work Laptop")
   - **Key type**: Authentication Key
   - **Key**: Paste your public key
4. Click **"Add SSH key"**

---

## Step 7: Test the Connection

```bash
ssh -T git@github.com
```

**Success message:**
```
Hi username! You've successfully authenticated, but GitHub does not provide shell access.
```

---

## Step 8: Configure Git Remote (if needed)

If your repository was set up with HTTPS, switch to SSH:

```bash
# Check current remote
git remote -v

# Change from HTTPS to SSH
git remote set-url origin git@github.com:USERNAME/REPOSITORY.git
```

---

## Troubleshooting

### "Permission denied (publickey)"

1. **Check if ssh-agent is running:**
   ```bash
   eval "$(ssh-agent -s)"
   ```

2. **Check if key is added:**
   ```bash
   ssh-add -l
   ```
   If empty, add it:
   ```bash
   ssh-add ~/.ssh/id_ed25519
   ```

3. **Verify the key on GitHub matches:**
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```
   Compare with the key in your GitHub settings.

### "Could not open a connection to your authentication agent"

Start the agent first:
```bash
eval "$(ssh-agent -s)"
```

### SSH agent doesn't persist after terminal restart

Add this to your `~/.zshrc` or `~/.bashrc`:

```bash
# Start SSH agent if not running
if [ -z "$SSH_AUTH_SOCK" ]; then
   eval "$(ssh-agent -s)" > /dev/null
   ssh-add ~/.ssh/id_ed25519 2> /dev/null
fi
```

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `ssh-keygen -t ed25519 -C "email"` | Generate new key |
| `eval "$(ssh-agent -s)"` | Start SSH agent |
| `ssh-add ~/.ssh/id_ed25519` | Add key to agent |
| `ssh-add -l` | List keys in agent |
| `cat ~/.ssh/id_ed25519.pub` | Show public key |
| `ssh -T git@github.com` | Test GitHub connection |

---

## Security Best Practices

1. **Use Ed25519** over RSA (more secure, shorter keys)
2. **Use a passphrase** for sensitive environments
3. **Never share your private key** (`id_ed25519` without `.pub`)
4. **Rotate keys periodically** for high-security projects

# Development environment

Local setup should match GitHub Actions so the same Python version and dependencies run everywhere.

## Quick fix: get `python3` to 3.10 now

If `python3 --version` still shows 3.9.x, run these in your terminal **in order**:

```bash
# 1. Install Python 3.10 (one-time)
brew install python@3.10

# 2. Use it in this terminal (Apple Silicon Mac)
export PATH="/opt/homebrew/opt/python@3.10/bin:$PATH"

# On Intel Mac, use this instead of the line above:
# export PATH="/usr/local/opt/python@3.10/bin:$PATH"

# 3. Confirm
python3 --version
# Should print: Python 3.10.x
```

To make the change permanent, add the `export PATH=...` line to your shell config, then reopen the terminal or run `source ~/.zshrc` (or `source ~/.bash_profile`):

```bash
echo 'export PATH="/opt/homebrew/opt/python@3.10/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

(Use `~/.bash_profile` instead of `~/.zshrc` if you use bash.)

## Python 3.10 required

This project uses **Python 3.10**. The repo is pinned via `.python-version` (for pyenv) and GitHub Actions use `3.10`.

Check your version:

```bash
python3 --version
# Should show: Python 3.10.x
```

## Install Python 3.10 (macOS with Homebrew)

### Option A: Homebrew Python

1. Install Python 3.10:

   ```bash
   brew install python@3.10
   ```

2. Use it for this project (pick one):

   **Prefer `python3` to be 3.10 everywhere (replace system/python.org):**

   ```bash
   brew link python@3.10 --force
   # Then reopen your terminal; python3 --version should be 3.10.x
   ```

   **Or use the full path for this repo only (no link):**

   ```bash
   # Add to PATH for this session, or add to your shell profile:
   export PATH="/opt/homebrew/opt/python@3.10/bin:$PATH"
   # Then:
   python3 --version  # should be 3.10.x
   ```

   On Intel Macs the path is often `/usr/local/opt/python@3.10/bin`.

### Option B: pyenv (recommended if you use multiple Python versions)

1. Install pyenv (if needed):

   ```bash
   brew install pyenv
   ```

2. Install Python 3.10 and use it in this repo:

   ```bash
   pyenv install 3.10
   cd /path/to/ai-newsy
   pyenv local 3.10
   ```

   The repo’s `.python-version` file will make `python` and `python3` resolve to 3.10 in this directory.

3. Ensure your shell runs pyenv (add to `~/.zshrc` or `~/.bash_profile` if not already there):

   ```bash
   eval "$(pyenv init -)"
   ```

## Create a virtual environment (recommended)

After Python 3.10 is active:

```bash
cd /path/to/ai-newsy
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Then run scripts with the venv active:

```bash
python execution/fetch_ai_news.py --limit 5
python execution/assign_topics.py
python execution/send_daily_email.py --test-email you@example.com
```

## Matching GitHub

- **CI**: `.github/workflows/daily_digest.yml` uses `actions/setup-python@v5` with `python-version: '3.10'`.
- **Local**: Use Python 3.10 (Homebrew or pyenv) and the same `requirements.txt` so behavior matches.

## Troubleshooting

- **`python3 --version` is still 3.9**  
  Use one of the PATH or pyenv steps above so `python3` points at 3.10.

- **`brew link python@3.10` fails**  
  Use the `export PATH=...` method or pyenv instead of linking.

- **OpenSSL / urllib3 warnings**  
  Python 3.10+ with Homebrew typically uses a newer OpenSSL; upgrading to 3.10 and using a venv usually clears those.

# 🚀 Deployment Guide — Railway

This guide deploys SMECreditAI to Railway with a PostgreSQL database, free SSL, and a public URL — all for free.

---

## Prerequisites

- GitHub account (code must be pushed)
- Railway account — sign up free at [railway.app](https://railway.app) using GitHub

---

## Step 1 — Prepare your code

Make sure these files exist in your repo root (already created):

```
✅ Procfile
✅ railway.toml
✅ requirements.txt   (includes gunicorn + psycopg2-binary)
✅ .gitignore         (instance/, venv/, *.pkl, *.csv excluded)
```

Push everything to GitHub:
```bash
git add .
git commit -m "Add Railway deployment config"
git push
```

---

## Step 2 — Create Railway project

1. Go to [railway.app](https://railway.app) → **New Project**
2. Click **"Deploy from GitHub repo"**
3. Select your `sme-credit-scoring` repository
4. Railway will auto-detect Python and start building

---

## Step 3 — Add PostgreSQL database

1. In your Railway project dashboard click **"+ New"**
2. Select **"Database" → "PostgreSQL"**
3. Railway automatically sets `DATABASE_URL` in your environment — your app reads this automatically

---

## Step 4 — Set environment variables

In Railway dashboard → your service → **"Variables"** tab, add:

| Variable | Value |
|---|---|
| `SECRET_KEY` | A long random string e.g. `openssl rand -hex 32` |
| `MAIL_USERNAME` | your@gmail.com (optional) |
| `MAIL_PASSWORD` | Gmail App Password (optional) |
| `MAIL_DEFAULT_SENDER` | your@gmail.com (optional) |

> `DATABASE_URL` is set automatically by Railway — do NOT add it manually.

---

## Step 5 — Train model and seed database

Railway runs your app but the ML model `.pkl` files are gitignored (too large).
You need to train and upload them.

### Option A — Train locally, commit temporarily (easiest)

```bash
# 1. Train locally
python ml/generate_dataset.py
python ml/train_model.py

# 2. Temporarily allow pkl files
echo "# Allow pkl for deploy" >> .gitignore
git add ml/saved_models/*.pkl
git commit -m "Add trained model for deploy"
git push

# 3. After Railway deploys successfully, remove from git tracking
git rm --cached ml/saved_models/*.pkl
echo "ml/saved_models/*.pkl" >> .gitignore
git commit -m "Re-gitignore pkl files"
git push
```

### Option B — Add a build command in Railway

In Railway → Service → Settings → **"Build Command"**:
```bash
python ml/generate_dataset.py && python ml/train_model.py && python reset_db.py
```

This trains the model fresh on every deploy (takes ~30 seconds).

---

## Step 6 — Database initialization

Add this to Railway → Service → Settings → **"Start Command"** (overrides Procfile):
```bash
python reset_db.py && gunicorn --chdir backend 'app:create_app()' --bind 0.0.0.0:$PORT --workers 2
```

Or run `reset_db.py` once manually via Railway's shell:
- Railway Dashboard → Service → **"Shell"** tab
- Run: `python reset_db.py`

---

## Step 7 — Get your live URL

1. Railway dashboard → your service → **"Settings"** tab
2. Under **"Networking"** → click **"Generate Domain"**
3. You'll get a URL like `https://sme-credit-scoring-production.up.railway.app`

Your app is now live! 🎉

---

## Redeploy after code changes

Railway auto-deploys every time you push to GitHub:
```bash
git add .
git commit -m "Your changes"
git push
# Railway picks this up automatically in ~60 seconds
```

---

## Troubleshooting

### Build fails — "No module named X"
Make sure all imports are in `requirements.txt` and push again.

### App crashes on start
Check Railway logs: Dashboard → Service → **"Deployments"** → click latest → **"View Logs"**

### Database errors after redeploy
Run `python reset_db.py` in the Railway shell to recreate tables.

### Port errors
Railway sets `$PORT` automatically — never hardcode port 5000 in production. The Procfile already handles this with `--bind 0.0.0.0:$PORT`.

---

## Cost

Railway free tier includes:
- **$5 free credit/month** — enough for a low-traffic app
- **PostgreSQL** — included
- **SSL certificate** — automatic
- **Custom domain** — supported

---

## Alternative free hosts

| Platform | Notes |
|---|---|
| **Render** | Similar to Railway, free tier has cold starts |
| **Fly.io** | Great for Flask, slightly more setup |
| **PythonAnywhere** | Simple but limited, good for demos |
| **Heroku** | No longer free but very reliable |
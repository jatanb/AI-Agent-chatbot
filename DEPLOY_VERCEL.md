# Deploy to Vercel - Complete Guide

## Quick Setup for Flask App

### Step 1: Prepare Your Project

Ensure you have these files in your project root:
- `flask_app.py` (main app)
- `vercel.json` (already created ✅)
- `requirements.txt` (list of dependencies)

### Step 2: Create requirements.txt

Run this command to generate dependencies:
```bash
pip freeze > requirements.txt
```

Or create manually with minimum needed:
```
flask>=2.3.0
gunicorn>=21.0.0
google-generativeai
tavily-python
```

### Step 3: Create Vercel Account

1. Go to https://vercel.com
2. Sign up with GitHub, GitLab, or email
3. Authorize Vercel to access your repositories

### Step 4: Deploy Using Git (Easiest)

#### Option A: Push to GitHub First
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/Goverment-RAG.git
git branch -M main
git push -u origin main
```

#### Option B: Deploy from Vercel Dashboard
1. Go to https://vercel.com/dashboard
2. Click "Add New..." → "Project"
3. Select "Import Git Repository"
4. Paste your GitHub repo URL
5. Click "Import"
6. Configure project settings:
   - **Framework**: Python
   - **Root Directory**: . (or ./src if nested)
7. Add Environment Variables (if needed):
   - `GEMINI_API_KEY=your_key`
   - `TAVILY_API_KEY=your_key`
8. Click "Deploy"

### Step 5: Deploy Using CLI (Alternative)

```bash
# Install Vercel CLI
npm install -g vercel

# Login to Vercel
vercel login

# Deploy
vercel --prod
```

The CLI will:
- Detect Python project
- Build using vercel.json config
- Deploy to production

### Step 6: Verify Deployment

1. After deployment, you'll get a URL like: `https://goverment-rag.vercel.app`
2. Visit the URL to test your app
3. Check logs in Vercel dashboard if issues

---

## For Streamlit App

**Note:** Vercel doesn't natively support Streamlit. Better alternatives:

### Option 1: Deploy Streamlit on Streamlit Cloud (Recommended)
```bash
# 1. Push code to GitHub
git push origin main

# 2. Go to https://share.streamlit.io
# 3. Click "New app"
# 4. Select your GitHub repo
# 5. Enter main file: app.py
# 6. Deploy!
```

### Option 2: Deploy on Heroku
```bash
# 1. Install Heroku CLI from heroku.com/cli
# 2. Create Procfile:
echo "web: streamlit run app.py" > Procfile

# 3. Deploy
heroku login
heroku create your-app-name
git push heroku main
```

### Option 3: Deploy on Railway
1. Go to https://railway.app
2. Connect GitHub
3. Select repository
4. Add start command: `streamlit run app.py`
5. Deploy!

---

## File Structure for Vercel

```
Goverment-RAG/
├── flask_app.py          ✅ Main Flask app
├── app.py                (Streamlit - deploy elsewhere)
├── vercel.json           ✅ Vercel config
├── requirements.txt      ✅ Dependencies
├── templates/            (Flask templates)
│   ├── base.html
│   ├── home.html
│   ├── features.html
│   ├── working.html
│   └── privacy.html
├── static/               (CSS, JS, images)
├── src/                  (Source code)
│   ├── components/
│   ├── features/
│   ├── database/
│   └── auth/
├── .env.local            (Local environment variables)
├── .env.production       (Production env vars)
└── .git/                 (GitHub repo)
```

---

## Environment Variables

### In Vercel Dashboard:
1. Go to Project Settings → Environment Variables
2. Add your API keys:
   ```
   GEMINI_API_KEY=sk_xxxxx
   TAVILY_API_KEY=tvly_xxxxx
   DATABASE_URL=your_db_url
   ```
3. Select which environments (Production, Preview, Development)
4. Redeploy after adding variables

### Local Testing:
Create `.env.local`:
```
GEMINI_API_KEY=your_key
TAVILY_API_KEY=your_key
```

---

## Troubleshooting

### Issue: "Build failed"
- **Solution:** Check `requirements.txt` has all dependencies
- Run: `pip freeze > requirements.txt`

### Issue: "Module not found"
- **Solution:** Ensure all imports are in `requirements.txt`
- Check if package names are correct (e.g., `google-generativeai` not `google`)

### Issue: "Timeout during deployment"
- **Solution:** 
  - Some large dependencies take time
  - Check Vercel logs for details
  - Try deploying again

### Issue: "Application error"
- **Solution:**
  - Check function logs in Vercel dashboard
  - Ensure `flask_app.py` has correct imports
  - Verify environment variables are set

### Issue: "Database connection failed"
- **Solution:**
  - Add DATABASE_URL to environment variables
  - Ensure database is accessible from Vercel IPs
  - Check credentials in .env

---

## Performance Tips

1. **Keep deployment small:**
   - Don't include node_modules, venv, __pycache__
   - Create `.gitignore`:
     ```
     venv/
     __pycache__/
     *.pyc
     .env
     .env.local
     ```

2. **Optimize requirements.txt:**
   - Remove unused packages
   - Keep versions pinned: `flask==2.3.5`

3. **Use caching:**
   - Vercel caches dependencies between builds
   - Faster subsequent deployments

4. **Monitor performance:**
   - Check "Analytics" in Vercel dashboard
   - View function duration and memory usage

---

## Quick Links

- Vercel Dashboard: https://vercel.com/dashboard
- Vercel Docs: https://vercel.com/docs
- Python on Vercel: https://vercel.com/docs/builders/overview#python
- Environment Variables: https://vercel.com/docs/concepts/projects/environment-variables

---

## One-Command Deploy

After setting up GitHub and vercel.json:

```bash
# Make changes locally
git add .
git commit -m "Your message"
git push origin main

# Vercel automatically deploys!
# Check https://vercel.com/dashboard for status
```

That's it! ✨ Your Flask app is live at your Vercel URL.

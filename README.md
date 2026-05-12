# NoteNest — Setup & Run Guide

## What is NoteNest?
A platform where contributors register, upload handwritten notes, and AI (Claude) verifies
accuracy before publishing. Notes scoring 70%+ go live automatically.

---

## Project Structure

```
notenest/
├── app.py                  ← Main Flask app (routes, models, AI logic)
├── requirements.txt        ← Python dependencies
├── static/
│   ├── css/style.css       ← All styling (dark modern theme)
│   ├── js/main.js          ← Frontend JS
│   └── uploads/            ← Uploaded note images (auto-created)
└── templates/
    ├── base.html           ← Nav, flash messages, footer
    ├── index.html          ← Explore/home page
    ├── register.html       ← Registration form
    ├── login.html          ← Login form
    ├── upload.html         ← Upload note form
    ├── upload_result.html  ← AI verification result
    ├── note_detail.html    ← Single note view
    └── dashboard.html      ← Contributor dashboard
```

---

## Step 1 — Install Python

Make sure Python 3.9+ is installed:
```bash
python --version
```

---

## Step 2 — Create a virtual environment

```bash
cd notenest
python -m venv venv

# Activate it:
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
```

---

## Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

---

## Step 4 — Set your Anthropic API key

NoteNest uses Claude (claude-sonnet-4-6) to verify notes.
Get your API key from: https://console.anthropic.com

Set it as an environment variable:

```bash
# On Windows (Command Prompt):
set ANTHROPIC_API_KEY=sk-ant-your-key-here

# On Mac/Linux:
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

---

## Step 5 — Run the app

```bash
python app.py
```

You will see:
```
* Running on http://127.0.0.1:5000
```

Open your browser and go to: http://127.0.0.1:5000

The SQLite database (notenest.db) and uploads/ folder are created automatically.

---

## How it works

1. **Register** — Create an account at /register
2. **Upload** — Go to "Upload Notes", fill in title, subject, description,
   paste the note content, and optionally attach a handwritten image
3. **AI Verifies** — Claude reads the content and scores it 0–100 for factual accuracy
4. **Published** — Score >= 70: note goes live. Score < 70: feedback shown, resubmit

---

## Pages

| URL              | Description                        |
|------------------|------------------------------------|
| /                | Browse all published notes         |
| /register        | Create a contributor account       |
| /login           | Sign in                            |
| /upload          | Upload a new note (login required) |
| /dashboard       | View your notes & stats            |
| /note/<id>       | Read a single note                 |
| /api/verify      | POST endpoint for AI verification  |

---

## Database

SQLite is used by default (notenest.db file created automatically).
To switch to PostgreSQL for production, change this line in app.py:

```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:pass@localhost/notenest'
```

And install psycopg2:
```bash
pip install psycopg2-binary
```

---

## Production tips

- Change `SECRET_KEY` in app.py to a long random string
- Set `debug=False` in app.run()
- Use gunicorn: `gunicorn -w 4 app:app`
- Store uploads on a cloud storage (AWS S3 / Cloudinary) instead of local disk
- Use environment variables for all secrets (never hardcode API keys)

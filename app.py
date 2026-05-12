from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import base64
import json
import re
import urllib.request
import urllib.error

app = Flask(__name__)
app.config['SECRET_KEY'] = 'notenest-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///notenest.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
db = SQLAlchemy(app)

class User(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    first_name  = db.Column(db.String(80), nullable=False)
    last_name   = db.Column(db.String(80), nullable=False)
    username    = db.Column(db.String(80), unique=True, nullable=False)
    email       = db.Column(db.String(120), unique=True, nullable=False)
    password    = db.Column(db.String(200), nullable=False)
    subject     = db.Column(db.String(100))
    joined_at   = db.Column(db.DateTime, default=datetime.utcnow)
    notes       = db.relationship('Note', backref='author', lazy=True)

class Note(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    title        = db.Column(db.String(200), nullable=False)
    topic        = db.Column(db.String(100), nullable=False)
    description  = db.Column(db.Text)
    content      = db.Column(db.Text)
    image_file   = db.Column(db.String(200))
    specific_topic = db.Column(db.String(200))
    ai_score     = db.Column(db.Integer)
    ai_verdict   = db.Column(db.String(100))
    ai_feedback  = db.Column(db.Text)
    is_published = db.Column(db.Boolean, default=False)
    views        = db.Column(db.Integer, default=0)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    user_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please sign in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def call_gemini(prompt, image_path=None):
    """Call Google Gemini API directly using urllib — no extra library needed."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise Exception("GEMINI_API_KEY not set. Please set it in the terminal.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    parts = []

    if image_path and os.path.exists(image_path):
        ext = image_path.rsplit('.', 1)[-1].lower()
        mime_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png'}
        with open(image_path, 'rb') as f:
            img_b64 = base64.b64encode(f.read()).decode('utf-8')
        parts.append({
            "inline_data": {
                "mime_type": mime_map.get(ext, 'image/jpeg'),
                "data": img_b64
            }
        })

    parts.append({"text": prompt})

    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2000
        }
    }).encode('utf-8')

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8')
        raise Exception(f"Gemini API error {e.code}: {err_body}")

    raw = result['candidates'][0]['content']['parts'][0]['text'].strip()
    raw = re.sub(r'^```json|^```|```$', '', raw, flags=re.MULTILINE).strip()
    return json.loads(raw)

def read_and_verify_note(image_path, title, topic, specific_topic=''):
    """Read handwriting from image and verify accuracy using Gemini."""
    prompt = f"""You are an expert academic assistant for NoteNest, a platform for handwritten educational notes.

You have been given an image of handwritten notes.

Title: {title}
Subject: {topic}
Specific Topic: {specific_topic}

Your tasks:
1. READ and EXTRACT all the handwritten text from the image as accurately as possible.
2. VERIFY the factual accuracy of the extracted content.
3. GENERATE a short description (1-2 sentences) summarizing what the notes cover.

Respond ONLY with a valid JSON object — no extra text, no markdown, no explanation:
{{
  "extracted_text": "<full text extracted from the handwritten image>",
  "description": "<1-2 sentence summary of what the notes cover>",
  "score": <integer 0-100 for factual accuracy>,
  "verdict": "<short phrase like Highly Accurate or Needs Revision>",
  "result_description": "<one sentence summary of the verification result>",
  "checks": [
    {{"status": "pass", "title": "<check title>", "detail": "<explanation>"}},
    {{"status": "pass", "title": "<check title>", "detail": "<explanation>"}},
    {{"status": "warn", "title": "<check title>", "detail": "<explanation>"}}
  ],
  "published": <true if score >= 70 else false>
}}

Rules:
- extracted_text: transcribe ALL visible handwritten text
- score: 0-100 based on factual accuracy
- checks: 3-4 items, status must be pass warn or fail
- published: true only if score >= 70
- If image is unclear, set score to 0 and explain in checks"""

    return call_gemini(prompt, image_path)

def verify_text_only(content, title, topic, specific_topic=''):
    """Verify plain text content using Gemini."""
    prompt = f"""You are an expert academic fact-checker for NoteNest.

Title: {title}
Subject: {topic}
Specific Topic: {specific_topic}
Content: {content}

Respond ONLY with valid JSON — no extra text, no markdown:
{{
  "extracted_text": "<the content as provided>",
  "description": "<1-2 sentence summary>",
  "score": <integer 0-100>,
  "verdict": "<short phrase>",
  "result_description": "<one sentence>",
  "checks": [
    {{"status": "pass", "title": "<title>", "detail": "<detail>"}},
    {{"status": "pass", "title": "<title>", "detail": "<detail>"}},
    {{"status": "warn", "title": "<title>", "detail": "<detail>"}}
  ],
  "published": <true if score >= 70 else false>
}}"""

    return call_gemini(prompt)

@app.route('/')
def index():
    q     = request.args.get('q', '').strip()
    topic = request.args.get('topic', 'all')
    query = Note.query.filter_by(is_published=True)
    if q:
        query = query.filter(Note.title.ilike(f'%{q}%') | Note.topic.ilike(f'%{q}%'))
    if topic and topic != 'all':
        query = query.filter(Note.topic.ilike(f'%{topic}%'))
    notes = query.order_by(Note.created_at.desc()).all()
    return render_template('index.html', notes=notes, q=q, topic=topic)

@app.route('/note/<int:note_id>')
def note_detail(note_id):
    note = Note.query.get_or_404(note_id)
    if not note.is_published:
        flash('This note is not yet published.', 'warning')
        return redirect(url_for('index'))
    note.views += 1
    db.session.commit()
    return render_template('note_detail.html', note=note)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name'].strip()
        last_name  = request.form['last_name'].strip()
        username   = request.form['username'].strip()
        email      = request.form['email'].strip().lower()
        password   = request.form['password']
        subject    = request.form.get('subject', '')
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return redirect(url_for('register'))
        user = User(first_name=first_name, last_name=last_name,
                    username=username, email=email,
                    password=generate_password_hash(password), subject=subject)
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        session['username'] = user.username
        flash(f'Welcome to NoteNest, {first_name}!', 'success')
        return redirect(url_for('upload'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        user     = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f'Welcome back, {user.first_name}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been signed out.', 'info')
    return redirect(url_for('index'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        title          = request.form['title'].strip()
        topic          = request.form['topic']
        specific_topic = request.form.get('specific_topic', '').strip()
        if not title or not topic or not specific_topic:
            flash('Please fill in all required fields.', 'danger')
            return redirect(url_for('upload'))

        file      = request.files.get('image')
        has_image = file and file.filename and allowed_file(file.filename)
        has_text  = request.form.get('content', '').strip()

        if not has_image and not has_text:
            flash('Please upload a handwritten note image.', 'danger')
            return redirect(url_for('upload'))

        image_filename = None
        image_path = None
        if has_image:
            image_filename = secure_filename(
                f"{session['user_id']}_{int(datetime.utcnow().timestamp())}_{file.filename}"
            )
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            file.save(image_path)

        try:
            if has_image:
                result = read_and_verify_note(image_path, title, topic, specific_topic)
            else:
                result = verify_text_only(has_text, title, topic, specific_topic)
        except Exception as e:
            flash(f'AI verification failed: {str(e)}', 'danger')
            return redirect(url_for('upload'))

        note = Note(
            title=title, topic=topic,
            specific_topic=specific_topic,
            description=result.get('description', f'{specific_topic} — Notes on {topic}'),
            content=result.get('extracted_text', has_text or ''),
            image_file=image_filename,
            ai_score=result.get('score', 0),
            ai_verdict=result.get('verdict', ''),
            ai_feedback=json.dumps(result),
            is_published=result.get('published', False),
            user_id=session['user_id']
        )
        db.session.add(note)
        db.session.commit()
        return render_template('upload_result.html', result=result, note=note)

    return render_template('upload.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user  = User.query.get(session['user_id'])
    notes = Note.query.filter_by(user_id=user.id).order_by(Note.created_at.desc()).all()
    total_views    = sum(n.views for n in notes)
    verified_count = sum(1 for n in notes if n.is_published)
    avg_score      = round(sum(n.ai_score for n in notes if n.ai_score) / len(notes), 1) if notes else 0
    return render_template('dashboard.html', user=user, notes=notes,
                           total_views=total_views, verified_count=verified_count,
                           avg_score=avg_score)

@app.route('/earnings')
@login_required
def earnings():
    return render_template('earnings.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)

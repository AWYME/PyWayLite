import sqlite3
import io
import sys
import contextlib
from datetime import datetime
from data import ACHIEVEMENTS
from flask import Flask, g, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

#TODO: change button at the end of lesson on lesson.html

app = Flask(__name__)
app.secret_key = 'supersecretkey'

DATABASE = 'database.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        with open('schema.sql', 'r', encoding='utf-8') as f:
            db.executescript(f.read())
        db.commit()

def check_and_award_achievements(user_id):
    db = get_db()
    total = db.execute('SELECT COUNT(*) FROM lessons').fetchone()[0]
    completed = db.execute('SELECT COUNT(*) FROM progress WHERE user_id = ? AND completed = 1', (user_id,)).fetchone()[0]

    earned = set(row['achievement_key'] for row in db.execute(
        'SELECT achievement_key FROM user_achievements WHERE user_id = ?', (user_id,)).fetchall())

    new_achievements = []
    for key, ach in ACHIEVEMENTS.items():
        if key not in earned and ach['condition'](completed, total):
            db.execute('''
                INSERT INTO user_achievements (user_id, achievement_key, earned_at)
                VALUES (?, ?, ?)
            ''', (user_id, key, datetime.now()))
            new_achievements.append(ach)

    if new_achievements:
        db.commit()
    return new_achievements

def run_code_with_input(code, input_data):
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(input_data)
    old_stdout = sys.stdout
    redirected_output = io.StringIO()
    sys.stdout = redirected_output

    try:
        exec(code, {'__name__': '__main__'}, {})
        output = redirected_output.getvalue()
    except Exception as e:
        output = f'Ошибка: {e}'
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout

    return output.strip()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    lessons = db.execute('SELECT * FROM lessons ORDER BY id').fetchall()
    progress = db.execute('SELECT lesson_id FROM progress WHERE user_id = ? AND completed = 1',
                          (session['user_id'],)).fetchall()
    completed_ids = {p['lesson_id'] for p in progress}
    return render_template('index.html', lessons=lessons, completed_ids=completed_ids)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        try:
            db.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                       (username, generate_password_hash(password)))
            db.commit()
            user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            session['user_id'] = user['id']
        except sqlite3.IntegrityError:
            return 'Имя уже занято'
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        return 'Неверные данные'
    return render_template('login.html')

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    user = db.execute('SELECT username FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    total = db.execute('SELECT COUNT(*) FROM lessons').fetchone()[0]
    completed = db.execute('SELECT COUNT(*) FROM progress WHERE user_id = ? AND completed = 1', (session['user_id'],)).fetchone()[0]

    earned = db.execute('''
        SELECT achievement_key, earned_at FROM user_achievements
        WHERE user_id = ?
        ORDER BY earned_at DESC
    ''', (session['user_id'],)).fetchall()

    achievements = []
    for e in earned:
        key = e['achievement_key']
        if key in ACHIEVEMENTS:
            ach = ACHIEVEMENTS[key].copy()
            ach['earned_at'] = e['earned_at']
            achievements.append(ach)

    return render_template('profile.html', user=user, total=total, completed=completed, achievements=achievements)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/lesson/<int:lesson_id>')
def lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    lesson = db.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    if lesson is None:
        return 'Урок не найден', 404
    completed = db.execute('SELECT * FROM progress WHERE user_id = ? AND lesson_id = ? AND completed = 1', (session['user_id'], lesson_id)).fetchone()
    return render_template('lesson.html', lesson=lesson, completed=completed)

@app.route('/check/<int:lesson_id>', methods=['POST'])
def check(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    code = request.form['code']
    db = get_db()
    tests = db.execute('SELECT input_data, expected_output FROM tests WHERE lesson_id = ?', (lesson_id,)).fetchall()

    if not tests:
        return 'Нет тестов для этого урока', 400

    all_passed = True
    results = []
    for test in tests:
        input_data = test['input_data'] or ''
        expected = test['expected_output'].strip()
        output = run_code_with_input(code, input_data)
        passed = (output == expected)
        results.append({
            'input': input_data,
            'expected': expected,
            'output': output,
            'passed': passed
        })
        if not passed:
            all_passed = False

    if all_passed:
        db.execute('INSERT OR IGNORE INTO progress (user_id, lesson_id, completed) VALUES (?, ?, 1)',(session['user_id'], lesson_id))
        db.commit()
        new_achievements = check_and_award_achievements(session['user_id'])
        return render_template('result.html', passed=True, results=results, lesson_id=lesson_id, new_achievements=new_achievements)
    else:
        return render_template('result.html', passed=False, results=results, lesson_id=lesson_id)

if __name__ == '__main__':
    app.run(debug=True)
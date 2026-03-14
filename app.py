from flask import Flask, request, render_template, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import base64
import random
import string
from datetime import datetime
import requests as req

app = Flask(__name__, static_folder='static')
app.secret_key = 'rxscan-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rxscan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'maddy39202@gmail.com'
app.config['MAIL_PASSWORD'] = 'lkls cjaz elrc qojt'


db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

GROQ_API_KEY = "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"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    prescriptions = db.relationship('Prescription', backref='user', lazy=True)

class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(200))
    member = db.Column(db.String(50), default='self')
    result = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def index():
    return render_template('index.html', username=current_user.username)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid email or password!')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error='Email already exists!')
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            user.password = generate_password_hash(new_password)
            db.session.commit()
            msg = Message('RxScan - Password Reset', sender='maddy39202@gmail.com', recipients=[email])
            msg.body = f'Your new password is: {new_password}\n\nPlease login and change your password immediately.'
            mail.send(msg)
            return render_template('forgot_password.html', success='New password sent to your email!')
        return render_template('forgot_password.html', error='Email not found!')
    return render_template('forgot_password.html')

@app.route('/history')
@login_required
def history():
    prescriptions = Prescription.query.filter_by(user_id=current_user.id).order_by(Prescription.date.desc()).all()
    return render_template('history.html', prescriptions=prescriptions)

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_prescription(id):
    prescription = Prescription.query.get_or_404(id)
    if prescription.user_id != current_user.id:
        return jsonify({'success': False})
    db.session.delete(prescription)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    Prescription.query.filter_by(user_id=current_user.id).delete()
    user = User.query.get(current_user.id)
    logout_user()
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('register'))

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form['current_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']
    if not check_password_hash(current_user.password, current_password):
        return render_template('settings.html', password_error='Current password is wrong!')
    if new_password != confirm_password:
        return render_template('settings.html', password_error='New passwords do not match!')
    current_user.password = generate_password_hash(new_password)
    db.session.commit()
    return render_template('settings.html', password_success=True)

@app.route('/analyze', methods=['POST'])
@login_required
def analyze():
    if 'prescription' not in request.files:
        return jsonify({'error': 'No file uploaded'})
    file = request.files['prescription']
    member = request.form.get('member', 'self')
    if file.filename == '':
        return jsonify({'error': 'No file selected'})
    file_data = file.read()
    base64_image = base64.b64encode(file_data).decode('utf-8')

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    },
                    {
                        "type": "text",
                        "text": """You must analyze this prescription image. STRICT RULES: NO asterisks (*), NO markdown, NO bullet points, NO dashes (-), NO bold formatting. Plain text only. Use EXACTLY this format:

PRESCRIPTION DETAILS
====================
Patient Name: 
Age: 
Date: 
Doctor Name: 
Hospital/Clinic: 

MEDICINES
====================
Medicine 1: [name] | Dosage: [dosage] | Frequency: [times per day] | Duration: [days]
Medicine 2: [name] | Dosage: [dosage] | Frequency: [times per day] | Duration: [days]

INSTRUCTIONS
====================
Instructions: 
Refills: 

If any detail is not visible, write Not mentioned. DO NOT use any special characters."""
                    }
                ]
            }
        ],
        "max_tokens": 1024
    }

    response = req.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
    data = response.json()
    if 'choices' in data:
        result = data['choices'][0]['message']['content']
    else:
        return jsonify({'error': 'Groq API error: ' + str(data.get('error', {}).get('message', 'Unknown error'))})

    prescription = Prescription(user_id=current_user.id, filename=file.filename, member=member, result=result)
    db.session.add(prescription)
    db.session.commit()
    return jsonify({'result': result})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
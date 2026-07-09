from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_dance.contrib.google import make_google_blueprint, google
import os
import json
import subprocess
import shutil
from werkzeug.utils import secure_filename
from datetime import datetime
import zipfile

app = Flask(__name__)
app.secret_key = 'MinaPy_Secret_Key_2026'

# إعدادات جوجل
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
google_bp = make_google_blueprint(
    client_id='YOUR_GOOGLE_CLIENT_ID',
    client_secret='YOUR_GOOGLE_CLIENT_SECRET',
    redirect_to='google_login'
)
app.register_blueprint(google_bp, url_prefix='/login')

# إعدادات التحميل
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'py', 'txt', 'json', 'zip', 'requirements.txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# الإدمن (البريد الإلكتروني)
ADMIN_EMAIL = 'vgty65v@gmail.com'

# إنشاء مجلد التحميلات
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    if 'email' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/google-login')
def google_login():
    if not google.authorized:
        return redirect(url_for('google.login'))
    
    resp = google.get('/oauth2/v2/userinfo')
    if resp.ok:
        user_info = resp.json()
        session['email'] = user_info['email']
        session['name'] = user_info['name']
        session['picture'] = user_info['picture']
        session['is_admin'] = (user_info['email'] == ADMIN_EMAIL)
        flash('تم تسجيل الدخول بنجاح!', 'success')
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('تم تسجيل الخروج', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        flash('الرجاء تسجيل الدخول أولاً', 'warning')
        return redirect(url_for('login'))
    
    user_dir = os.path.join(UPLOAD_FOLDER, session['email'].replace('@', '_').replace('.', '_'))
    files = []
    if os.path.exists(user_dir):
        for f in os.listdir(user_dir):
            file_path = os.path.join(user_dir, f)
            files.append({
                'name': f,
                'size': os.path.getsize(file_path),
                'date': datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M')
            })
    
    return render_template('dashboard.html', 
                         user=session, 
                         files=files,
                         is_admin=session.get('is_admin', False))

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'email' not in session:
        flash('الرجاء تسجيل الدخول أولاً', 'warning')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'files[]' not in request.files:
            flash('لم يتم اختيار ملفات', 'danger')
            return redirect(request.url)
        
        files = request.files.getlist('files[]')
        user_dir = os.path.join(UPLOAD_FOLDER, session['email'].replace('@', '_').replace('.', '_'))
        os.makedirs(user_dir, exist_ok=True)
        
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(user_dir, filename))
        
        flash(f'تم رفع {len(files)} ملف بنجاح!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('upload.html')

@app.route('/delete/<filename>')
def delete_file(filename):
    if 'email' not in session:
        flash('الرجاء تسجيل الدخول', 'warning')
        return redirect(url_for('login'))
    
    user_dir = os.path.join(UPLOAD_FOLDER, session['email'].replace('@', '_').replace('.', '_'))
    file_path = os.path.join(user_dir, filename)
    
    if os.path.exists(file_path):
        os.remove(file_path)
        flash(f'تم حذف الملف {filename}', 'info')
    else:
        flash('الملف غير موجود', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/run/<filename>')
def run_python_file(filename):
    if 'email' not in session:
        flash('الرجاء تسجيل الدخول', 'warning')
        return redirect(url_for('login'))
    
    user_dir = os.path.join(UPLOAD_FOLDER, session['email'].replace('@', '_').replace('.', '_'))
    file_path = os.path.join(user_dir, filename)
    
    if not os.path.exists(file_path):
        flash('الملف غير موجود', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        # تشغيل ملف البايثون
        result = subprocess.run(
            ['python', file_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout + result.stderr
        return render_template('output.html', 
                             filename=filename, 
                             output=output or 'لا يوجد مخرجات')
    except subprocess.TimeoutExpired:
        flash('انتهى وقت التشغيل (30 ثانية)', 'warning')
        return redirect(url_for('dashboard'))
    except Exception as e:
        flash(f'خطأ: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/admin')
def admin_panel():
    if 'email' not in session or session.get('email') != ADMIN_EMAIL:
        flash('غير مصرح بالدخول', 'danger')
        return redirect(url_for('dashboard'))
    
    users = []
    for user_dir in os.listdir(UPLOAD_FOLDER):
        user_path = os.path.join(UPLOAD_FOLDER, user_dir)
        if os.path.isdir(user_path):
            files = os.listdir(user_path)
            users.append({
                'name': user_dir.replace('_', '@').replace('_', '.'),
                'files': files,
                'count': len(files)
            })
    
    return render_template('admin.html', users=users)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
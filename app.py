from flask import Flask, request, jsonify, redirect, url_for, flash, render_template, session, make_response
from werkzeug.utils import secure_filename
from datetime import timedelta, datetime
from functools import wraps
import os
from PIL import Image
from flask_wtf.csrf import CSRFProtect

from dbhelper import *

app = Flask(__name__)
csrf = CSRFProtect(app)

app.config.update(
    SECRET_KEY='KAPOY NAKO',
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=1),
    WTF_CSRF_TIME_LIMIT=None,
    WTF_CSRF_SSL_STRICT=False
)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['SESSION_TYPE'] = 'filesystem'

from routes.auth_routes import auth_bp
from routes.student_routes import student_bp
from routes.admin_routes import admin_bp

# Add root route before blueprint registration
@app.route('/')
def index():
    return redirect(url_for('auth.login'))

# Update blueprint registrations
app.register_blueprint(auth_bp)  # No prefix for auth routes
app.register_blueprint(student_bp, url_prefix='/student')
app.register_blueprint(admin_bp)  # The url_prefix is already set in the Blueprint

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.after_request
def add_header(response):
    """
    Add headers to prevent browser caching for authenticated pages
    """
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
    return response

def resize_image(image_path, max_size=(300, 300)):
    with Image.open(image_path) as img:
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        aspect = img.width / img.height
        if img.width > max_size[0] or img.height > max_size[1]:
            if aspect > 1:
                new_width = min(img.width, max_size[0])
                new_height = int(new_width / aspect)
            else:
                new_height = min(img.height, max_size[1])
                new_width = int(new_height * aspect)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        img.save(image_path, 'JPEG', quality=95, optimize=True)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash("Please log in first!", "warning")
            session.clear()
            response = make_response(redirect(url_for('auth.login')))
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '-1'
            return response
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not all(session.get(key) for key in ['user_id', 'user_type', 'is_admin']):
            flash("Admin access required!", "danger")
            return redirect(url_for('auth.login'))
        session.modified = True
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or 'user_type' not in session or session.get('user_type') != 'student':
            flash("Student access required!", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

if __name__ == '__main__':
    app.run(debug=True)
    # app.run(debug=True, host='192.168.254.199', port=5000)

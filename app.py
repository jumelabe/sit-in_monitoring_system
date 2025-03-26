import sqlite3
import os
from flask import Flask, request, jsonify, redirect, url_for, flash, render_template, session, make_response, Response
from werkzeug.utils import secure_filename
from PIL import Image
from functools import wraps
from datetime import timedelta, datetime
import csv
import io
from openpyxl import Workbook
from io import BytesIO
import pandas as pd
from flask import send_file
import platform
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

app = Flask(__name__)
app.secret_key = 'kaon aron di ma brother'  # Secret key for session management

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Update Flask configuration
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)  # Increase session lifetime
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Allow non-HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_TYPE'] = 'filesystem'

# Ensure the upload directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_db_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

def resize_image(image_path, max_size=(300, 300)):
    with Image.open(image_path) as img:
        # Convert to RGB if image is in RGBA mode
        if img.mode == 'RGBA':
            img = img.convert('RGB')
            
        # Calculate aspect ratio
        aspect = img.width / img.height
        
        if img.width > max_size[0] or img.height > max_size[1]:
            if aspect > 1:
                # Width is greater than height
                new_width = min(img.width, max_size[0])
                new_height = int(new_width / aspect)
            else:
                # Height is greater than width
                new_height = min(img.height, max_size[1])
                new_width = int(new_height * aspect)
                
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
        # Save with high quality
        img.save(image_path, 'JPEG', quality=95, optimize=True)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash("Please log in first!", "warning")
            session.clear()  # Clear any invalid session data
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not all(session.get(key) for key in ['user_id', 'user_type', 'is_admin']):
            return redirect(url_for('login'))
        session.modified = True
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or 'user_type' not in session or session.get('user_type') != 'student':
            flash("Student access required!", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@app.before_request
def validate_session():
    if request.endpoint and 'static' in request.endpoint:
        return  # Skip session validation for static files
        
    if 'user_id' in session:
        session.permanent = True
        session.modified = True
        
        # Keep admin session alive
        if session.get('user_type') == 'admin':
            session['is_admin'] = True
            session['last_activity'] = datetime.now().isoformat()

@app.route('/')
def home():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    
    if session.get('user_type') == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('dashboard'))

@app.route('/edit_profile', methods=['POST'])
@login_required
def edit_profile():
    student_id = session['user_id']
    firstname = request.form.get('firstname')
    lastname = request.form.get('lastname')
    course = request.form.get('course')
    year_level = request.form.get('year_level')
    email_address = request.form.get('email_address')

    # Handle Profile Picture Upload
    profile_picture = request.files.get('profile_picture')
    profile_picture_url = None

    if profile_picture and profile_picture.filename != '':
        # Create a unique filename using timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"profile_{student_id}_{timestamp}_{secure_filename(profile_picture.filename)}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        try:
            # Save the original file with proper extension
            file_extension = os.path.splitext(profile_picture.filename)[1].lower()
            if file_extension not in ['.jpg', '.jpeg', '.png']:
                raise ValueError("Invalid file format. Only JPG and PNG are allowed.")
                
            profile_picture.save(file_path)
            # Resize the image with improved quality
            resize_image(file_path)
            # Set the relative path for database storage
            profile_picture_url = os.path.join('uploads', filename).replace('\\', '/')
        except Exception as e:
            flash(f"Error saving profile picture: {str(e)}", "danger")
            return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if profile_picture_url:
            # Get current profile picture
            cursor.execute("SELECT profile_picture FROM students WHERE idno = ?", (student_id,))
            old_picture = cursor.fetchone()['profile_picture']

            # Delete old profile picture if it exists
            if old_picture:
                old_picture_path = os.path.join('static', old_picture)
                if os.path.exists(old_picture_path):
                    os.remove(old_picture_path)

            cursor.execute("""
                UPDATE students 
                SET firstname = ?, lastname = ?, course = ?, year_level = ?, 
                    email_address = ?, profile_picture = ?
                WHERE idno = ?
            """, (firstname, lastname, course, year_level, email_address, profile_picture_url, student_id))
        else:
            cursor.execute("""
                UPDATE students 
                SET firstname = ?, lastname = ?, course = ?, year_level = ?, 
                    email_address = ?
                WHERE idno = ?
            """, (firstname, lastname, course, year_level, email_address, student_id))

        conn.commit()
        flash("Profile updated successfully!", "success")
    except sqlite3.Error as e:
        flash(f"Database error: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Clear any existing session
    if session.get('user_id'):
        session.clear()

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        password = request.form.get('password')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check admin first
            cursor.execute("SELECT * FROM admin WHERE username = ? AND password = ?", (user_id, password))
            admin = cursor.fetchone()

            if admin:
                session.permanent = True  # Enable session expiry
                session['user_id'] = str(admin["id"])
                session['user_type'] = 'admin'
                session['username'] = admin["username"]
                session['is_admin'] = True  # Add explicit admin flag
                session.modified = True  # Ensure session is saved
                flash("Admin login successful!", "success")
                return redirect(url_for('admin_dashboard'))

            # Then check students
            cursor.execute("SELECT * FROM students WHERE idno = ? AND password = ?", (user_id, password))
            student = cursor.fetchone()

            if student:
                session.permanent = True  # Enable session expiry
                session['user_id'] = str(student["idno"])
                session['user_type'] = 'student'
                session['firstname'] = student["firstname"]
                session['lastname'] = student["lastname"]
                session['session_count'] = student["session_count"]
                flash("Login successful!", "success")
                return redirect(url_for('dashboard'))

            flash("Invalid credentials!", "danger")
            return redirect(url_for('login'))

        except sqlite3.Error as e:
            flash(f"Database error: {str(e)}", "danger")
            return redirect(url_for('login'))
        finally:
            conn.close()

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        lastname = request.form.get('lastname')
        firstname = request.form.get('firstname')
        middlename = request.form.get('middlename', '')
        course = request.form.get('course')
        year_level = request.form.get('year_level')
        email = request.form.get('email')
        username = request.form.get('username')  
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if student ID or username already exists
        cursor.execute("SELECT * FROM students WHERE idno = ? OR username = ?", (student_id, username))
        existing_user = cursor.fetchone()

        if existing_user:
            flash("User already exists. Try a different ID or username.", "danger")
            conn.close()
            return redirect(url_for('register'))

        try:
            cursor.execute(
                'INSERT INTO students (idno, lastname, firstname, midname, course, year_level, email_address, username, password, session_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (student_id, lastname, firstname, middlename, course, year_level, email, username, password, 30)  # Initialize session_count to 30 hours
            )
            conn.commit()
            flash("Registration successful! You can now log in.", "success")
        except sqlite3.Error as e:
            flash(f"Database error: {str(e)}", "danger")
        finally:
            conn.close()

        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    if session.get('user_type') != 'student':
        session.clear()
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch user information
    cursor.execute("""
        SELECT idno, firstname, lastname, midname, course, year_level, email_address, profile_picture, session_count
        FROM students WHERE idno = ?
    """, (session['user_id'],))
    
    user = cursor.fetchone()

    # Fetch announcements
    cursor.execute("SELECT * FROM announcements ORDER BY created_at DESC")
    announcements = cursor.fetchall()
    conn.close()

    if not user:
        flash("User not found!", "danger")
        return redirect(url_for('logout'))

    # Update session data
    session['firstname'] = user['firstname']
    session['lastname'] = user['lastname']
    session['session_count'] = user['session_count']

    # Convert user data into a dictionary for Jinja template
    user_data = {
        "idno": user["idno"],
        "firstname": user["firstname"],
        "lastname": user["lastname"],
        "midname": user["midname"],
        "course": user["course"] or "N/A",  # Default if empty
        "year_level": user["year_level"] or "N/A",  # Default if empty
        "email_address": user["email_address"] or "N/A",  # Default if empty
        "profile_picture": user["profile_picture"] if user["profile_picture"] else None,  # None if not set
        "session_count": user["session_count"] if user["session_count"] else 0
    }

    return render_template('dashboard.html', user=user_data, announcements=announcements)

@app.route('/sit_in', methods=['POST'])
def sit_in():
    id_number = request.form.get('id_number')
    name = request.form.get('name')
    sit_purpose = request.form.get('sit_purpose')
    laboratory = request.form.get('laboratory')
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    current_date = datetime.now().strftime('%Y-%m-%d')

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check existing active session
            cursor.execute("""
                SELECT * FROM current_sit_in 
                WHERE id_number = ? AND status = 'Active'
            """, (id_number,))
            existing_sit_in = cursor.fetchone()

            if existing_sit_in:
                flash("Student is already logged in for a sit-in session.", "danger")
                return redirect(url_for('admin_dashboard'))

            # Check session count
            cursor.execute("SELECT session_count FROM students WHERE idno = ?", (id_number,))
            session_count = cursor.fetchone()["session_count"]
            
            if session_count <= 0:
                flash("Student has no remaining session time.", "danger")
                return redirect(url_for('admin_dashboard'))

            # Insert into current_sit_in
            cursor.execute("""
                INSERT INTO current_sit_in (id_number, name, purpose, sit_lab, session, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (id_number, name, sit_purpose, laboratory, session_count, 'Active'))

            # Insert initial record into sit_in_records without logout_time
            cursor.execute("""
                INSERT INTO sit_in_records (id_number, name, purpose, lab, login_time, date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (id_number, name, sit_purpose, laboratory, current_time, current_date))

            conn.commit()
            flash("Sit-in logged successfully!", "success")
            return redirect(url_for('admin_dashboard'))
        
    except sqlite3.Error as e:
        flash(f"Database error: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/update_logout', methods=['POST'])
def update_logout():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get current sit-in details before updating status
        cursor.execute("""
            SELECT name, purpose, sit_lab FROM current_sit_in 
            WHERE id_number = ? AND status = 'Active'
        """, (data['id_number'],))
        current_session = cursor.fetchone()

        if current_session:
            # Update status in current_sit_in
            cursor.execute("""
                UPDATE current_sit_in 
                SET status = 'Completed' 
                WHERE id_number = ? AND status = 'Active'
            """, (data['id_number'],))
            
            # Get the current time for logging
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            # Insert into sit_in_records
            cursor.execute("""
                INSERT INTO sit_in_records 
                (id_number, name, purpose, lab, login_time, logout_time, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                data['id_number'],
                current_session['name'],
                current_session['purpose'],
                current_session['sit_lab'],
                current_time,  # Using current time as login_time
                data['logout_time'],
                current_date
            ))
            
            # Update session count
            cursor.execute("SELECT session_count FROM students WHERE idno = ?", (data['id_number'],))
            session_count = cursor.fetchone()[0]
            new_session_count = max(session_count - 1, 0)  # Deduct 1 hour or prevent going below 0
            cursor.execute("UPDATE students SET session_count = ? WHERE idno = ?", (new_session_count, data['id_number']))
            
            conn.commit()
            return jsonify({"message": "Logout successful and record created"}), 200
        else:
            return jsonify({"message": "No active session found"}), 404
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@app.route('/sit_in_history')
@login_required
def sit_in_history():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch sit-in history for the current user
    cursor.execute("""
        SELECT date, sit_purpose, laboratory, login_time, logout_time
        FROM sit_in_history
        WHERE id_number = ?
        ORDER BY date DESC, login_time DESC
    """, (user_id,))
    
    history = cursor.fetchall()
    conn.close()
    
    return render_template('sit_in_history.html', history=history)

@app.route('/reserve', methods=["GET", "POST"])
@login_required
def reserve():
    user_id = session['user_id']  # Get the logged-in user ID

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Fetch student details including session_count
        cursor.execute("SELECT idno, firstname, lastname, session_count FROM students WHERE idno = ?", (user_id,))
        user = cursor.fetchone()

        if not user:
            flash("User not found!", "danger")
            return redirect(url_for('logout'))

        remaining_session = user["session_count"]  # Sync remaining session with database

        if request.method == 'POST':
            purpose = request.form['purpose']
            lab = request.form['lab']
            time_in = request.form['time_in']
            date = request.form['date']

            # Prevent reservations if session count is zero
            if remaining_session <= 0:
                flash("You have no remaining session hours.", "danger")
                return redirect(url_for('reserve'))

            try:
                # Insert reservation without deducting session count
                cursor.execute('INSERT INTO reservations (id_number, student_name, sit_purpose, laboratory, time_in, date, remaining_sessions) VALUES (?, ?, ?, ?, ?, ?, ?)',
                               (user["idno"], f"{user['firstname']} {user['lastname']}", purpose, lab, time_in, date, remaining_session))

                conn.commit()

                flash("Reservation created successfully!", "success")
            except sqlite3.Error as e:
                flash(f"Database error: {str(e)}", "danger")

            return redirect(url_for('reserve'))

    # Pass updated remaining session count to template
    return render_template('reservation.html', 
                           id_number=user["idno"],
                           student_name=f"{user['firstname']} {user['lastname']}",
                           remaining_session=session["session_count"])

@app.route('/admin_dashboard', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_dashboard():
    session.modified = True  # Ensure session is refreshed
    
    if not session.get('is_admin'):
        session['is_admin'] = True
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            cursor.execute(
                'INSERT INTO announcements (title, content, created_at) VALUES (?, ?, ?)',
                (title, content, created_at)
            )
            conn.commit()
            flash("Announcement created successfully!", "success")
        except sqlite3.Error as e:
            flash(f"Database error: {str(e)}", "danger")

    # Fetch statistics
    cursor.execute("SELECT COUNT(*) FROM students")
    student_registered = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM current_sit_in WHERE status = 'Active'")
    current_sit_in = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM current_sit_in")
    total_sit_in = cursor.fetchone()[0]

    # Fetch announcements
    cursor.execute("SELECT id, title, content, created_at FROM announcements ORDER BY created_at DESC")
    announcements = cursor.fetchall()
    
    conn.close()
    
    return render_template('admin/admin_dashboard.html', student_registered=student_registered, current_sit_in=current_sit_in, total_sit_in=total_sit_in, announcements=announcements)

@app.route('/student_list')
@admin_required
def student_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch students data
    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()
    
    conn.close()
    
    return render_template('admin/student_list.html', students=students)

@app.route('/get_student/<student_id>')
def get_student(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT idno, firstname, midname, lastname, session_count FROM students WHERE idno = ?", (student_id,))
    student = cursor.fetchone()
    conn.close()

    if student:
        student_data = {
            "success": True,
            "idno": student["idno"],
            "name": f"{student['firstname']} {student['midname']} {student['lastname']}",
            "session_count": student["session_count"]
        }
        return jsonify(student_data)
    else:
        return jsonify({"success": False})

@app.route('/current_sit_in')
@admin_required
def current_sit_in():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.idno, s.firstname, s.midname, s.lastname, s.course, s.year_level, 
               s.session_count, c.purpose, c.sit_lab, c.status
        FROM students s
        INNER JOIN current_sit_in c ON s.idno = c.id_number
        WHERE c.status = 'Active'
        ORDER BY c.sit_id_number DESC
    """)
    sit_ins = cursor.fetchall()
    conn.close()
    # Add debug print to check what's being returned
    print("Current sit-ins:", [dict(sit_in) for sit_in in sit_ins])
    return render_template('admin/current_sit_in.html', sit_ins=sit_ins)

@app.route('/end_session/<idno>', methods=['POST'])
@admin_required
def end_session(idno):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Check if the student has an active sit-in session
            cursor.execute("""
                SELECT id_number, name, purpose, sit_lab FROM current_sit_in 
                WHERE id_number = ? AND status = 'Active'
            """, (idno,))
            current_session = cursor.fetchone()

            if current_session:
                # Update status in current_sit_in
                cursor.execute("""
                    UPDATE current_sit_in 
                    SET status = 'Completed' 
                    WHERE id_number = ? AND status = 'Active'
                """, (idno,))

                # Update logout_time in sit_in_records
                cursor.execute("""
                    UPDATE sit_in_records 
                    SET logout_time = ?
                    WHERE id_number = ? AND logout_time IS NULL
                """, (current_time, idno))

                # Deduct session count
                cursor.execute("""
                    UPDATE students SET session_count = MAX(session_count - 1, 0) 
                    WHERE idno = ?
                """, (idno,))

                conn.commit()
                return jsonify({"message": "Session ended successfully"}), 200
            else:
                return jsonify({"message": "No active session found"}), 404

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"message": "An error occurred"}), 500

@app.route('/announcement/edit/<int:id>', methods=['POST'])
@admin_required
def edit_announcement(id):
    title = request.form.get('title')
    content = request.form.get('content')

    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                'UPDATE announcements SET title = ?, content = ? WHERE id = ?',
                (title, content, id)
            )
            conn.commit()
            flash("Announcement updated successfully!", "success")
        except sqlite3.Error as e:
            flash(f"Database error: {str(e)}", "danger")
        finally:
            cursor.close()

    return redirect(url_for('admin_dashboard'))

@app.route('/announcement/delete/<int:id>', methods=['POST'])
@admin_required
def delete_announcement(id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM announcements WHERE id = ?', (id,))
            conn.commit()
            flash("Announcement deleted successfully!", "success")
        except sqlite3.Error as e:
            flash(f"Database error: {str(e)}", "danger")
        finally:
            cursor.close()

    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/sit_in_purposes')
@admin_required
def sit_in_purposes():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sit_purpose, COUNT(*) as count
        FROM sit_in_history
        GROUP BY sit_purpose
    """)
    results = cursor.fetchall()
    conn.close()

    labels = [row['sit_purpose'] for row in results]
    counts = [row['count'] for row in results]

    return jsonify({"labels": labels, "counts": counts})

@app.route('/sit_in_records')
@admin_required
def sit_in_records():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Fetch all records with proper ordering
        cursor.execute("""
            SELECT id_number, name, purpose, lab, 
                   strftime('%Y-%m-%d %H:%M:%S', login_time) as login_time,
                   strftime('%Y-%m-%d %H:%M:%S', logout_time) as logout_time,
                   strftime('%Y-%m-%d', date) as date
            FROM sit_in_records
            ORDER BY date DESC, login_time DESC
        """)
        records = cursor.fetchall()
        conn.close()
        
        return render_template('admin/sit_in_records.html', records=records)
        
    except sqlite3.Error as e:
        flash(f"Database error: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/reports')
@admin_required
def reports():
    try:
        start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get basic statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT id_number) as unique_students,
                (
                    SELECT lab
                    FROM sit_in_records 
                    GROUP BY lab 
                    ORDER BY COUNT(*) DESC 
                    LIMIT 1
                ) as most_active_lab,
                ROUND(AVG(
                    CASE 
                        WHEN login_time IS NOT NULL AND logout_time IS NOT NULL
                        THEN (julianday(logout_time) - julianday(login_time)) * 24
                        ELSE NULL
                    END
                ), 1) as avg_duration
            FROM sit_in_records
            WHERE date BETWEEN ? AND ?
        """, (start_date, end_date))
        
        stats = cursor.fetchone()
        
        # Get reports data
        cursor.execute("""
            SELECT 
                id_number,
                name,
                purpose,
                lab,
                datetime(login_time) as login_time,
                datetime(logout_time) as logout_time,
                date,
                ROUND((julianday(logout_time) - julianday(login_time)) * 24, 1) as duration
            FROM sit_in_records
            WHERE date BETWEEN ? AND ?
            ORDER BY date DESC, login_time DESC
        """, (start_date, end_date))
        
        reports = cursor.fetchall()
        
        # Get unique labs and purposes for filters
        cursor.execute("SELECT DISTINCT lab FROM sit_in_records WHERE lab IS NOT NULL ORDER BY lab")
        labs = [row['lab'] for row in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT purpose FROM sit_in_records WHERE purpose IS NOT NULL ORDER BY purpose")
        purposes = [row['purpose'] for row in cursor.fetchall()]
        
        conn.close()

        if request.headers.get('Accept') == 'application/json':
            return jsonify({
                'reports': [dict(row) for row in reports],
                'stats': dict(stats)
            })

        formatted_stats = {
            'total_records': stats['total_records'],
            'unique_students': stats['unique_students'],
            'most_active_lab': stats['most_active_lab'] or 'N/A',
            'avg_duration': f"{stats['avg_duration']:.1f}h" if stats['avg_duration'] else '0.0h'
        }
        
        return render_template('admin/reports.html',
                             reports=reports,
                             start_date=start_date,
                             end_date=end_date,
                             labs=labs,
                             purposes=purposes,
                             **formatted_stats)
                             
    except Exception as e:
        print(f"Error in reports: {str(e)}")
        flash("Error loading reports", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/export_reports/<format>')
@admin_required
def export_reports(format):
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Improved query with better date handling and duration calculation
        query = """
            SELECT 
                id_number,
                name,
                purpose,
                lab,
                datetime(login_time) as login_time,
                datetime(logout_time) as logout_time,
                date,
                CASE 
                    WHEN login_time IS NOT NULL AND logout_time IS NOT NULL
                    THEN ROUND((julianday(logout_time) - julianday(login_time)) * 24, 1)
                    ELSE NULL
                END as duration
            FROM sit_in_records
            WHERE 1=1
        """
        params = []
        
        if start_date and end_date:
            query += " AND date BETWEEN ? AND ?"
            params.extend([start_date, end_date])
            
        query += " ORDER BY date DESC, login_time DESC"
        
        cursor.execute(query, params)
        reports = [dict(row) for row in cursor.fetchall()]
        conn.close()

        if not reports:
            flash("No data available for export", "warning")
            return redirect(url_for('reports'))

        try:
            if format == 'csv':
                return export_to_csv(reports)
            elif format == 'excel':
                return export_to_excel(reports, start_date, end_date)
            elif format == 'pdf':
                return export_to_pdf(reports, start_date, end_date)
            else:
                flash("Invalid export format", "error")
                return redirect(url_for('reports'))
        except Exception as e:
            flash(f"Export failed: {str(e)}", "error")
            return redirect(url_for('reports'))

    except Exception as e:
        flash(f"Export error: {str(e)}", "error")
        return redirect(url_for('reports'))

def export_to_csv(reports):
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['ID Number', 'Name', 'Purpose', 'Laboratory', 
                    'Login Time', 'Logout Time', 'Date', 'Duration (hours)'])
    
    # Write data
    for report in reports:
        writer.writerow([
            report['id_number'],
            report['name'],
            report['purpose'],
            report['lab'],
            report['login_time'],
            report['logout_time'],
            report['date'],
            f"{report['duration']:.1f}" if report['duration'] else ''
        ])
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=sit_in_reports_{datetime.now().strftime("%Y%m%d")}.csv'
    return response

def export_to_excel(reports, start_date=None, end_date=None):
    wb = Workbook()
    ws = wb.active
    ws.title = "Sit-in Reports"

    # Title and date range
    ws.merge_cells('A1:H1')
    ws['A1'] = "Sit-in Reports"
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center')

    if start_date and end_date:
        ws.merge_cells('A2:H2')
        ws['A2'] = f"Period: {start_date} to {end_date}"
        ws['A2'].alignment = Alignment(horizontal='center')
        current_row = 3
    else:
        current_row = 2

    # Headers with styling
    headers = ['ID Number', 'Name', 'Purpose', 'Laboratory', 
              'Login Time', 'Logout Time', 'Date', 'Duration (hours)']
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=current_row, column=col)
        cell.value = header
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        cell.border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

    # Data
    for row_idx, report in enumerate(reports, current_row + 1):
        for col, value in enumerate([
            report['id_number'],
            report['name'],
            report['purpose'],
            report['lab'],
            report['login_time'],
            report['logout_time'],
            report['date'],
            f"{report['duration']:.1f}" if report['duration'] else ''
        ], 1):
            cell = ws.cell(row=row_idx, column=col)
            cell.value = value
            cell.border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )

    # Auto-adjust column widths
    for col in ws.columns:
        max_length = 0
        column = [cell for cell in col]
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[get_column_letter(column[0].column)].width = adjusted_width

    # Save to BytesIO
    excel_file = BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)

    return send_file(
        excel_file,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'sit_in_reports_{datetime.now().strftime("%Y%m%d")}.xlsx'
    )

def export_to_pdf(reports, start_date=None, end_date=None):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=18
    )

    elements = []
    styles = getSampleStyleSheet()

    # Title
    elements.append(Paragraph("Sit-in Reports", styles['Title']))
    elements.append(Spacer(1, 12))

    # Date range and generation time
    if start_date and end_date:
        elements.append(Paragraph(f"Period: {start_date} to {end_date}", styles['Normal']))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Prepare table data
    table_data = [['ID Number', 'Name', 'Purpose', 'Laboratory', 
                   'Login Time', 'Logout Time', 'Date', 'Duration (hrs)']]
    
    for report in reports:
        table_data.append([
            str(report['id_number']),
            str(report['name']),
            str(report['purpose']),
            str(report['lab']),
            str(report['login_time'] or ''),
            str(report['logout_time'] or ''),
            str(report['date']),
            f"{report['duration']:.1f}" if report['duration'] else ''
        ])

    # Create and style the table
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('WORDWRAP', (0,0), (-1,-1), True),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'sit_in_reports_{datetime.now().strftime("%Y%m%d")}.pdf'
    )

@app.errorhandler(Exception)
def handle_error(error):
    print(f"Error occurred: {str(error)}")  # Add logging
    if 'user_id' in session:
        session.modified = True  # Try to preserve session
        return redirect(url_for('admin_dashboard' if session.get('is_admin') else 'dashboard'))
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
    #app.run(debug=True, host='172.19.131.164', port=5000)
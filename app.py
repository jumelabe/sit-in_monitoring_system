import sqlite3
import os
from flask import Flask, request, jsonify, redirect, url_for, flash, render_template, session, make_response
from werkzeug.utils import secure_filename
from PIL import Image
from functools import wraps
from datetime import timedelta, datetime

app = Flask(__name__)
app.secret_key = 'kaon aron di ma brother'  # Secret key for session management

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
        if 'user_id' not in session:
            flash("Please log in first!", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash("Admin access required!", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@app.route('/')
def home():
    return redirect(url_for('login'))

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
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check in students table
        cursor.execute("SELECT * FROM students WHERE idno = ?", (user_id,))
        user = cursor.fetchone()

        if user and user["password"] == password:  # Plain text password check
            session['user_id'] = str(user["idno"])  # Ensure session stores string
            session['role'] = 'student'  # Store user role in session
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))

        # Check in admin table if not found in students
        cursor.execute("SELECT * FROM admin WHERE username = ?", (user_id,))
        admin = cursor.fetchone()

        if admin and admin["password"] == password:  # Plain text password check
            session['user_id'] = str(admin["id"])  # Ensure session stores string
            session['role'] = 'admin'  # Store user role in session
            flash("Login successful!", "success")
            return redirect(url_for('admin_dashboard'))

        flash("Invalid credentials, please try again.", "danger")
        return redirect(url_for('login'))

    response = make_response(render_template('login.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

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

def insert_sit_in_record(id_number, name, sit_purpose, laboratory, login_time, date, action):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Insert into sit_in_history
            cursor.execute("""
                INSERT INTO sit_in_history (id_number, name, sit_purpose, laboratory, login_time, date, action)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (id_number, name, sit_purpose, laboratory, login_time, date, action))
            
            # Get the student's session count
            cursor.execute("SELECT session_count FROM students WHERE idno = ?", (id_number,))
            session_count = cursor.fetchone()["session_count"]
            
            # Insert into current_sit_in
            cursor.execute("""
                INSERT INTO current_sit_in (id_number, name, purpose, sit_lab, session, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (id_number, name, sit_purpose, laboratory, session_count, 'Active'))
            
            conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        raise

@app.route('/sit_in', methods=['POST'])
def sit_in():
    id_number = request.form.get('id_number')
    name = request.form.get('name')
    sit_purpose = request.form.get('sit_purpose')
    laboratory = request.form.get('laboratory')

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Check if the student is already in current_sit_in with Active status
            cursor.execute("""
                SELECT * FROM current_sit_in 
                WHERE id_number = ? AND status = 'Active'
            """, (id_number,))
            existing_sit_in = cursor.fetchone()

            if existing_sit_in:
                flash("Student is already logged in for a sit-in session.", "danger")
                return redirect(url_for('admin_dashboard'))

            # Check if student has remaining session time
            cursor.execute("SELECT session_count FROM students WHERE idno = ?", (id_number,))
            session_count = cursor.fetchone()["session_count"]
            
            if session_count <= 0:
                flash("Student has no remaining session time.", "danger")
                return redirect(url_for('admin_dashboard'))

            # Insert only into current_sit_in
            cursor.execute("""
                INSERT INTO current_sit_in (id_number, name, purpose, sit_lab, session, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (id_number, name, sit_purpose, laboratory, session_count, 'Active'))

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
    
    # Update status in current_sit_in
    cursor.execute("""
        UPDATE current_sit_in 
        SET status = 'Completed' 
        WHERE id_number = ? AND status = 'Active'
    """, (data['id_number'],))
    
    # Calculate the duration of the sit-in session
    cursor.execute("""
        SELECT login_time FROM sit_in_history WHERE id_number = ? AND logout_time IS NULL
    """, (data['id_number'],))
    login_time = cursor.fetchone()[0]
    login_time = datetime.strptime(login_time, '%Y-%m-%d %H:%M:%S')
    logout_time = datetime.strptime(data['logout_time'], '%Y-%m-%d %H:%M:%S')
    duration = logout_time - login_time
    minutes_used = duration.total_seconds() / 60
    
    # Update the logout time
    cursor.execute("""
        UPDATE sit_in_history SET logout_time = ? WHERE id_number = ? AND logout_time IS NULL
    """, (data['logout_time'], data['id_number']))
    
    # Update session count
    cursor.execute("SELECT session_count FROM students WHERE idno = ?", (data['id_number'],))
    session_count = cursor.fetchone()[0]
    new_session_count = max(session_count - minutes_used, 0)  # Ensure it does not go below 0
    cursor.execute("UPDATE students SET session_count = ? WHERE idno = ?", (new_session_count, data['id_number']))
    
    conn.commit()
    conn.close()
    return jsonify({"message": "Logout time updated successfully"})

@app.route('/get_sit_in_history', methods=['GET'])
def get_sit_in_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sit_in_history")
    records = cursor.fetchall()
    conn.close()
    return jsonify([dict(zip([column[0] for column in cursor.description], row)) for row in records])

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

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch students data
    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()
    
    # Fetch statistics
    cursor.execute("SELECT COUNT(*) FROM students")
    student_registered = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM current_sit_in WHERE status = 'Active'")
    current_sit_in = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM current_sit_in")
    total_sit_in = cursor.fetchone()[0]
    
    conn.close()
    
    return render_template('admin_dashboard.html', students=students, student_registered=student_registered, current_sit_in=current_sit_in, total_sit_in=total_sit_in)

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
    return render_template('current_sit_in.html', sit_ins=sit_ins)

@app.route('/end_session/<idno>', methods=['POST'])
@admin_required
def end_session(idno):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Check if the student has an active sit-in session
            cursor.execute("""
                SELECT id_number, name, purpose, sit_lab FROM current_sit_in 
                WHERE id_number = ? AND status = 'Active'
            """, (idno,))
            current_session = cursor.fetchone()

            if current_session:
                # Instead of deleting, update status to 'Completed'
                cursor.execute("""
                    UPDATE current_sit_in 
                    SET status = 'Completed'
                    WHERE id_number = ? AND status = 'Active'
                """, (idno,))

                # Get the current timestamp
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                current_date = datetime.now().strftime('%Y-%m-%d')

                # Record in sit_in_history
                cursor.execute("""
                INSERT INTO sit_in_history 
                (id_number, name, sit_purpose, laboratory, login_time, logout_time, date, action)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                idno,
                current_session['name'],
                current_session['purpose'],
                current_session['sit_lab'],
                current_time,  # Login time
                current_time,  # Logout time
                current_date,
                "Ended Session"
            ))

                # Deduct session count
                cursor.execute("""
                    UPDATE students SET session_count = MAX(session_count - 1, 0) WHERE idno = ?
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


@app.route('/announcement', methods=['GET', 'POST'])
@login_required
def announcement():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('message')  # Ensure consistency with DB column
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
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('announcement'))

    cursor.execute("SELECT id, title, content, created_at FROM announcements ORDER BY created_at DESC")
    announcements = cursor.fetchall()
    cursor.close()  # Fix: Close cursor before closing connection
    conn.close()

    return render_template('announcement.html', announcements=announcements)

@app.route('/announcement/edit/<int:id>', methods=['POST'])
@admin_required
def edit_announcement(id):
    title = request.form.get('title')
    content = request.form.get('message')  # Ensure consistency with DB column

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

    return redirect(url_for('announcement'))

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

    return redirect(url_for('announcement'))

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    response = redirect(url_for('login'))

    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    
    return response

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

if __name__ == '__main__':
    app.run(debug=True)



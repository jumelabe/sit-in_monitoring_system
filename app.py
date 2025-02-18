import sqlite3
import os
from flask import Flask, request, jsonify, redirect, url_for, flash, render_template, session
from werkzeug.utils import secure_filename
from PIL import Image

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

def resize_image(image_path, size=(150, 150)):
    with Image.open(image_path) as img:
        img = img.resize(size, Image.LANCZOS)
        img.save(image_path, quality=95)

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/edit_profile', methods=['POST'])
def edit_profile():
    if 'user_id' not in session:
        flash("Please log in first!", "warning")
        return redirect(url_for('login'))

    student_id = session['user_id']
    firstname = request.form.get('firstname')
    lastname = request.form.get('lastname')
    course = request.form.get('course')
    year_level = request.form.get('year_level')
    email_address = request.form.get('email_address')

    # Handle Profile Picture Upload
    profile_picture = request.files.get('profile_picture')
    profile_picture_url = None  # Default to None

    if profile_picture and profile_picture.filename != '':
        filename = secure_filename(profile_picture.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        profile_picture.save(file_path)
        resize_image(file_path)  # Resize the image
        profile_picture_url = f'static/uploads/{filename}'

    conn = get_db_connection()
    cursor = conn.cursor()

    # Update query (without profile picture)
    update_query = """
        UPDATE students 
        SET firstname = ?, lastname = ?, course = ?, year_level = ?, email_address = ?
        WHERE idno = ?
    """
    values = [firstname, lastname, course, year_level, email_address, student_id]

    # Update query (with profile picture)
    if profile_picture_url:
        update_query = """
            UPDATE students 
            SET firstname = ?, lastname = ?, course = ?, year_level = ?, email_address = ?, profile_picture = ?
            WHERE idno = ?
        """
        values = [firstname, lastname, course, year_level, email_address, profile_picture_url, student_id]

    try:
        cursor.execute(update_query, values)
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
        student_id = request.form.get('student_id')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students WHERE idno = ?", (student_id,))
        user = cursor.fetchone()
        conn.close()

        if user and user["password"] == password:  # Plain text password check
            session['user_id'] = str(user["idno"])  # Ensure session stores string
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials, please try again.", "danger")
            return redirect(url_for('login'))

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
                'INSERT INTO students (idno, lastname, firstname, midname, course, year_level, email_address, username, password) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (student_id, lastname, firstname, middlename, course, year_level, email, username, password)
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
def dashboard():
    if 'user_id' not in session:
        flash("Please log in first!", "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch user information
    cursor.execute("""
        SELECT idno, firstname, lastname, midname, course, year_level, email_address, profile_picture, session_count
        FROM students WHERE idno = ?
    """, (session['user_id'],))
    
    user = cursor.fetchone()
    conn.close()

    if not user:
        flash("User not found!", "danger")
        return redirect(url_for('logout'))

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

    return render_template('dashboard.html', user=user_data)

def migrate():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # Check if the table already exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sit_in_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT NOT NULL,
            name TEXT NOT NULL,
            sit_purpose TEXT NOT NULL,
            laboratory TEXT NOT NULL,
            login_time TEXT NOT NULL,
            logout_time TEXT,
            date TEXT NOT NULL,
            action TEXT NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()
    print("Migration completed: sit_in_history table created (if not exists).")

def insert_sit_in_record(id_number, name, sit_purpose, laboratory, login_time, date, action):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sit_in_history (id_number, name, sit_purpose, laboratory, login_time, date, action)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (id_number, name, sit_purpose, laboratory, login_time, date, action))
    conn.commit()
    conn.close()
    print("Sit-in record inserted successfully.")

@app.route('/log_sit_in', methods=['POST'])
def log_sit_in():
    data = request.json
    insert_sit_in_record(data['id_number'], data['name'], data['sit_purpose'], data['laboratory'], data['login_time'], data['date'], data['action'])
    return jsonify({"message": "Sit-in logged successfully"}), 201

@app.route('/update_logout', methods=['POST'])
def update_logout():
    data = request.json
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sit_in_history SET logout_time = ? WHERE id_number = ? AND logout_time IS NULL
    """, (data['logout_time'], data['id_number']))
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
def sit_in_history():
    return render_template('sit_in_history.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    migrate()  # Ensure the database is set up
    app.run(debug=True)



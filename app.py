import sqlite3
from flask import Flask, request, redirect, url_for, flash, render_template, session

app = Flask(__name__)
app.secret_key = 'kaon aron di ma brother'  # Secret key for session management

def get_db_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

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

        if user and user["password"] == password:  # Direct password check
            session['user_id'] = user["idno"]
            flash("Login successful!", "success")
            return redirect(url_for('index'))
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

@app.route('/')
@app.route('/index')
def index():
    if 'user_id' not in session:
        flash("Please log in first!", "warning")
        return redirect(url_for('login'))

    return render_template('dashboard.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

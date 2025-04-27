from flask import Blueprint, request, render_template, redirect, url_for, flash, session, make_response
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from email_validator import validate_email, EmailNotValidError
from dbhelper import get_user_by_credentials, create_student, check_student_id_exists
import re

auth_bp = Blueprint('auth', __name__)

class LoginForm(FlaskForm):
    pass

class RegisterForm(FlaskForm):
    student_id = StringField('Student ID', validators=[
        DataRequired(),
        Length(min=8, max=8, message="Student ID must be 8 digits")
    ])
    lastname = StringField('Last Name', validators=[DataRequired()])
    firstname = StringField('First Name', validators=[DataRequired()])
    middlename = StringField('Middle Name')
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Invalid email address')
    ])
    course = SelectField('Course', validators=[DataRequired()], choices=[
        ('BSIT', 'BS Information Technology'),
        ('BSCS', 'BS Computer Science'),
        ('BSCPE', 'BS Computer Engineering'),
        ('BSBA', 'BS Business Administration'),
        ('BSA', 'BS Accountancy'),
        ('BSHM', 'BS Hospitality Management'),
        ('BSN', 'BS Nursing'),
        ('BSC', 'BS Criminology')
    ])
    year_level = SelectField('Year Level', validators=[DataRequired()], choices=[
        ('1', '1st Year'),
        ('2', '2nd Year'),
        ('3', '3rd Year'),
        ('4', '4th Year')
    ])
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8),
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])

    def validate_student_id(self, field):
        if not field.data.isdigit():
            raise ValidationError('Student ID must contain only numbers')
        if check_student_id_exists(field.data):
            raise ValidationError('Student ID already registered')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        session.clear()
        
    form = LoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        user_id = request.form.get('user_id', '').strip()
        password = request.form.get('password', '').strip()
        
        if not user_id or not password:
            flash("Please enter both user ID and password", "danger")
            return redirect(url_for('auth.login'))

        result = get_user_by_credentials(user_id, password)
        if result:
            session.clear()
            session.permanent = True
            
            user_type = result['type']
            user = result['data']
            session['user_id'] = str(user["id"] if user_type == 'admin' else user["idno"])
            session['user_type'] = user_type

            if user_type == 'admin':
                session['username'] = user["username"]
                session['is_admin'] = True
                flash("Admin login successful!", "success")
                return redirect(url_for('admin.admin_dashboard'))
            else:
                session['firstname'] = user["firstname"]
                session['lastname'] = user["lastname"]
                session['session_count'] = user["session_count"]
                flash("Login successful!", "success")
                return redirect(url_for('student.dashboard'))

        flash("Invalid credentials!", "danger")
        return redirect(url_for('auth.login'))

    return render_template('login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if request.method == 'POST' and form.validate_on_submit():
        try:
            # Get the middlename value directly from request.form
            middlename = request.form.get('middlename', '')
            
            student_data = {
                'student_id': form.student_id.data,
                'lastname': form.lastname.data,
                'firstname': form.firstname.data,
                'middlename': middlename if middlename else '',  # Use the form value directly
                'email': form.email.data,
                'course': form.course.data,
                'year_level': int(form.year_level.data),
                'username': form.username.data,
                'password': form.password.data
            }
            
            if create_student(student_data):
                flash("Registration successful! You can now login.", "success")
                return redirect(url_for('auth.login'))
            else:
                flash("Registration failed. Please try again.", "danger")
        except Exception as e:
            flash(f"An error occurred during registration: {str(e)}", "danger")
            print(f"Debug - Exception:", str(e))  # Debug print
        
    return render_template('register.html', form=form)

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    response = make_response(redirect(url_for('auth.login')))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

from flask import Blueprint, request, render_template, redirect, url_for, flash, session, send_file
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from dbhelper import *
from dbhelper import insert_sit_in_history_from_record

student_bp = Blueprint('student', __name__, url_prefix='/student')
csrf = CSRFProtect()

RESOURCE_UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads', 'resources')

@student_bp.route('/dashboard')
def dashboard():
    if session.get('user_type') != 'student':
        session.clear()
        return redirect(url_for('auth.login'))

    student = get_student_by_id(session['user_id'])
    if not student:
        flash("User not found!", "danger")
        return redirect(url_for('auth.logout'))

    session['firstname'] = student['firstname']
    session['lastname'] = student['lastname']
    session['session_count'] = student['session_count']

    user_data = {
        "idno": student["idno"],
        "firstname": student["firstname"],
        "lastname": student["lastname"],
        "midname": student["midname"],
        "course": student["course"] or "N/A",
        "year_level": student["year_level"] or "N/A",
        "email_address": student["email_address"] or "N/A",
        "profile_picture": student["profile_picture"] or None,
        "session_count": student["session_count"] or 0
    }

    announcements = get_announcements()
    return render_template('dashboard.html', user=user_data, announcements=announcements)

@student_bp.route('/announcements')
def announcements():
    if session.get('user_type') != 'student':
        session.clear()
        return redirect(url_for('auth.login'))
    
    announcements = get_announcements()
    return render_template('announcement.html', announcements=announcements)

@student_bp.route('/edit_profile', methods=['POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    try:
        # Get form data
        form_data = {
            'firstname': request.form.get('firstname'),
            'lastname': request.form.get('lastname'),
            'midname': request.form.get('midname', ''),  # Get midname with empty string as default
            'course': request.form.get('course'),
            'year_level': request.form.get('year_level'),
            'email_address': request.form.get('email_address')
        }

        # Handle file upload if present
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"profile_{session['user_id']}_{timestamp}_{secure_filename(file.filename)}"
                file_path = os.path.join('static/uploads', filename)
                file.save(file_path)
                form_data['profile_picture_url'] = os.path.join('uploads', filename).replace('\\', '/')

        # Update profile
        if update_student_profile(session['user_id'], form_data):
            flash('Profile updated successfully!', 'success')
        else:
            flash('Failed to update profile.', 'danger')

    except Exception as e:
        print(f"Error in edit_profile: {e}")
        flash('An error occurred while updating profile.', 'danger')

    return redirect(url_for('student.dashboard'))

@student_bp.route('/sit-in-history')
def sit_in_history():
    if session.get('user_type') != 'student':
        session.clear()
        return redirect(url_for('auth.login'))
    
    student_id = session.get('user_id')
    history = get_sit_in_history_by_student(student_id)
    csrf_token = generate_csrf()
    
    # Add debug print to verify data
    print(f"Retrieved {len(history)} history records for student {student_id}")
    
    return render_template('sit_in_history.html', history=history, csrf_token=csrf_token)

@student_bp.route('/reserve', methods=['GET', 'POST'])
def reserve():
    if session.get('user_type') != 'student':
        session.clear()
        return redirect(url_for('auth.login'))
    
    student = get_student_by_id(session['user_id'])
    
    if request.method == 'POST':
        # Handle reservation submission
        reservation_data = {
            'id_number': request.form.get('id_number'),
            'purpose': request.form.get('purpose'),
            'lab': request.form.get('lab'),
            'time_in': request.form.get('time_in'),
            'date': request.form.get('date')
        }
        # TODO: Add database function to save reservation
        flash('Reservation submitted successfully!', 'success')
        return redirect(url_for('student.reserve'))
    
    # For GET request, display form
    return render_template('reservation.html',
                         id_number=student['idno'],
                         student_name=f"{student['firstname']} {student['lastname']}",
                         remaining_session=student['session_count'])

@student_bp.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    if session.get('user_type') != 'student':
        return redirect(url_for('auth.login'))
    
    # CSRF is automatically checked by Flask-WTF
    history_id = request.form.get('history_id')
    feedback = request.form.get('feedback')
    
    if not history_id or not feedback:
        flash('Invalid feedback submission', 'error')
        return redirect(url_for('student.sit_in_history'))
    
    user_id = session.get('user_id')
    success = insert_feedback(history_id, feedback, user_id)
    if success:
        flash('Feedback submitted successfully!', 'success')
    else:
        flash('Failed to submit feedback.', 'danger')
    return redirect(url_for('student.sit_in_history'))

@student_bp.route('/reset_all_sessions', methods=['POST'])
def reset_all_sessions():
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))
    
    try:
        # Only reset session counts for all students
        success = reset_all_active_sessions()
        if success:
            flash('All students\' session counts have been reset successfully!', 'success')
        else:
            flash('Failed to reset session counts.', 'danger')
        return redirect(url_for('admin.student_list'))
    except Exception as e:
        flash(f'Error resetting session counts: {str(e)}', 'danger')
        return redirect(url_for('admin.student_list'))

@student_bp.route('/reset_session/<idno>', methods=['POST'])
def reset_session(idno):
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))
    
    try:
        # Only reset session count for the student
        success = reset_student_session(idno)
        if success:
            flash('Session count reset successfully!', 'success')
        else:
            flash('Failed to reset session count.', 'danger')
        return redirect(url_for('admin.student_list'))
    except Exception as e:
        flash(f'Error resetting session count: {str(e)}', 'danger')
        return redirect(url_for('admin.student_list'))

@student_bp.route('/admin_end_session/<idno>', methods=['POST'])
def admin_end_session(idno):
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))
    try:
        # End the session in sit_in_records
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sit_in_records
            SET logout_time = datetime('now', 'localtime')
            WHERE id_number = ? AND logout_time IS NULL
        """, (idno,))
        conn.commit()
        conn.close()
        # Copy the ended session to sit_in_history
        insert_sit_in_history_from_record(idno)
        flash('Session ended and history updated.', 'success')
    except Exception as e:
        flash(f'Error ending session: {str(e)}', 'danger')
    return redirect(url_for('admin.student_list'))

@student_bp.route('/resources')
def resources():
    if session.get('user_type') != 'student':
        session.clear()
        return redirect(url_for('auth.login'))
    # List all files in the resources upload folder
    files = []
    if os.path.exists(RESOURCE_UPLOAD_FOLDER):
        files = os.listdir(RESOURCE_UPLOAD_FOLDER)
    return render_template('resources.html', files=files)

@student_bp.route('/resources/download/<filename>')
def download_resource(filename):
    if session.get('user_type') != 'student':
        session.clear()
        return redirect(url_for('auth.login'))
    return send_file(
        os.path.join(RESOURCE_UPLOAD_FOLDER, filename),
        as_attachment=True
    )

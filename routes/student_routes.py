from flask import Blueprint, request, render_template, redirect, url_for, flash, session, send_file, jsonify
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from dbhelper import *
from dbhelper import insert_sit_in_history_from_record, create_reservation, get_computers_by_lab

student_bp = Blueprint('student', __name__, url_prefix='/student')
csrf = CSRFProtect()

RESOURCE_UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads', 'resources')

@student_bp.route('/dashboard')
def dashboard():
    if session.get('user_type') != 'student':
        session.clear()
        return redirect(url_for('auth.login'))
    
    # Get profile details
    student = get_student_by_id(session['user_id'])
    
    # Get active sit-in session, if any
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sir.*, c.pc_number as computer_number
        FROM sit_in_records sir
        LEFT JOIN computers c ON sir.lab = c.lab_room AND sir.computer_number = c.pc_number
        WHERE sir.id_number = ? AND sir.logout_time IS NULL
        ORDER BY sir.login_time DESC
        LIMIT 1
    """, (session['user_id'],))
    sit_in = cursor.fetchone()
    
    # Get pending or approved reservations
    cursor.execute("""
        SELECT * FROM computer_reservation_requests
        WHERE student_id = ? AND status IN ('pending', 'approved')
        ORDER BY date, time_in
    """, (session['user_id'],))
    reservations = cursor.fetchall()
    
    conn.close()
    
    # Format sit-in data for display
    active_sit_in = None
    if sit_in:
        active_sit_in = {
            'purpose': sit_in['purpose'],
            'lab': sit_in['lab'],
            'login_time': sit_in['login_time'],
            'computer_number': sit_in['computer_number'] if 'computer_number' in sit_in.keys() else None
        }
    
    # Format reservations for display
    pending_reservations = []
    for res in reservations:
        reservation = {
            'id': res['id'],
            'lab_room': res['lab_room'],
            'purpose': res['purpose'],
            'date': res['date'],
            'time_in': res['time_in'],
            'status': res['status'],
            'computer_number': res['computer_number'],
            'notes': res['notes']
        }
        pending_reservations.append(reservation)
    
    # Get announcements
    announcements = get_announcements()
    
    return render_template('dashboard.html', 
                         student=student, 
                         active_sit_in=active_sit_in,
                         pending_reservations=pending_reservations,
                         announcements=announcements[0:3] if announcements else [])

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
        lab_value = request.form.get('laboratory')
        
        # Format the lab room properly for consistency
        if lab_value:
            # If lab value is just a number (e.g., "524"), format it as "Room 524"
            if lab_value.isdigit():
                lab_room = f"Room {lab_value}"
            else:
                lab_room = lab_value
        else:
            lab_room = None
        
        reservation_data = {
            'id_number': request.form.get('id_number'),
            'purpose': request.form.get('purpose'),
            'lab': lab_room,  # Use the properly formatted lab room
            'time_in': request.form.get('time_in'),
            'date': request.form.get('date'),
            'computer_id': request.form.get('selected_computer')  # Get selected computer ID
        }
        
        # Validate selected computer
        if not reservation_data['computer_id']:
            flash('Please select an available computer', 'danger')
            return render_template('reservation.html',
                                 id_number=student['idno'],
                                 student_name=f"{student['firstname']} {student['lastname']}",
                                 remaining_session=student['session_count'],
                                 csrf_token=generate_csrf())
        
        # Create the reservation in the database
        try:
            # Create reservation request
            create_reservation(reservation_data)
            
            flash('Reservation submitted successfully!', 'success')
            return redirect(url_for('student.reserve'))
        except Exception as e:
            flash(f'Error creating reservation: {str(e)}', 'danger')
            return redirect(url_for('student.reserve'))
    
    # For GET request, display form
    return render_template('reservation.html',
                         id_number=student['idno'],
                         student_name=f"{student['firstname']} {student['lastname']}",
                         remaining_session=student['session_count'],
                         csrf_token=generate_csrf())

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
    # Fetch only enabled resources from the database
    resources = get_all_resources(enabled_only=True)
    return render_template('resources.html', resources=resources)

@student_bp.route('/resources/download/<filename>')
def download_resource(filename):
    if session.get('user_type') != 'student':
        session.clear()
        return redirect(url_for('auth.login'))
    return send_file(
        os.path.join(RESOURCE_UPLOAD_FOLDER, filename),
        as_attachment=True
    )

@student_bp.route('/get-available-computers/<lab_room>')
def get_available_computers(lab_room):
    """API endpoint to get available computers for a specific lab room"""
    if session.get('user_type') != 'student':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Format the lab room value to match the format in the database
        if lab_room.isdigit():
            # The select has values like "524", but the database uses "Room 524"
            formatted_lab_room = f"Room {lab_room}"
        else:
            formatted_lab_room = lab_room
        
        # Get all computers for the lab
        computers = get_computers_by_lab(formatted_lab_room)
        
        # If no computers found, try to find the lab with a different format
        if not computers:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT lab_room FROM computers")
            available_labs = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            # Try to find a matching lab
            for available_lab in available_labs:
                if lab_room in available_lab or available_lab in lab_room:
                    # We found a match, try this lab room
                    computers = get_computers_by_lab(available_lab)
                    if computers:
                        break
        
        # Filter to only available computers
        available_computers = [computer for computer in computers if computer['status'] == 'available']
        
        return jsonify({
            'success': True,
            'computers': available_computers,
            'total': len(available_computers)
        })
    except Exception as e:
        print(f"Error getting available computers: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@student_bp.route('/lab-schedules')
def lab_schedules():
    if session.get('user_type') != 'student':
        session.clear()
        return redirect(url_for('auth.login'))
    
    # Get all lab rooms
    lab_rooms = get_lab_rooms()
    
    # Get computer availability for each lab
    labs_data = []
    for lab in lab_rooms:
        computers = get_computers_by_lab(lab)
        available_count = sum(1 for computer in computers if computer['status'] == 'available')
        total_count = len(computers)
        
        labs_data.append({
            'name': lab,
            'available': available_count,
            'total': total_count,
            'computers': computers
        })
    
    return render_template('lab_schedules.html', labs=labs_data)

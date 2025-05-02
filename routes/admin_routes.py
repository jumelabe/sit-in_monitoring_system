from flask import Blueprint, request, render_template, redirect, url_for, flash, session, jsonify, send_file, make_response
from flask_wtf.csrf import CSRFProtect
from dbhelper import *
from datetime import datetime
import csv
import pandas as pd
from io import BytesIO
import xlsxwriter
from xhtml2pdf import pisa
import os
from werkzeug.utils import secure_filename
import sqlite3

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads', 'resources')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'txt', 'zip', 'rar', 'jpg', 'png'}

# Ensure upload folder exists at runtime
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Change Blueprint registration to include url_prefix
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
csrf = CSRFProtect()

@admin_bp.route('/dashboard', methods=['GET', 'POST'])  # Change from /admin_dashboard to /dashboard
def admin_dashboard():
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))

    # Handle announcement creation
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        if title and content:
            success = insert_announcement(title, content)
            if success:
                flash("Announcement created successfully!", "success")
            else:
                flash("Failed to create announcement.", "danger")

    # Get dashboard data
    stats = {
        'student_registered': get_student_count(),
        'current_sit_in': get_current_sit_in_count(),
        'total_sit_in': get_total_sit_in_count()
    }
    
    announcements = get_announcements()
    return render_template('admin/admin_dashboard.html', 
                         announcements=announcements, 
                         **stats)

@admin_bp.route('/announcement/edit/<int:id>', methods=['POST'])
def edit_announcement(id):
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))

    title = request.form.get('title')
    content = request.form.get('content')
    
    if not title or not content:
        flash('Title and content are required.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE announcements 
            SET title = ?, content = ?
            WHERE id = ?
        """, (title, content, id))
        
        conn.commit()
        flash('Announcement updated successfully!', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Error updating announcement: {str(e)}', 'danger')
        
    finally:
        conn.close()
    
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/announcement/delete/<int:id>', methods=['POST'])
def delete_announcement_route(id):
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        if delete_announcement(id):
            flash('Announcement deleted successfully!', 'success')
        else:
            flash('Failed to delete announcement.', 'danger')
    except Exception as e:
        flash(f'Error deleting announcement: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/sit_in_purposes')
def sit_in_purposes():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT purpose, COUNT(*) as count
            FROM sit_in_records 
            WHERE purpose IS NOT NULL
            GROUP BY purpose
            ORDER BY count DESC
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return jsonify({
                'success': True,
                'labels': [],
                'counts': [],
                'message': 'No data available'
            })
        
        labels = [str(row[0]) for row in results]
        counts = [int(row[1]) for row in results]
        
        return jsonify({
            'success': True,
            'labels': labels,
            'counts': counts
        })
        
    except Exception as e:
        print(f"Error in sit_in_purposes route: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Database error'
        }), 500

@admin_bp.route('/student_list')
def student_list():
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))
    students = get_students()
    return render_template('admin/student_list.html', students=students)

@admin_bp.route('/current_sit_in')
def current_sit_in():
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))

    conn = get_connection()
    cursor = conn.cursor()
    
    # Updated query to get all current sit-in students with complete information
    cursor.execute("""
        SELECT 
            s.idno,
            s.firstname,
            s.midname,
            s.lastname,
            s.course,
            s.year_level,
            sir.purpose,
            sir.lab as sit_lab,
            s.session_count as session
        FROM sit_in_records sir
        JOIN students s ON sir.id_number = s.idno
        WHERE sir.logout_time IS NULL
        ORDER BY sir.login_time DESC
    """)
    
    sit_ins = [dict(zip([
        'idno', 'firstname', 'midname', 'lastname', 'course', 
        'year_level', 'purpose', 'sit_lab', 'session'
    ], row)) for row in cursor.fetchall()]
    
    conn.close()
    return render_template('admin/current_sit_in.html', sit_ins=sit_ins)

def get_purpose_stats():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT purpose, COUNT(*) as count 
        FROM sit_in_records 
        GROUP BY purpose
    """)
    stats = cursor.fetchall()
    conn.close()
    return stats

@admin_bp.route('/sit_in_records')
def sit_in_records():
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))
    records = get_sit_in_records()
    purpose_stats = get_purpose_stats()
    return render_template('admin/sit_in_records.html', 
                         records=records,
                         purpose_stats=purpose_stats)

@admin_bp.route('/reports')
def reports():
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))

    selected_lab = request.args.get('lab', '')
    selected_purpose = request.args.get('purpose', '')

    # Get unique labs and purposes for filters
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT lab FROM sit_in_records ORDER BY lab")
    labs = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("SELECT DISTINCT purpose FROM sit_in_records ORDER BY purpose")
    purposes = [row[0] for row in cursor.fetchall()]
    conn.close()

    # Get filtered reports data
    data = get_filtered_reports(selected_lab, selected_purpose)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'reports': data['reports'],
            'labs': labs,
            'purposes': purposes
        })

    return render_template('admin/reports.html',
                         reports=data['reports'],
                         labs=labs,
                         purposes=purposes,
                         selected_lab=selected_lab,
                         selected_purpose=selected_purpose)

@admin_bp.route('/feedback_reports')
def feedback_reports():
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))
    
    selected_lab = request.args.get('lab', '')
    feedbacks = get_feedbacks(selected_lab=selected_lab)
    
    # Add X-Requested-With header check for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'feedbacks': feedbacks
        })
    
    return render_template('admin/feedback_report.html', 
                         feedbacks=feedbacks,
                         laboratories=get_labs(),
                         selected_lab=selected_lab)

@admin_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    response = make_response(redirect(url_for('auth.login')))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@admin_bp.route('/reset_all_sessions', methods=['POST'])
def reset_all_sessions():
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))

    try:
        success = reset_all_active_sessions()
        if success:
            flash('All sessions have been reset successfully!', 'success')
        else:
            flash('Error resetting data: Could not reset all sessions.', 'danger')
    except Exception as e:
        flash(f'Error resetting data: {str(e)}', 'danger')

    return redirect(url_for('admin.student_list'))

@admin_bp.route('/end_session', methods=['POST'])
def end_session():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    id_number = data.get('id_number')
    
    if not id_number:
        return jsonify({'success': False, 'message': 'Student ID is required'}), 400
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        conn.execute("BEGIN TRANSACTION")
        
        # First check if there's an active session
        cursor.execute("""
            SELECT COUNT(*) 
            FROM sit_in_records 
            WHERE id_number = ? AND logout_time IS NULL
        """, (id_number,))
        
        if cursor.fetchone()[0] == 0:
            return jsonify({'success': False, 'message': 'No active session found'}), 400

        # End the session
        cursor.execute("""
            UPDATE sit_in_records 
            SET logout_time = datetime('now', 'localtime')
            WHERE id_number = ? AND logout_time IS NULL
        """, (id_number,))
        
        # Deduct 1 session count
        cursor.execute("""
            UPDATE students SET session_count = CASE
                WHEN session_count > 0 THEN session_count - 1
                ELSE 0
            END
            WHERE idno = ?
        """, (id_number,))

        conn.commit()

        # Insert into history
        success = insert_sit_in_history_from_record(id_number)
        if not success:
            return jsonify({'success': False, 'message': 'Failed to create history record'}), 500

        return jsonify({
            'success': True,
            'message': 'Session ended and history updated successfully'
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({
            'success': False,
            'message': f'Error ending session: {str(e)}'
        }), 500
        
    finally:
        conn.close()

@admin_bp.route('/reset_session/<idno>', methods=['POST'])
def reset_session(idno):
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))

    try:
        success = reset_student_session(idno)
        if success:
            flash('Student sessions have been reset successfully!', 'success')
        else:
            flash('Error resetting student data: Could not reset student.', 'danger')
    except Exception as e:
        flash(f'Error resetting student data: {str(e)}', 'danger')

    return redirect(url_for('admin.student_list'))

@admin_bp.route('/export-reports/<format>', methods=['GET'])
def export_reports(format):
    if session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized access'}), 401

    try:
        lab = request.args.get('lab', '')
        purpose = request.args.get('purpose', '')
        
        # Get filtered data
        result = get_filtered_reports(lab, purpose)
        if not result.get('reports'):
            return jsonify({'error': 'No data available to export'}), 404

        df = pd.DataFrame(result['reports'])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format.lower() == 'csv':
            output = BytesIO()
            df.to_csv(output, index=False, encoding='utf-8-sig')
            output.seek(0)
            
            return send_file(
                output,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'sit_in_reports_{timestamp}.csv'
            )

        elif format.lower() == 'excel':
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Reports')
                worksheet = writer.sheets['Reports']
                
                # Auto-adjust column widths
                for idx, col in enumerate(df.columns):
                    series = df[col]
                    max_len = max(
                        series.astype(str).map(len).max(),
                        len(str(col))
                    ) + 2
                    worksheet.set_column(idx, idx, max_len)
            
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'sit_in_reports_{timestamp}.xlsx'
            )

        elif format.lower() == 'pdf':
            html_string = render_template(
                'admin/pdf_template.html',
                reports=df.to_dict('records'),
                timestamp=timestamp
            )
            
            output = BytesIO()
            pisa.CreatePDF(
                html_string,
                dest=output,
                encoding='utf-8'
            )
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'sit_in_reports_{timestamp}.pdf'
            )

        return jsonify({'error': 'Invalid format specified'}), 400

    except Exception as e:
        print(f"Export error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/reward_student', methods=['POST'])
def reward_student():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    id_number = data.get('id_number')
    
    if not id_number:
        return jsonify({'success': False, 'message': 'Student ID is required'}), 400

    conn = get_connection()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN TRANSACTION")

        # End the session
        cursor.execute("""
            UPDATE sit_in_records 
            SET logout_time = datetime('now', 'localtime')
            WHERE id_number = ? AND logout_time IS NULL
        """, (id_number,))

        # Deduct 1 session count
        cursor.execute("""
            UPDATE students SET session_count = CASE
                WHEN session_count > 0 THEN session_count - 1
                ELSE 0
            END
            WHERE idno = ?
        """, (id_number,))

        # Add 1 to both reward_points and reward_redeemable
        cursor.execute("""
            UPDATE students 
            SET reward_points = COALESCE(reward_points, 0) + 1,
                reward_redeemable = COALESCE(reward_redeemable, 0) + 1
            WHERE idno = ?
        """, (id_number,))

        # Check if redeemable points reached 3
        cursor.execute("SELECT reward_redeemable FROM students WHERE idno = ?", (id_number,))
        redeemable = cursor.fetchone()
        if redeemable and redeemable[0] >= 3:
            # Reset redeemable and add 1 session
            cursor.execute("""
                UPDATE students 
                SET reward_redeemable = 0,
                    session_count = session_count + 1
                WHERE idno = ?
            """, (id_number,))

        conn.commit()

        # Insert into history
        success = insert_sit_in_history_from_record(id_number)
        if not success:
            return jsonify({'success': False, 'message': 'Failed to create history record'}), 500

        return jsonify({
            'success': True,
            'message': 'Student rewarded and session ended successfully'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
    finally:
        conn.close()

@admin_bp.route('/leaderboards')
def leaderboards():
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))

    # Use combined leaderboard (top 5 by sit-in count and reward points)
    leaderboard_data = get_combined_leaderboard_students(limit=5)

    return render_template(
        'admin/leaderboards.html',
        leaderboard_data=leaderboard_data
    )

@admin_bp.route('/resources', methods=['GET', 'POST'])
def admin_resources():
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))

    upload_error = None
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        url_link = request.form.get('resource_url', '').strip()
        file = request.files.get('resource_file')

        if not title:
            upload_error = 'Title is required.'
        elif not (file and file.filename) and not url_link:
            upload_error = 'Please provide a file or a URL.'
        elif (file and file.filename) and url_link:
            upload_error = 'Please provide only one: file or URL.'
        elif file and file.filename:
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                # Ensure unique filename
                counter = 1
                base, ext = os.path.splitext(filename)
                while os.path.exists(file_path):
                    filename = f"{base}_{counter}{ext}"
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    counter += 1
                file.save(file_path)
                insert_resource(title, description, filename, None)
                flash('Resource uploaded successfully!', 'success')
                return redirect(url_for('admin.admin_resources'))
            else:
                upload_error = 'Invalid file type.'
        elif url_link:
            insert_resource(title, description, None, url_link)
            flash('Resource link added successfully!', 'success')
            return redirect(url_for('admin.admin_resources'))

    resources = get_all_resources()
    return render_template(
        'admin/admin_resources.html',
        resources=resources,
        upload_error=upload_error
    )

@admin_bp.route('/resources/enable/<int:resource_id>', methods=['POST'])
def enable_resource(resource_id):
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    enabled = request.form.get('enabled', '1') == '1'
    set_resource_enabled(resource_id, enabled)
    return redirect(url_for('admin.admin_resources'))

@admin_bp.route('/resources/delete/<int:resource_id>', methods=['POST'])
def delete_resource_route(resource_id):
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    file_name = delete_resource(resource_id)
    # Optionally, remove file from disk if it exists
    if file_name:
        file_path = os.path.join(UPLOAD_FOLDER, file_name)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error deleting file: {e}")
    flash('Resource deleted successfully!', 'success')
    return redirect(url_for('admin.admin_resources'))

@admin_bp.route('/resources/download/<filename>')
def download_resource(filename):
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))
    return send_file(
        os.path.join(UPLOAD_FOLDER, filename),
        as_attachment=True
    )

# --- Student resources view ---
@admin_bp.route('/student/resources')
def student_resources():
    # No login required or check for student session if needed
    resources = get_all_resources()
    return render_template('student/resources.html', resources=resources)

@admin_bp.route('/delete_student/<idno>', methods=['POST'])
def delete_student(idno):
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Start transaction
        conn.execute("BEGIN TRANSACTION")
        
        # Delete from sit_in_records
        cursor.execute("DELETE FROM sit_in_records WHERE id_number = ?", (idno,))
        
        # Delete from students
        cursor.execute("DELETE FROM students WHERE idno = ?", (idno,))
        
        conn.commit()
        flash('Student deleted successfully!', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting student: {str(e)}', 'danger')
        
    finally:
        conn.close()
    
    return redirect(url_for('admin.student_list'))

@admin_bp.route('/get_student/<idno>')
def get_student_api(idno):
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    student = get_student_by_id(idno)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'})
    # Compose full name
    name = f"{student['firstname']} {student['midname']} {student['lastname']}".strip()
    return jsonify({
        'success': True,
        'idno': student['idno'],
        'name': name,
        'session_count': student['session_count']
    })

@admin_bp.route('/sit_in', methods=['POST'])
def sit_in_student():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    # Accept both JSON and form data
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    id_number = data.get('id_number')
    sit_purpose = data.get('sit_purpose')
    laboratory = data.get('laboratory')

    if not id_number or not sit_purpose or not laboratory:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    student = get_student_by_id(id_number)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    # Check if student has remaining sessions
    session_count = student['session_count']
    if session_count is not None and int(session_count) <= 0:
        return jsonify({'success': False, 'message': 'No remaining sessions for this student'}), 400

    # Check if student already has an active session
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM sit_in_records WHERE id_number = ? AND logout_time IS NULL",
        (id_number,)
    )
    if cursor.fetchone()[0] > 0:
        conn.close()
        return jsonify({'success': False, 'message': 'Student already has an active session'}), 400

    try:
        # Insert sit-in record (add date field)
        name = f"{student['firstname']} {student['midname']} {student['lastname']}".strip()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            INSERT INTO sit_in_records (id_number, name, purpose, lab, login_time, date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (id_number, name, sit_purpose, laboratory, now, today))
        # Do NOT deduct session count here!
        conn.commit()
        return jsonify({'success': True, 'message': 'Sit-in session started successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    finally:
        conn.close()

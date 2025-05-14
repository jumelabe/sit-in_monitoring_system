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
        
        # Find and update the computer status to available
        cursor.execute("""
            UPDATE computers 
            SET status = 'available', student_id = NULL 
            WHERE student_id = ?
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
        
        # Define file name with meaningful context
        file_prefix = 'sit_in_reports'
        if lab:
            file_prefix += f'_lab_{lab}'
        if purpose:
            file_prefix += f'_{purpose}'
        filename = f"{file_prefix}_{timestamp}"
        
        if format.lower() == 'csv':
            output = BytesIO()
            # Add UTF-8 BOM for Excel compatibility with special characters
            output.write(b'\xef\xbb\xbf')
            
            # Format columns for better readability
            for col in ['login_time', 'logout_time', 'date']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
            
            df.to_csv(output, index=False, encoding='utf-8')
            output.seek(0)
            
            return send_file(
                output,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'{filename}.csv'
            )

        elif format.lower() == 'excel':
            try:
                # Create a simple Excel file without fancy formatting
                output = BytesIO()
                
                # Use the simplest possible Excel export
                df.to_excel(output, index=False, sheet_name='Sit-In Reports')
                output.seek(0)
                
                return send_file(
                    output,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True,
                    download_name=f'{filename}.xlsx'
                )
            except Exception as e:
                print(f"Excel export error: {str(e)}")
                # Fall back to CSV if Excel fails
                output = BytesIO()
                output.write(b'\xef\xbb\xbf')  # UTF-8 BOM
                df.to_csv(output, index=False, encoding='utf-8')
                output.seek(0)
                
                return send_file(
                    output,
                    mimetype='text/csv',
                    as_attachment=True,
                    download_name=f'{filename}.csv'
                )

        elif format.lower() == 'pdf':
            # Try multiple possible paths for the logo files
            app_root = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(app_root)
            
            # Try different possible filenames and locations
            possible_uc_logos = [
                os.path.join(project_root, 'static', 'images', 'uc_logo.jpg'),
                os.path.join(project_root, 'static', 'images', 'uc.logo.jpg'),
                os.path.join(project_root, 'static', 'images', 'uc-logo.jpg')
            ]
            
            possible_css_logos = [
                os.path.join(project_root, 'static', 'images', 'css.png'),
                os.path.join(project_root, 'static', 'images', 'css_logo.png'),
                os.path.join(project_root, 'static', 'images', 'css-logo.png')
            ]
            
            # Find the first existing logo file
            uc_logo_path = None
            for path in possible_uc_logos:
                if os.path.exists(path):
                    uc_logo_path = path
                    break
                    
            css_logo_path = None
            for path in possible_css_logos:
                if os.path.exists(path):
                    css_logo_path = path
                    break
            
            # Debug information
            print(f"Project root: {project_root}")
            print(f"UC logo path: {uc_logo_path}")
            print(f"CSS logo path: {css_logo_path}")
            
            # Convert images to base64 for embedding in HTML
            import base64
            uc_logo_b64 = ""
            css_logo_b64 = ""
            
            # Try to read UC logo
            if uc_logo_path:
                try:
                    with open(uc_logo_path, "rb") as img_file:
                        uc_logo_b64 = base64.b64encode(img_file.read()).decode('utf-8')
                        print(f"Successfully encoded UC logo")
                except Exception as e:
                    print(f"Error encoding UC logo: {str(e)}")
            else:
                print("UC logo file not found")
                
            # Try to read CSS logo
            if css_logo_path:
                try:
                    with open(css_logo_path, "rb") as img_file:
                        css_logo_b64 = base64.b64encode(img_file.read()).decode('utf-8')
                        print(f"Successfully encoded CSS logo")
                except Exception as e:
                    print(f"Error encoding CSS logo: {str(e)}")
            else:
                print("CSS logo file not found")
            
            # Prepare data for PDF template
            html_context = {
                'reports': df.to_dict('records'),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'lab': lab,
                'purpose': purpose,
                'uc_logo_b64': uc_logo_b64,
                'css_logo_b64': css_logo_b64
            }
            
            # Render the template with complete context
            html_string = render_template(
                'admin/pdf_template.html',
                **html_context
            )
            
            # Create PDF
            output = BytesIO()
            
            # Create PDF with pisa
            pisa_status = pisa.CreatePDF(
                html_string,
                dest=output
            )
            
            if pisa_status.err:
                print(f"PDF generation error: {pisa_status.err}")
                return jsonify({'error': 'PDF generation failed'}), 500
                
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'{filename}.pdf'
            )

        return jsonify({'error': 'Invalid format specified'}), 400

    except Exception as e:
        import traceback
        traceback.print_exc()
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

        # Find and update the computer status to available
        cursor.execute("""
            UPDATE computers 
            SET status = 'available', student_id = NULL 
            WHERE student_id = ?
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

@admin_bp.route('/admin_resources', methods=['GET', 'POST'])
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
    
    # Get lab schedules for the schedule tab
    schedules = get_lab_schedules()
    
    # Get lab rooms for the lab selection dropdown
    lab_rooms = get_lab_rooms()
    
    return render_template(
        'admin/admin_resources.html',
        resources=resources,
        schedules=schedules,
        lab_rooms=lab_rooms,
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
    
    # Check if student has a pending reservation
    cursor.execute(
        "SELECT id, lab_room, purpose FROM computer_reservation_requests WHERE student_id = ? AND status = 'pending' ORDER BY date ASC, time_in ASC LIMIT 1",
        (id_number,)
    )
    pending_reservation = cursor.fetchone()
    
    if pending_reservation:
        # If there's a pending reservation, suggest using that instead
        reservation_id = pending_reservation['id']
        reservation_lab = pending_reservation['lab_room']
        reservation_purpose = pending_reservation['purpose']
        
        conn.close()
        return jsonify({
            'success': False, 
            'has_reservation': True,
            'message': f'Student has a pending reservation for {reservation_lab} with purpose: {reservation_purpose}. Please approve that reservation instead.',
            'reservation_id': reservation_id
        }), 400

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

@admin_bp.route('/computer_control')
def computer_control():
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))

    # Check if reset is requested
    if request.args.get('reset') == 'true':
        if reset_computers_table():
            flash("Computer tables have been reset and initialized with 50 computers per lab.", "success")
        else:
            flash("Failed to reset computer tables.", "danger")
        return redirect(url_for('admin.computer_control'))

    # Ensure computers table exists and has sample data
    ensure_computers_table()
    initialize_sample_computers()
    
    # Ensure reservation table exists
    ensure_reservation_table()

    selected_lab = request.args.get('lab')
    active_tab = request.args.get('tab', 'computers')

    # Fetch lab stats and lab rooms
    lab_stats = get_lab_computer_stats()
    lab_rooms = get_lab_rooms()

    # Fetch computers for selected lab
    computers = []
    if selected_lab:
        computers = get_computers_by_lab(selected_lab)

    # Fetch reservation requests
    requests = get_reservation_requests()
    
    # Get filters from request args
    filters = {
        'student_id': request.args.get('student_id', ''),
        'lab_room': request.args.get('lab_room', ''),
        'status': request.args.get('status', ''),
        'action': request.args.get('action', '')
    }
    
    # Fetch reservation logs with filters
    logs = get_reservation_logs(filters)
    print(f"DEBUG: Fetched {len(logs)} logs before filtering")
    
    # Filter logs to focus on approved and denied reservations if no specific filter is set
    # Commenting out this filtering to ensure all logs are shown
    """
    if not filters['action']:
        # Only show approved and denied logs by default
        logs = [log for log in logs if log['action'] in ['approved', 'denied']]
        print(f"DEBUG: After filtering for approved/denied actions: {len(logs)} logs")
    """
    
    # Print the first few logs for debugging
    if logs:
        print("DEBUG: First log details:")
        print(f"  ID: {logs[0]['id']}")
        print(f"  Action: {logs[0]['action']}")
        print(f"  Status: {logs[0]['status']}")
        print(f"  Student ID: {logs[0]['student_id']}")
    else:
        print("DEBUG: No logs found after filtering")
    
    # Fetch reservation logs with filters
    logs = get_reservation_logs(filters)
    
    # We're no longer filtering logs by action to show all logs
    # if not filters['action']:
    #     logs = [log for log in logs if log['action'] in ['approved', 'denied']]
    
    # Get unique student IDs, lab rooms, statuses, and actions for filter dropdowns
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT student_id FROM computer_reservation_requests ORDER BY student_id")
    student_ids = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("SELECT DISTINCT lab_room FROM computer_reservation_requests ORDER BY lab_room")
    log_lab_rooms = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("SELECT DISTINCT status FROM computer_reservation_requests ORDER BY status")
    statuses = [row[0] for row in cursor.fetchall()]
    
    # Add distinct actions from reservation_logs
    cursor.execute("SELECT DISTINCT action FROM reservation_logs ORDER BY action")
    actions = [row[0] for row in cursor.fetchall() if row[0]]
    
    # If no actions found in the logs, provide default actions
    if not actions:
        actions = ['approved', 'denied', 'created', 'cancelled']
    
    conn.close()

    return render_template(
        'admin/computer_control.html',
        lab_stats=lab_stats,
        lab_rooms=lab_rooms,
        selected_lab=selected_lab,
        computers=computers,
        requests=requests,
        logs=logs,
        student_ids=student_ids,
        log_lab_rooms=log_lab_rooms,
        statuses=statuses,
        actions=actions,
        filters=filters,
        active_tab=active_tab
    )

@admin_bp.route('/bulk_update_computer_status', methods=['POST'])
def bulk_update_computer_status():
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json
    if session.get('user_type') != 'admin':
        if is_ajax:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))
    
    # Check if it's an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    try:
        # Handle form data or JSON data
        if request.is_json:
            data = request.get_json()
            status = data.get('status')
            computer_ids = data.get('computer_ids', [])
            usage_type = data.get('usage_type')
            student_id = data.get('student_id')
        else:
            data = request.form
            status = data.get('status')
            computer_ids = data.getlist('computer_ids[]')
            usage_type = data.get('usage_type')
            student_id = data.get('student_id')
        
        if not status or not computer_ids:
            if is_ajax:
                return jsonify({'success': False, 'message': 'Missing parameters for bulk update'}), 400
            flash('Missing parameters for bulk update', 'danger')
            return redirect(url_for('admin.computer_control'))
        
        # Handle "in_use" status differently based on usage type
        if status == 'in_use':
            # Class use case - no student ID required
            if usage_type == 'class':
                conn = get_connection()
                cursor = conn.cursor()
                
                # Update each computer as in use without student_id
                success_count = 0
                for computer_id in computer_ids:
                    try:
                        cursor.execute(
                            "UPDATE computers SET status = ?, student_id = NULL WHERE id = ?",
                            ('in_use', computer_id)
                        )
                        success_count += 1
                    except Exception as e:
                        print(f"Error updating computer {computer_id}: {e}")
                
                conn.commit()
                conn.close()
                
                if is_ajax:
                    return jsonify({
                        'success': True, 
                        'message': f'{success_count} computers marked as in use for class'
                    })
                flash(f'{success_count} computers marked as in use for class', 'success')
                return redirect(url_for('admin.computer_control', lab=request.args.get('lab', '')))
                
            # Individual use requires student ID
            elif usage_type == 'individual' and student_id:
                # Verify student exists and has active sit-in
                student = get_student_by_id(student_id)
                if not student:
                    if is_ajax:
                        return jsonify({
                            'success': False, 
                            'message': 'Student not found. Please check the ID and try again.'
                        }), 404
                    flash('Student not found. Please check the ID and try again.', 'danger')
                    return redirect(url_for('admin.computer_control', lab=request.args.get('lab', '')))
                
                conn = get_connection()
                cursor = conn.cursor()
                
                # Check if student has active sit-in
                cursor.execute(
                    "SELECT COUNT(*) FROM sit_in_records WHERE id_number = ? AND logout_time IS NULL",
                    (student_id,)
                )
                
                if cursor.fetchone()[0] == 0:
                    conn.close()
                    if is_ajax:
                        return jsonify({
                            'success': False, 
                            'message': 'Student does not have an active sit-in session. They must start a sit-in session first.'
                        }), 400
                    flash('Student does not have an active sit-in session. They must start a sit-in session first.', 'danger')
                    return redirect(url_for('admin.computer_control', lab=request.args.get('lab', '')))
                
                # Update each computer
                success_count = 0
                for computer_id in computer_ids:
                    try:
                        cursor.execute(
                            "UPDATE computers SET status = ?, student_id = ? WHERE id = ?",
                            ('in_use', student_id, computer_id)
                        )
                        success_count += 1
                    except Exception as e:
                        print(f"Error updating computer {computer_id}: {e}")
                
                conn.commit()
                conn.close()
                
                if is_ajax:
                    return jsonify({
                        'success': True, 
                        'message': f'{success_count} computers assigned to student {student_id}'
                    })
                flash(f'{success_count} computers assigned to student {student_id}', 'success')
                return redirect(url_for('admin.computer_control', lab=request.args.get('lab', '')))
            else:
                # If neither class nor valid individual, show error
                if is_ajax:
                    return jsonify({
                        'success': False, 
                        'message': 'For individual use, a valid student ID is required'
                    }), 400
                flash('For individual use, a valid student ID is required', 'danger')
                return redirect(url_for('admin.computer_control', lab=request.args.get('lab', '')))
        
        # Handle 'available' status (we removed maintenance)
        conn = get_connection()
        cursor = conn.cursor()
        
        # Update each computer
        success_count = 0
        for computer_id in computer_ids:
            try:
                # For bulk operations, directly update the database
                cursor.execute(
                    "UPDATE computers SET status = ?, student_id = NULL WHERE id = ?",
                    ('available', computer_id)
                )
                success_count += 1
            except Exception as e:
                print(f"Error updating computer {computer_id}: {e}")
        
        conn.commit()
        conn.close()
        
        if is_ajax:
            return jsonify({
                'success': True, 
                'message': f'{success_count} of {len(computer_ids)} computers updated successfully!'
            })
        flash(f'{success_count} of {len(computer_ids)} computers updated successfully!', 'success')
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        if is_ajax:
            return jsonify({'success': False, 'message': f'Error in bulk update: {str(e)}'}), 500
        flash(f'Error in bulk update: {str(e)}', 'danger')
    finally:
        if 'conn' in locals():
            conn.close()
    
    return redirect(url_for('admin.computer_control', lab=request.args.get('lab', '')))

@admin_bp.route('/update_computer_status_route', methods=['POST'])
def update_computer_status_route():
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json
    if session.get('user_type') != 'admin':
        if is_ajax:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        return redirect(url_for('auth.login'))

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    computer_id = data.get('computer_id')
    status = data.get('status')
    student_id = data.get('student_id')

    if not computer_id or not status:
        if is_ajax:
            return jsonify({'success': False, 'message': 'Missing parameters'}), 400
        flash('Missing parameters', 'danger')
        return redirect(url_for('admin.computer_control', lab=request.args.get('lab', '')))

    if status not in ['available', 'in_use']:
        status = 'available'

    if status == 'in_use' and not student_id:
        if is_ajax:
            return jsonify({'success': False, 'message': 'Student ID is required when marking a computer as in use'}), 400
        flash('Student ID is required when marking a computer as in use', 'danger')
        return redirect(url_for('admin.computer_control', lab=request.args.get('lab', '')))

    if status == 'in_use' and student_id:
        student = get_student_by_id(student_id)
        if not student:
            if is_ajax:
                return jsonify({'success': False, 'message': 'Student not found. Please check the ID and try again.'}), 404
            flash('Student not found. Please check the ID and try again.', 'danger')
            return redirect(url_for('admin.computer_control', lab=request.args.get('lab', '')))
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM sit_in_records WHERE id_number = ? AND logout_time IS NULL",
                (student_id,)
            )
            if cursor.fetchone()[0] == 0:
                if is_ajax:
                    conn.close()
                    return jsonify({'success': False, 'message': 'Student does not have an active sit-in session. They must start a sit-in session first.'}), 400
                flash('Student does not have an active sit-in session. They must start a sit-in session first.', 'danger')
                conn.close()
                return redirect(url_for('admin.computer_control', lab=request.args.get('lab', '')))
            cursor.execute(
                "SELECT status, lab_room, pc_number, student_id FROM computers WHERE id = ?", 
                (computer_id,)
            )
            computer = cursor.fetchone()
            if not computer:
                if is_ajax:
                    conn.close()
                    return jsonify({'success': False, 'message': 'Computer not found. Please refresh and try again.'}), 404
                flash('Computer not found. Please refresh and try again.', 'danger')
                conn.close()
                return redirect(url_for('admin.computer_control', lab=request.args.get('lab', '')))
            comp_status = computer['status'] if hasattr(computer, '__getitem__') and 'status' in computer.keys() else computer[0]
            comp_student_id = computer['student_id'] if hasattr(computer, '__getitem__') and 'student_id' in computer.keys() else computer[3]
            if comp_status == 'in_use' and comp_student_id and comp_student_id != student_id:
                if is_ajax:
                    conn.close()
                    return jsonify({'success': False, 'message': 'This computer is already in use by another student. Please select another computer.'}), 400
                flash('This computer is already in use by another student. Please select another computer.', 'danger')
                conn.close()
                return redirect(url_for('admin.computer_control', lab=request.args.get('lab', '')))
            cursor.execute(
                "UPDATE computers SET status = ?, student_id = ? WHERE id = ?",
                (status, student_id, computer_id)
            )
            conn.commit()
            if is_ajax:
                conn.close()
                return jsonify({'success': True, 'message': 'Computer assigned to student successfully'})
            flash('Computer assigned to student successfully!', 'success')
        except Exception as e:
            print(f"DEBUG: Exception in update_computer_status_route: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            if is_ajax:
                return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
            flash(f'Error: {str(e)}', 'danger')
            return redirect(url_for('admin.computer_control', lab=request.args.get('lab', '')))
        finally:
            if 'conn' in locals():
                try:
                    conn.close()
                except:
                    pass
        if is_ajax:
            return jsonify({'success': True, 'message': 'Computer assigned to student successfully'})
        return redirect(url_for('admin.computer_control', lab=request.args.get('lab', '')))

    # Handle available status
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE computers SET status = ?, student_id = NULL WHERE id = ?",
            (status, computer_id)
        )
        conn.commit()
        if is_ajax:
            conn.close()
            return jsonify({'success': True, 'message': 'Computer status updated successfully'})
        flash('Computer status updated successfully!', 'success')
    except Exception as e:
        print(f"DEBUG: Exception in update_computer_status_route (available): {e}")
        if is_ajax:
            if 'conn' in locals():
                conn.close()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('admin.computer_control', lab=request.args.get('lab', '')))
    finally:
        if 'conn' in locals():
            try:
                conn.close()
            except:
                pass
    if is_ajax:
        return jsonify({'success': True, 'message': 'Computer status updated successfully'})
    return redirect(url_for('admin.computer_control', lab=request.args.get('lab', '')))

@admin_bp.route('/approve_reservation/<int:request_id>', methods=['POST'])
def approve_reservation(request_id):
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        print(f"DEBUG: Starting approval process for reservation {request_id}")
        
        # Get the reservation request
        cursor.execute("SELECT * FROM computer_reservation_requests WHERE id = ?", (request_id,))
        request_data = cursor.fetchone()
        if not request_data:
            flash("Reservation request not found.", "danger")
            return redirect(url_for('admin.computer_control', tab='requests'))
        
        print(f"DEBUG: Found reservation data: {dict(request_data)}")
        
        # Get student ID
        student_id = request_data['student_id']
        
        # Check if student already has an active sit-in session
        cursor.execute(
            "SELECT COUNT(*) FROM sit_in_records WHERE id_number = ? AND logout_time IS NULL",
            (student_id,)
        )
        if cursor.fetchone()[0] > 0:
            flash(f"Student {student_id} already has an active sit-in session. Cannot approve another reservation.", "danger")
            return redirect(url_for('admin.computer_control', tab='requests'))
        
        # Format the lab room to match the computers table format (e.g., "Room 524")
        # The computers table uses "Room 524" format while reservation might use just "524"
        lab_room_value = request_data['lab_room']
        if not lab_room_value.startswith("Room "):
            lab_room = f"Room {lab_room_value}"
        else:
            lab_room = lab_room_value
        
        computer_number = request_data['computer_number']
        
        print(f"DEBUG: Looking for computer in lab {lab_room}, number {computer_number}")
        
        # Check if the lab room exists in the computers table
        cursor.execute("SELECT COUNT(*) FROM computers WHERE lab_room = ?", (lab_room,))
        lab_exists = cursor.fetchone()[0]
        
        if lab_exists == 0:
            flash(f"Lab {lab_room} not found in the system.", "danger")
            return redirect(url_for('admin.computer_control', tab='requests'))
        
        # Find the computer in the lab
        if computer_number:
            cursor.execute(
                "SELECT id, status, student_id FROM computers WHERE lab_room = ? AND pc_number = ?",
                (lab_room, computer_number)
            )
            computer = cursor.fetchone()
            
            if not computer:
                flash(f"Computer #{computer_number} not found in {lab_room}.", "danger")
                return redirect(url_for('admin.computer_control', tab='requests'))
                
            if computer['status'] == 'in_use':
                flash(f"Computer #{computer_number} in {lab_room} is already in use.", "danger")
                return redirect(url_for('admin.computer_control', tab='requests'))
                
            computer_id = computer['id']
        else:
            # If no specific computer was requested, find an available one
            cursor.execute(
                "SELECT id, pc_number FROM computers WHERE lab_room = ? AND status = 'available' ORDER BY pc_number LIMIT 1",
                (lab_room,)
            )
            available_computer = cursor.fetchone()
            
            if not available_computer:
                flash(f"No computers available in {lab_room}.", "danger")
                return redirect(url_for('admin.computer_control', tab='requests'))
                
            computer_id = available_computer['id']
            computer_number = available_computer['pc_number']
        
        # Update the computer status to in_use
        cursor.execute(
            "UPDATE computers SET status = 'in_use', student_id = ? WHERE id = ?",
            (student_id, computer_id)
        )
        
        # Update the reservation status to approved
        cursor.execute(
            "UPDATE computer_reservation_requests SET status = 'approved', computer_number = ? WHERE id = ?",
            (computer_number, request_id)
        )
        
        # Create a sit-in record for the student
        student_name = request_data['student_name']
        purpose = request_data['purpose']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Extract just the room number for consistency with sit_in form
        lab_number = lab_room.replace("Room ", "") if lab_room.startswith("Room ") else lab_room
        
        cursor.execute("""
            INSERT INTO sit_in_records (id_number, name, purpose, lab, login_time, date, computer_number)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (student_id, student_name, purpose, lab_number, now, today, computer_number))
        
        # Log the reservation approval
        try:
            log_reservation_action(
                request_id, 
                'approved', 
                f"Reservation approved for computer #{computer_number} in {lab_room}"
            )
        except Exception as log_error:
            print(f"Warning: Failed to log approval action: {str(log_error)}")
            # Continue with approval even if logging fails
            
        # Direct insert into reservation_logs like in deny_reservation function
        cursor.execute(
            "INSERT INTO reservation_logs (request_id, student_id, lab_room, computer_number, action, status, reservation_time, purpose) "
            "SELECT id, student_id, lab_room, computer_number, 'approved', 'approved', date || ' ' || time_in, purpose "
            "FROM computer_reservation_requests WHERE id = ?",
            (request_id,)
        )
            
        conn.commit()
        flash(f"Reservation for {student_name} approved successfully. Assigned to computer #{computer_number} in {lab_room}.", "success")
    except Exception as e:
        conn.rollback()
        print(f"DEBUG: Error in approve_reservation: {str(e)}")
        flash(f"Error approving reservation: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.computer_control', tab='requests'))

@admin_bp.route('/deny_reservation/<int:request_id>', methods=['POST'])
def deny_reservation(request_id):
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Update the reservation status to denied
        cursor.execute(
            "UPDATE computer_reservation_requests SET status = 'denied' WHERE id = ?",
            (request_id,)
        )
        # Optionally, log the denial in reservation_logs
        cursor.execute(
            "INSERT INTO reservation_logs (request_id, student_id, lab_room, computer_number, action, status, reservation_time, purpose) "
            "SELECT id, student_id, lab_room, computer_number, 'denied', 'denied', date || ' ' || time_in, purpose "
            "FROM computer_reservation_requests WHERE id = ?",
            (request_id,)
        )
        conn.commit()
        flash("Reservation request denied.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error denying reservation: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.computer_control', tab='requests'))

@admin_bp.route('/save_lab_schedule', methods=['POST'])
def save_lab_schedule():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        day = request.json.get('day')
        time_slot = request.json.get('timeSlot')
        lab = request.json.get('lab')
        
        if not all([day, time_slot, lab]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
            
        # Check if the time slot is in the expected format: "HH:MM AM/PM - HH:MM AM/PM"
        if not isinstance(time_slot, str) or ' - ' not in time_slot:
            return jsonify({'success': False, 'message': 'Invalid time slot format'}), 400
            
        # Save to database
        save_schedule(day, time_slot, lab)
        
        return jsonify({
            'success': True,
            'message': f'Schedule added for {lab} on {day} at {time_slot}'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/delete_lab_schedule', methods=['POST'])
def delete_lab_schedule():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        day = request.json.get('day')
        time_slot = request.json.get('timeSlot')
        
        if not all([day, time_slot]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
            
        # Delete from database
        delete_schedule(day, time_slot)
        
        return jsonify({
            'success': True,
            'message': f'Schedule removed for {day} at {time_slot}'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/toggle_schedule_availability', methods=['POST'])
def toggle_schedule_availability():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        day = request.json.get('day')
        time_slot = request.json.get('timeSlot')
        is_available = request.json.get('isAvailable')
        
        if not all([day, time_slot]) or is_available is None:
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
            
        # Update availability in database
        update_schedule_availability(day, time_slot, is_available)
        
        status = "available" if is_available else "occupied"
        return jsonify({
            'success': True,
            'message': f'Schedule for {day} at {time_slot} marked as {status}'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

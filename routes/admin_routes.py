from flask import Blueprint, request, render_template, redirect, url_for, flash, session, jsonify, send_file, make_response
from flask_wtf.csrf import CSRFProtect
from dbhelper import *
from datetime import datetime
import csv
import pandas as pd
from io import BytesIO
import xlsxwriter
from xhtml2pdf import pisa

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
        print(f"Error in end_session: {e}")  # Debug print
        return jsonify({
            'success': False,
            'message': f'Error ending session: {str(e)}'
        }), 500
        
    finally:
        conn.close()

@admin_bp.route('/get_student/<idno>')  # Changed from /admin/get_student/<idno>
def get_student(idno):
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:    
        student = get_student_by_id(idno)
        if student:
            return jsonify({
                'success': True,
                'idno': student['idno'],
                'name': f"{student['firstname']} {student['lastname']}",
                'session_count': student['session_count']
            })
        return jsonify({'success': False, 'message': 'Student not found'}), 404
    except Exception as e:
        print(f"Error in get_student route: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/sit_in', methods=['POST'])
def sit_in():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Invalid request format'}), 400
        
    data = request.json
    idno = data.get('id_number')
    purpose = data.get('sit_purpose')
    laboratory = data.get('laboratory')
    
    if not all([idno, purpose, laboratory]):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if student already has an active session
        cursor.execute("""
            SELECT id_number 
            FROM sit_in_records 
            WHERE id_number = ? AND logout_time IS NULL
        """, (idno,))
        active_session = cursor.fetchone()
        
        if active_session:
            return jsonify({'success': False, 'message': 'Student already has an active session'}), 400

        # Check if student has any remaining sessions
        cursor.execute("SELECT session_count FROM students WHERE idno = ?", (idno,))
        result = cursor.fetchone()
        if not result or result[0] <= 0:
            return jsonify({'success': False, 'message': 'No remaining sessions available'}), 400
            
        # Get student name
        cursor.execute("SELECT firstname, lastname FROM students WHERE idno = ?", (idno,))
        student = cursor.fetchone()
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
            
        student_name = f"{student[0]} {student[1]}"
        
        # Create new sit-in record without incrementing session count
        cursor.execute("""
            INSERT INTO sit_in_records (id_number, name, purpose, lab, login_time, date)
            VALUES (?, ?, ?, ?, datetime('now', 'localtime'), date('now'))
        """, (idno, student_name, purpose, laboratory))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Sit-in session started successfully'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
        
    finally:
        conn.close()

@admin_bp.route('/reset_session/<idno>', methods=['POST'])
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
    
    success = add_reward_point(id_number)
    if success:
        return jsonify({
            'success': True,
            'message': 'Student rewarded and session ended successfully'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Failed to add reward point'
        }), 500

@admin_bp.route('/leaderboards')
def leaderboards():
    if session.get('user_type') != 'admin':
        flash("Admin access required.", "danger")
        return redirect(url_for('auth.login'))

    # Use combined leaderboard (top 5 by sit-in count and reward points)
    leaderboard_data = get_combined_leaderboard_students(limit=5)
    print("DEBUG: leaderboard_data length =", len(leaderboard_data))
    print("DEBUG: leaderboard_data =", leaderboard_data)

    return render_template(
        'admin/leaderboards.html',
        leaderboard_data=leaderboard_data
    )

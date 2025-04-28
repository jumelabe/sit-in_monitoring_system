import sqlite3
from datetime import datetime

DB_NAME = 'users.db'

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_user_by_credentials(user_id, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admin WHERE username = ? AND password = ?", (user_id, password))
    admin = cursor.fetchone()
    if admin:
        conn.close()
        return {'type': 'admin', 'data': admin}
    cursor.execute("SELECT * FROM students WHERE idno = ? AND password = ?", (user_id, password))
    student = cursor.fetchone()
    conn.close()
    if student:
        return {'type': 'student', 'data': student}
    return None

def get_student_by_id(idno):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE idno = ?", (idno,))
    student = cursor.fetchone()
    conn.close()
    return student

def update_student_profile(student_id, data):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Handle middle name - convert None to empty string and strip whitespace
        midname = data.get('midname') or ''
        midname = midname.strip()
        
        if data.get("profile_picture_url"):
            cursor.execute("""
                UPDATE students SET firstname=?, lastname=?, midname=?,
                course=?, year_level=?, email_address=?, profile_picture=? 
                WHERE idno=?
            """, (data['firstname'], data['lastname'], midname,
                  data['course'], data['year_level'], data['email_address'],
                  data['profile_picture_url'], student_id))
        else:
            cursor.execute("""
                UPDATE students SET firstname=?, lastname=?, midname=?,
                course=?, year_level=?, email_address=? WHERE idno=?
            """, (data['firstname'], data['lastname'], midname,
                  data['course'], data['year_level'], data['email_address'],
                  student_id))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating student profile: {e}")
        return False
    finally:
        conn.close()

def get_announcements():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM announcements ORDER BY created_at DESC")
    announcements = cursor.fetchall()
    conn.close()
    return announcements

def insert_announcement(title, content):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("INSERT INTO announcements (title, content, created_at) VALUES (?, ?, ?)", (title, content, created_at))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error inserting announcement: {e}")
        return False
    finally:
        conn.close()

def update_announcement(id, title, content):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            UPDATE announcements 
            SET title = ?, content = ?, updated_at = ? 
            WHERE id = ?''', 
            (title, content, updated_at, id))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating announcement: {e}")
        return False

def delete_announcement(id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM announcements WHERE id = ?', (id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error deleting announcement: {e}")
        return False

def get_student_count():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM students')
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Exception as e:
        print(f"Error getting student count: {e}")
        return 0

def get_current_sit_in_count():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM sit_in_records WHERE logout_time IS NULL')
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Exception as e:
        print(f"Error getting current sit-in count: {e}")
        return 0

def get_total_sit_in_count():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM sit_in_records')
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Exception as e:
        print(f"Error getting total sit-in count: {e}")
        return 0

def get_sit_in_purposes_data():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT purpose, COUNT(*) as count 
        FROM sit_in_records 
        GROUP BY purpose 
        ORDER BY count DESC
    """)
    results = cursor.fetchall()
    conn.close()

    labels = [row[0] for row in results]  # Purpose names
    counts = [row[1] for row in results]  # Count for each purpose
    
    return {
        'labels': labels,
        'counts': counts
    }

def get_sit_in_purposes_stats():
    """Get statistics for sit-in purposes"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Simplified query to get all purposes
        cursor.execute("""
            SELECT 
                purpose,
                COUNT(*) as count 
            FROM sit_in_records 
            WHERE purpose IS NOT NULL
            GROUP BY purpose 
            ORDER BY count DESC
        """)
        
        rows = cursor.fetchall()
        
        # Convert row objects to simple lists
        labels = []
        counts = []
        for row in rows:
            labels.append(row[0])
            counts.append(row[1])
        
        return {
            'labels': labels,
            'counts': counts,
            'success': True
        }
        
    except Exception as e:
        print(f"Database error in get_sit_in_purposes_stats: {str(e)}")
        return {
            'labels': [],
            'counts': [],
            'success': False,
            'error': str(e)
        }
    finally:
        if conn:
            conn.close()

def get_sit_in_history_by_student(idno):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, id_number, name, sit_purpose, laboratory, login_time, logout_time, date, feedback, feedback_date
        FROM sit_in_history
        WHERE id_number = ?
        ORDER BY date DESC, login_time DESC
    """, (idno,))
    history = cursor.fetchall()
    conn.close()
    return history

def insert_feedback(history_id, feedback, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        feedback_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            UPDATE sit_in_history SET feedback = ?, feedback_date = ?
            WHERE id = ? AND id_number = ?
        """, (feedback, feedback_date, history_id, user_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error updating feedback: {e}")
        return False
    finally:
        conn.close()

def insert_student(student_data):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO students (idno, lastname, firstname, midname, course, year_level,
            email_address, username, password, session_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            student_data['idno'], student_data['lastname'], student_data['firstname'],
            student_data['midname'], student_data['course'], student_data['year_level'],
            student_data['email'], student_data['username'], student_data['password'],
            student_data['session_count']
        ))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error inserting student: {e}")
        return False
    finally:
        conn.close()

def student_exists(idno, username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE idno = ? OR username = ?", (idno, username))
    student = cursor.fetchone()
    conn.close()
    return student is not None

def check_student_id_exists(student_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT idno FROM students WHERE idno = ?", (student_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def create_student(student_data):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        sql = """
        INSERT INTO students (
            idno, lastname, firstname, midname, 
            email_address, course, year_level, username, password,
            session_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 30)
        """  # Set initial session_count to 30
        
        cursor.execute(sql, (
            student_data['student_id'],
            student_data['lastname'],
            student_data['firstname'],
            student_data.get('middlename', ''),
            student_data['email'],
            student_data['course'],
            student_data['year_level'],
            student_data['username'],
            student_data['password']
        ))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error creating student: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_students():
    """Get all students from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()
    conn.close()
    return students

def get_current_sit_ins():
    """Get all active sit-in sessions."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.*, csi.purpose, csi.sit_lab, csi.session
        FROM students s
        JOIN current_sit_in csi ON s.idno = csi.id_number
        WHERE csi.status = 'Active'
    """)
    sit_ins = cursor.fetchall()
    conn.close()
    return sit_ins

def get_sit_in_records():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sir.id_number, sir.name, sir.purpose, sir.lab,
               sir.login_time, 
               CASE 
                   WHEN sir.logout_time IS NULL THEN 'Active'
                   ELSE sir.logout_time 
               END as logout_time
        FROM sit_in_records sir
        ORDER BY sir.login_time DESC
    """)
    records = cursor.fetchall()
    conn.close()
    return [dict(zip(['id_number', 'name', 'purpose', 'lab', 'login_time', 'logout_time'], record)) 
            for record in records]

def get_reports():
    """Get all sit-in reports."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            sir.id_number,
            s.firstname || ' ' || s.lastname as name,
            sir.purpose as purpose,
            sir.lab as lab,
            sir.login_time,
            sir.logout_time,
            CASE 
                WHEN sir.logout_time IS NULL THEN 'Active'
                ELSE CAST(
                    (julianday(sir.logout_time) - julianday(sir.login_time)) * 24 
                    AS TEXT) || ' hours'
            END as duration,
            date(sir.login_time) as date
        FROM sit_in_records sir
        JOIN students s ON sir.id_number = s.idno
        ORDER BY sir.login_time DESC
    """)
    reports = cursor.fetchall()
    conn.close()
    return reports

def get_filtered_reports(selected_lab='', selected_purpose=''):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT 
            sir.id_number,
            sir.name,
            sir.purpose,
            sir.lab,
            datetime(sir.login_time, 'localtime') as login_time,
            CASE 
                WHEN sir.logout_time IS NULL THEN 'Active'
                ELSE datetime(sir.logout_time, 'localtime')
            END as logout_time,
            CASE 
                WHEN sir.logout_time IS NULL THEN 'Active'
                ELSE ROUND((julianday(sir.logout_time) - julianday(sir.login_time)) * 24, 2) || ' hours'
            END as duration,
            date(sir.login_time, 'localtime') as date
        FROM sit_in_records sir
        WHERE 1=1
    """
    params = []
    
    if selected_lab:
        query += " AND sir.lab = ?"
        params.append(selected_lab)
    if selected_purpose:
        query += " AND sir.purpose = ?"
        params.append(selected_purpose)
    
    query += " ORDER BY sir.login_time DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    # Format the results
    reports = []
    for row in rows:
        reports.append({
            'id_number': row[0],
            'name': row[1],
            'purpose': row[2],
            'lab': row[3],
            'login_time': row[4],
            'logout_time': row[5],
            'duration': row[6],
            'date': row[7]
        })
    
    conn.close()
    
    return {
        'reports': reports
    }

def get_export_data(lab='', purpose=''):
    """Get data for export with optional lab and purpose filters"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Base query
        query = """
            SELECT 
                id_number,
                name,
                purpose,
                lab,
                login_time,
                logout_time,
                CASE
                    WHEN logout_time IS NULL THEN 'Active Session'
                    ELSE CAST((julianday(logout_time) - julianday(login_time)) * 24 * 60 AS INTEGER) || ' minutes'
                END AS duration,
                date
            FROM sit_in_records
            WHERE 1=1
        """
        
        # Add filters if provided
        params = []
        if lab:
            query += " AND lab = ?"
            params.append(lab)
        
        if purpose:
            query += " AND purpose = ?"
            params.append(purpose)
        
        # Order by date and login time
        query += " ORDER BY date DESC, login_time DESC"
        
        cursor.execute(query, params)
        
        # Convert to dictionary of records
        columns = [column[0] for column in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        
        return {'data': data}
    
    except Exception as e:
        print(f"Error getting export data: {str(e)}")
        return {'data': [], 'error': str(e)}

def get_labs():
    """Get list of available laboratories."""
    return ['Room 524', 'Room 526', 'Room 528', 'Room 530', 
            'Room 542', 'Room 544', 'Room 517']

def get_purposes():
    """Get list of available purposes."""
    return [
        'C Programming', 'Java Programming', 'Python Programming',
        'C# Programming', 'Database', 'Digital logic & Design',
        'Embedded Systems & IoT', 'System Integration & Architecture',
        'Computer Application', 'Project Management', 'IT Trends',
        'Technopreneurship', 'Capstone'
    ]

def get_feedbacks(selected_lab=None):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT 
            id_number,
            name,
            sit_purpose,
            laboratory,
            login_time,
            logout_time,
            date,
            feedback,
            feedback_date
        FROM sit_in_history 
        WHERE feedback IS NOT NULL
    """
    params = []
    
    if selected_lab and selected_lab != '':
        query += " AND laboratory = ?"
        params.append(selected_lab)
    
    query += " ORDER BY feedback_date DESC"
    
    cursor.execute(query, params)
    feedbacks = cursor.fetchall()
    conn.close()
    
    return [{
        'id_number': str(f[0]),
        'name': str(f[1]),
        'sit_purpose': str(f[2]),
        'laboratory': str(f[3]),
        'login_time': str(f[4]),
        'logout_time': str(f[5]),
        'date': str(f[6]),
        'feedback': str(f[7]),
        'feedback_date': str(f[8])
    } for f in feedbacks]

def reset_all_active_sessions():
    """Reset all active sit-in sessions, session counts, and sit-in histories for all students."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Begin transaction
        conn.execute("BEGIN TRANSACTION")
        
        # Update all active sit-in records with current timestamp
        cursor.execute("""
            UPDATE sit_in_records 
            SET logout_time = datetime('now', 'localtime')
            WHERE logout_time IS NULL
        """)
        
        # Reset session count to 30 for all students
        cursor.execute("""
            UPDATE students 
            SET session_count = 30
        """)
        
        # Delete all sit-in records
        cursor.execute("DELETE FROM sit_in_records")
        
        # Delete all sit-in history records
        cursor.execute("DELETE FROM sit_in_history")

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error in reset_all_active_sessions: {e}")
        return False
    finally:
        conn.close()

def reset_student_session(idno):
    """Reset session count and sit-in history for a specific student."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Reset session count to 30 for the student
        cursor.execute("""
            UPDATE students 
            SET session_count = 30
            WHERE idno = ?
        """, (idno,))
        
        # Delete all sit-in records for this student
        cursor.execute("DELETE FROM sit_in_records WHERE id_number = ?", (idno,))

        # Delete sit-in history for this student
        cursor.execute("DELETE FROM sit_in_history WHERE id_number = ?", (idno,))

        conn.commit()
        return True
    except Exception as e:
        print(f"Error in reset_student_session: {e}")
        return False
    finally:
        conn.close()

def add_reward_point(student_id):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Begin transaction
        cursor.execute("BEGIN TRANSACTION")
        
        # Ensure reward_points and reward_redeemable columns exist
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN reward_points INTEGER DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN reward_redeemable INTEGER DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # End current session and deduct session count
        cursor.execute("""
            UPDATE sit_in_records 
            SET logout_time = datetime('now', 'localtime')
            WHERE id_number = ? AND logout_time IS NULL
        """, (student_id,))

        # Add 1 to both reward_points (total) and reward_redeemable (for redemption logic)
        cursor.execute("""
            UPDATE students 
            SET session_count = CASE
                WHEN session_count > 0 THEN session_count - 1
                ELSE 0
            END,
            reward_points = COALESCE(reward_points, 0) + 1,
            reward_redeemable = COALESCE(reward_redeemable, 0) + 1
            WHERE idno = ?
        """, (student_id,))

        # Check if redeemable points reached 3
        cursor.execute("SELECT reward_redeemable FROM students WHERE idno = ?", (student_id,))
        redeemable = cursor.fetchone()
        if redeemable and redeemable[0] >= 3:
            # Reset redeemable and add 1 session
            cursor.execute("""
                UPDATE students 
                SET reward_redeemable = 0,
                    session_count = session_count + 1
                WHERE idno = ?
            """, (student_id,))

        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding reward point: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_top_performing_students(limit=50):
    """Get students ordered by reward points."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Ensure reward_points column exists
        try:
            cursor.execute("SELECT reward_points FROM students LIMIT 1")
        except sqlite3.OperationalError:
             # If column doesn't exist, return empty list or handle appropriately
            print("Reward points column does not exist.")
            return []

        cursor.execute("""
            SELECT idno, firstname, lastname, course, year_level, 
                   COALESCE(reward_points, 0) as reward_points
            FROM students 
            WHERE COALESCE(reward_points, 0) > 0
            ORDER BY reward_points DESC, lastname ASC
            LIMIT ?
        """, (limit,))
        students = cursor.fetchall()
        return students
    except Exception as e:
        print(f"Error fetching top performing students: {e}")
        return []
    finally:
        conn.close()

def get_most_active_students(limit=50):
    """Get students ordered by the number of sit-in sessions used (most active = most sessions used)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                s.idno, 
                s.firstname, 
                s.lastname, 
                s.course, 
                s.year_level, 
                COUNT(sir.id) as sit_in_count
            FROM students s
            JOIN sit_in_records sir ON s.idno = sir.id_number
            GROUP BY s.idno
            ORDER BY sit_in_count DESC, s.lastname ASC
            LIMIT ?
        """, (limit,))
        students = cursor.fetchall()
        return students
    except Exception as e:
        print(f"Error fetching most active students: {e}")
        return []
    finally:
        conn.close()

def get_combined_leaderboard_students(limit=5):
    """Get top students based on sit-in count and reward points."""
    print("Attempting to fetch combined leaderboard students...") # DEBUG
    conn = get_connection()
    cursor = conn.cursor()
    students = [] # Initialize students as empty list
    try:
        # Ensure reward_points column exists, add if not (optional, defensive coding)
        try:
            cursor.execute("SELECT reward_points FROM students LIMIT 1")
        except sqlite3.OperationalError:
            print("Reward points column potentially missing, attempting to add...") # DEBUG
            try:
                cursor.execute("ALTER TABLE students ADD COLUMN reward_points INTEGER DEFAULT 0")
                conn.commit()
                print("Added reward_points column to students table.") # DEBUG
            except sqlite3.OperationalError as alter_err:
                 print(f"Could not add reward_points column, might already exist: {alter_err}") # DEBUG
                 pass
        # Ensure reward_redeemable column exists
        try:
            cursor.execute("SELECT reward_redeemable FROM students LIMIT 1")
        except sqlite3.OperationalError:
            try:
                cursor.execute("ALTER TABLE students ADD COLUMN reward_redeemable INTEGER DEFAULT 0")
                conn.commit()
            except sqlite3.OperationalError:
                pass

        cursor.execute("""
            SELECT 
                s.idno, 
                s.firstname, 
                s.lastname, 
                s.course, 
                s.year_level, 
                COUNT(sir.id_number) as sit_in_count,
                COALESCE(s.reward_points, 0) as reward_points
            FROM students s
            LEFT JOIN sit_in_records sir ON s.idno = sir.id_number
            GROUP BY s.idno
            ORDER BY sit_in_count DESC, reward_points DESC, s.lastname ASC
            LIMIT ?
        """, (limit,))
        students = cursor.fetchall()
        print(f"Fetched {len(students)} students for leaderboard.") # DEBUG
        leaderboard = []
        for student in students:
            if hasattr(student, 'keys'):
                leaderboard.append(dict(student))
            else:
                leaderboard.append({
                    'idno': student[0],
                    'firstname': student[1],
                    'lastname': student[2],
                    'course': student[3],
                    'year_level': student[4],
                    'sit_in_count': student[5],
                    'reward_points': student[6]
                })
        print("DEBUG: leaderboard =", leaderboard)
        return leaderboard
    except Exception as e:
        print(f"Error fetching combined leaderboard students: {e}") # DEBUG
        return [] # Return empty list on error
    finally:
        print("Closing connection for get_combined_leaderboard_students.") # DEBUG
        conn.close()

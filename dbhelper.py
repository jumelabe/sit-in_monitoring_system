import sqlite3
from datetime import datetime

DB_NAME = 'users.db'

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    # Ensure sit_in_count column exists
    try:
        conn.execute("ALTER TABLE students ADD COLUMN sit_in_count INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass
        
    # Ensure we have the sit_in_records table with all needed columns
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sit_in_records (
                sit_in_id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_number TEXT NOT NULL,
                name TEXT NOT NULL,
                purpose TEXT,
                lab TEXT,
                login_time DATETIME,
                logout_time DATETIME,
                date TEXT,
                computer_number INTEGER
            )
        """)
        conn.commit()
    except sqlite3.OperationalError:
        pass
        
    # Ensure computer_number column exists in sit_in_records
    try:
        conn.execute("ALTER TABLE sit_in_records ADD COLUMN computer_number INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass
        
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
    """Get sit-in history for a specific student."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                h.id,
                h.id_number,
                h.name,
                h.sit_purpose,
                h.laboratory,
                datetime(h.login_time, 'localtime') as login_time,
                datetime(h.logout_time, 'localtime') as logout_time,
                h.date,
                h.action,
                h.feedback,
                datetime(h.feedback_date, 'localtime') as feedback_date
            FROM sit_in_history h
            WHERE h.id_number = ?
            ORDER BY h.date DESC, h.login_time DESC
        """, (idno,))
        
        history = cursor.fetchall()
        print(f"Found {len(history)} history records for student {idno}")  # Debug print
        
        return [{
            'id': row['id'],
            'id_number': row['id_number'],
            'name': row['name'],
            'sit_purpose': row['sit_purpose'],
            'laboratory': row['laboratory'],
            'login_time': row['login_time'],
            'logout_time': row['logout_time'],
            'date': row['date'],
            'action': row['action'],
            'feedback': row['feedback'],
            'feedback_date': row['feedback_date']
        } for row in history]
    except Exception as e:
        print(f"Error getting sit-in history: {e}")
        return []
    finally:
        conn.close()

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
        SELECT sir.sit_in_id, sir.id_number, sir.name, sir.purpose, sir.lab,
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
    return [dict(zip(['sit_in_id', 'id_number', 'name', 'purpose', 'lab', 'login_time', 'logout_time'], record)) 
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
        # Format duration for better readability in reports
        duration = row[6]
        if duration != 'Active' and 'hours' in duration:
            try:
                hours = float(duration.replace(' hours', ''))
                if hours < 1:
                    # Convert to minutes for short durations
                    minutes = round(hours * 60)
                    duration = f"{minutes} minutes"
                elif hours >= 24:
                    # Format days for long durations
                    days = int(hours / 24)
                    remaining_hours = round(hours % 24, 1)
                    if remaining_hours > 0:
                        duration = f"{days} days, {remaining_hours} hours"
                    else:
                        duration = f"{days} days"
                else:
                    # Format hours with better precision
                    hours_int = int(hours)
                    minutes = int((hours - hours_int) * 60)
                    if minutes > 0:
                        duration = f"{hours_int} hours, {minutes} minutes"
                    else:
                        duration = f"{hours_int} hours"
            except (ValueError, TypeError):
                pass  # Keep original duration if parsing fails
                
        reports.append({
            'id_number': row[0],
            'name': row[1],
            'purpose': row[2],
            'lab': row[3],
            'login_time': row[4],
            'logout_time': row[5],
            'duration': duration,
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
    labs = ['Room 524', 'Room 526', 'Room 527', 'Room 530', 
            'Room 542', 'Room 544', 'Room 517']
    return labs

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
    """Reset all students' session counts to 30, reset reward points, redeemable points, and sit-in counts (leaderboards)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Ensure reward_points, reward_redeemable, and sit_in_count columns exist
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
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN sit_in_count INTEGER DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        # Reset session count, reward_points, reward_redeemable, and sit_in_count for all students
        cursor.execute("""
            UPDATE students 
            SET session_count = 30,
                reward_points = 0,
                reward_redeemable = 0,
                sit_in_count = 0
        """)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error in reset_all_active_sessions: {e}")
        return False
    finally:
        conn.close()

def reset_student_session(idno):
    """Reset session count, reward points, redeemable points, and sit_in_count for a specific student.
       Only reset the student's session stats, NOT their sit-in records/history."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Ensure reward_points, reward_redeemable, and sit_in_count columns exist
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
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN sit_in_count INTEGER DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        # Reset session count, reward_points, reward_redeemable, and sit_in_count for the student
        cursor.execute("""
            UPDATE students 
            SET session_count = 30,
                reward_points = 0,
                reward_redeemable = 0,
                sit_in_count = 0
            WHERE idno = ?
        """, (idno,))
        # DO NOT delete sit-in records/history!
        conn.commit()
        return True
    except Exception as e:
        print(f"Error in reset_student_session: {e}")
        return False
    finally:
        conn.close()

def insert_sit_in_history_from_record(student_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                sir.id_number,
                sir.name,
                sir.purpose as sit_purpose,
                sir.lab as laboratory,
                datetime(sir.login_time, 'localtime') as login_time,
                datetime(sir.logout_time, 'localtime') as logout_time,
                date(sir.login_time, 'localtime') as date
            FROM sit_in_records sir
            WHERE sir.id_number = ? AND sir.logout_time IS NOT NULL
            ORDER BY sir.logout_time DESC LIMIT 1
        """, (student_id,))
        record = cursor.fetchone()

        if record:
            # Insert into sit_in_history with proper field mapping and default action
            cursor.execute("""
                INSERT INTO sit_in_history (
                    id_number, name, sit_purpose, laboratory,
                    login_time, logout_time, date, action
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record['id_number'],
                record['name'],
                record['sit_purpose'],
                record['laboratory'],
                record['login_time'],
                record['logout_time'],
                record['date'],
                'Completed'  # Default action value
            ))
            # Increment sit_in_count for the student
            cursor.execute("""
                UPDATE students SET sit_in_count = COALESCE(sit_in_count, 0) + 1 WHERE idno = ?
            """, (student_id,))
            conn.commit()
            print(f"Successfully inserted history record for student {student_id}")  # Debug print
            return True
        return False
    except Exception as e:
        print(f"Error inserting sit-in history: {e}")
        conn.rollback()
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
        
        # Ensure reward_points, reward_redeemable, and sit_in_count columns exist
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
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN sit_in_count INTEGER DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # End current session and deduct session count
        cursor.execute("""
            UPDATE sit_in_records 
            SET logout_time = datetime('now', 'localtime')
            WHERE id_number = ? AND logout_time IS NULL
        """, (student_id,))

        # Insert into sit_in_history after session ends (this will increment sit_in_count)
        conn.commit()  # Commit the logout_time update before copying to history
        insert_sit_in_history_from_record(student_id)
        cursor = conn.cursor()  # Re-acquire cursor after commit

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
        # Use sit_in_count column
        cursor.execute("""
            SELECT 
                idno, 
                firstname, 
                lastname, 
                course, 
                year_level, 
                COALESCE(sit_in_count, 0) as sit_in_count
            FROM students
            ORDER BY sit_in_count DESC, lastname ASC
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
        # Ensure reward_points, reward_redeemable, and sit_in_count columns exist
        try:
            cursor.execute("SELECT reward_points FROM students LIMIT 1")
        except sqlite3.OperationalError:
            try:
                cursor.execute("ALTER TABLE students ADD COLUMN reward_points INTEGER DEFAULT 0")
                conn.commit()
            except sqlite3.OperationalError:
                pass
        try:
            cursor.execute("SELECT reward_redeemable FROM students LIMIT 1")
        except sqlite3.OperationalError:
            try:
                cursor.execute("ALTER TABLE students ADD COLUMN reward_redeemable INTEGER DEFAULT 0")
                conn.commit()
            except sqlite3.OperationalError:
                pass
        try:
            cursor.execute("SELECT sit_in_count FROM students LIMIT 1")
        except sqlite3.OperationalError:
            try:
                cursor.execute("ALTER TABLE students ADD COLUMN sit_in_count INTEGER DEFAULT 0")
                conn.commit()
            except sqlite3.OperationalError:
                pass

        cursor.execute("""
            SELECT 
                idno, 
                firstname, 
                lastname, 
                course, 
                year_level, 
                COALESCE(sit_in_count, 0) as sit_in_count,
                COALESCE(reward_points, 0) as reward_points
            FROM students
            ORDER BY sit_in_count DESC, reward_points DESC, lastname ASC
            LIMIT ?
        """, (limit,))
        students = cursor.fetchall()
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

def ensure_resource_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            file_name TEXT,
            url TEXT,
            uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Try to add 'enabled' column if it does not exist
    try:
        cursor.execute("ALTER TABLE resources ADD COLUMN enabled INTEGER DEFAULT 1")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.close()

def ensure_computers_table():
    """Create the computers table if it doesn't exist"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS computers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lab_room TEXT NOT NULL,
            pc_number INTEGER NOT NULL,
            status TEXT DEFAULT 'available',
            student_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(lab_room, pc_number)
        )
    """)
    conn.commit()
    conn.close()

def initialize_sample_computers():
    """Initialize sample computers for each lab if none exist"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if computers already exist
    cursor.execute("SELECT COUNT(*) FROM computers")
    count = cursor.fetchone()[0]
    
    if count == 0:
        # No computers exist, let's add sample data
        labs = get_labs()
        
        # For each lab, create 50 computers
        for lab in labs:
            # Ensure consistent format for lab rooms - always use "Room XXX" format
            if not lab.startswith("Room ") and lab.strip().isdigit():
                lab_room = f"Room {lab.strip()}"
            else:
                lab_room = lab
                
            print(f"Initializing computers for lab: {lab_room}")
            
            for pc_number in range(1, 51):
                try:
                    cursor.execute("""
                        INSERT INTO computers (lab_room, pc_number, status)
                        VALUES (?, ?, 'available')
                    """, (lab_room, pc_number))
                except sqlite3.IntegrityError:
                    # Skip if already exists (due to unique constraint)
                    pass
        
        conn.commit()
    
    conn.close()

def insert_resource(title, description, file_name=None, url=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO resources (title, description, file_name, url, enabled) VALUES (?, ?, ?, ?, 1)",
            (title, description, file_name, url)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error inserting resource: {e}")
        return False
    finally:
        conn.close()

def get_all_resources(enabled_only=False):
    conn = get_connection()
    cursor = conn.cursor()
    # Defensive: ensure 'enabled' column exists
    try:
        cursor.execute("SELECT enabled FROM resources LIMIT 1")
    except sqlite3.OperationalError:
        try:
            cursor.execute("ALTER TABLE resources ADD COLUMN enabled INTEGER DEFAULT 1")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    if enabled_only:
        cursor.execute("SELECT id, title, description, file_name, url, uploaded_at, enabled FROM resources WHERE enabled = 1 ORDER BY uploaded_at DESC")
    else:
        cursor.execute("SELECT id, title, description, file_name, url, uploaded_at, enabled FROM resources ORDER BY uploaded_at DESC")
    resources = cursor.fetchall()
    conn.close()
    return resources

def set_resource_enabled(resource_id, enabled):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE resources SET enabled = ? WHERE id = ?", (1 if enabled else 0, resource_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating resource enabled status: {e}")
        return False
    finally:
        conn.close()

def delete_resource(resource_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Optionally, fetch file_name before deleting for file removal
        cursor.execute("SELECT file_name FROM resources WHERE id = ?", (resource_id,))
        row = cursor.fetchone()
        file_name = row[0] if row else None
        cursor.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
        conn.commit()
        return file_name
    except Exception as e:
        print(f"Error deleting resource: {e}")
        return None
    finally:
        conn.close()

def get_lab_computer_stats():
    """Return a list of dicts: lab_room, total, available, in_use, maintenance."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT lab_room,
               COUNT(*) as total,
               SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
               SUM(CASE WHEN status = 'in_use' THEN 1 ELSE 0 END) as in_use,
               SUM(CASE WHEN status = 'maintenance' THEN 1 ELSE 0 END) as maintenance
        FROM computers
        GROUP BY lab_room
        ORDER BY lab_room
    """)
    stats = []
    for row in cursor.fetchall():
        stats.append({
            'lab_room': row[0],
            'total': row[1],
            'available': row[2],
            'in_use': row[3],
            'maintenance': row[4]
        })
    conn.close()
    return stats

def get_lab_rooms():
    """Return a list of unique lab rooms from computers table."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT lab_room FROM computers ORDER BY lab_room")
    labs = [row[0] for row in cursor.fetchall()]
    conn.close()
    return labs

def get_computers_by_lab(lab_room):
    """Return a list of computers for a given lab_room."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, pc_number, status, student_id
        FROM computers
        WHERE lab_room = ?
        ORDER BY pc_number
    """, (lab_room,))
    computers = []
    for row in cursor.fetchall():
        computers.append({
            'id': row[0],
            'pc_number': row[1],
            'status': row[2],
            'student_id': row[3]
        })
    conn.close()
    return computers

def update_computer_status(computer_id, status, student_id=None):
    """Update the status (and optionally student_id) of a computer."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Validate input parameters
        if not computer_id:
            raise ValueError("Computer ID is required")
        
        if status not in ['available', 'in_use', 'maintenance']:
            raise ValueError(f"Invalid status: {status}")
        
        # First check if the computer exists
        cursor.execute("SELECT id FROM computers WHERE id = ?", (computer_id,))
        if not cursor.fetchone():
            raise ValueError(f"Computer with ID {computer_id} not found")
        
        # If assigning to a student, verify student exists
        if status == 'in_use' and student_id:
            cursor.execute("SELECT idno FROM students WHERE idno = ?", (student_id,))
            if not cursor.fetchone():
                raise ValueError(f"Student with ID {student_id} not found")
        
        # Update the database based on status
        if status == 'in_use' and student_id:
            cursor.execute(
                "UPDATE computers SET status=?, student_id=? WHERE id=?",
                (status, student_id, computer_id)
            )
        elif status == 'available':
            cursor.execute(
                "UPDATE computers SET status=?, student_id=NULL WHERE id=?",
                (status, computer_id)
            )
        else:
            cursor.execute(
                "UPDATE computers SET status=? WHERE id=?",
                (status, computer_id)
            )
            
        conn.commit()
        return True
    except ValueError as e:
        # Handle validation errors separately to provide better feedback
        print(f"Validation error in update_computer_status: {str(e)}")
        conn.rollback()
        raise
    except Exception as e:
        print(f"Database error in update_computer_status: {str(e)}")
        conn.rollback()
        raise
    finally:
        conn.close()

def ensure_reservation_table():
    """Create the computer reservation requests table if it doesn't exist"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS computer_reservation_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            student_name TEXT NOT NULL,
            lab_room TEXT NOT NULL,
            purpose TEXT NOT NULL,
            date TEXT NOT NULL,
            time_in TEXT NOT NULL,
            computer_number INTEGER,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    """)
    conn.commit()
    
    # Check if notes column exists, add it if not
    try:
        cursor.execute("SELECT notes FROM computer_reservation_requests LIMIT 1")
    except sqlite3.OperationalError:
        try:
            cursor.execute("ALTER TABLE computer_reservation_requests ADD COLUMN notes TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column might already exist
    
    conn.close()

def get_reservation_requests():
    """Get all pending reservation requests"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM computer_reservation_requests
        WHERE status = 'pending'
        ORDER BY date, time_in
    """)
    requests = cursor.fetchall()
    conn.close()
    return requests

def get_reservation_logs(filters=None):
    """Get all reservation logs with optional filtering"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Ensure the reservation_logs table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reservation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER,
                student_id TEXT,
                lab_room TEXT,
                computer_number INTEGER,
                purpose TEXT,
                reservation_time TEXT,
                action TEXT,
                status TEXT,
                details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        
        # Base query
        query = """
            SELECT 
                id, request_id, student_id, lab_room, computer_number, purpose,
                reservation_time, action, status, details, 
                datetime(timestamp, 'localtime') as formatted_timestamp
            FROM reservation_logs
        """
        
        params = []
        
        # Apply filters if provided
        if filters:
            where_clauses = []
            if filters.get('student_id'):
                where_clauses.append("student_id = ?")
                params.append(filters['student_id'])
            if filters.get('lab_room'):
                where_clauses.append("lab_room = ?")
                params.append(filters['lab_room'])
            if filters.get('status'):
                where_clauses.append("status = ?")
                params.append(filters['status'])
            if filters.get('action'):
                where_clauses.append("action = ?")
                params.append(filters['action'])
            
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
        
        # Order by timestamp descending
        query += " ORDER BY timestamp DESC"
        
        cursor.execute(query, params)
        logs = cursor.fetchall()
        
        # Format the logs
        formatted_logs = []
        for log in logs:
            log_dict = {}
            for key in log.keys():
                log_dict[key] = log[key]
            formatted_logs.append(log_dict)
        
        return formatted_logs
    except Exception as e:
        print(f"Error getting reservation logs: {e}")
        return []
    finally:
        conn.close()

def log_reservation_action(request_id, action, details=''):
    """Log a reservation action to the reservation_logs table.
    Always call this after approving or denying a reservation to ensure logs are up-to-date.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Ensure the reservation_logs table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reservation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER,
                student_id TEXT,
                lab_room TEXT,
                computer_number INTEGER,
                purpose TEXT,
                reservation_time TEXT,
                action TEXT,
                status TEXT,
                details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        
        # Get the reservation details
        cursor.execute("""
            SELECT student_id, student_name, lab_room, computer_number, purpose, 
                   date, time_in, status
            FROM computer_reservation_requests 
            WHERE id = ?
        """, (request_id,))
        
        reservation = cursor.fetchone()
        if not reservation:
            raise Exception(f"Reservation request {request_id} not found")
        
        # Sanitize values - make sure we don't have any None values
        student_id = reservation['student_id'] or ''
        lab_room = reservation['lab_room'] or ''
        computer_number = reservation['computer_number'] or 0
        purpose = reservation['purpose'] or ''
        date = reservation['date'] or ''
        time_in = reservation['time_in'] or ''
        
        # Set status based on action (for consistent display) and update the database
        if action == 'approved':
            status = 'approved'
            # Update the request status in computer_reservation_requests table
            cursor.execute("""
                UPDATE computer_reservation_requests 
                SET status = 'approved' 
                WHERE id = ?
            """, (request_id,))
        elif action == 'denied':
            status = 'denied'
            # Update the request status in computer_reservation_requests table
            cursor.execute("""
                UPDATE computer_reservation_requests 
                SET status = 'denied' 
                WHERE id = ?
            """, (request_id,))
        else:
            status = reservation['status'] or 'pending'
        
        # Format the reservation time
        reservation_time = f"{date} {time_in}"
        if reservation_time.strip() == ' ':
            reservation_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Log the action
        cursor.execute("""
            INSERT INTO reservation_logs (
                request_id, student_id, lab_room, computer_number, purpose,
                reservation_time, action, status, details, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
        """, (
            request_id,
            student_id,
            lab_room,
            computer_number,
            purpose,
            reservation_time,
            action,
            status,
            details
        ))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error in log_reservation_action: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def reset_computers_table():
    """Drop and recreate the computers table with 50 computers per lab"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Drop the existing table
        cursor.execute("DROP TABLE IF EXISTS computers")
        conn.commit()
        
        # Recreate the table
        ensure_computers_table()
        
        # Initialize with 50 computers per lab
        initialize_sample_computers()
        
        return True
    except Exception as e:
        print(f"Error resetting computers table: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def create_reservation(reservation_data):
    """Create a new computer reservation request"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get student name
        student_id = reservation_data['id_number']
        cursor.execute("SELECT firstname, lastname FROM students WHERE idno = ?", (student_id,))
        student = cursor.fetchone()
        
        if not student:
            raise Exception("Student not found")
        
        # Check if student already has an active sit-in session
        cursor.execute("""
            SELECT COUNT(*) FROM sit_in_records 
            WHERE id_number = ? AND logout_time IS NULL
        """, (student_id,))
        active_sessions = cursor.fetchone()[0]
        
        if active_sessions > 0:
            raise Exception("You already have an active sit-in session. You cannot create a new reservation until your current session is completed.")
        
        # Get the date and time for the new reservation
        new_date = reservation_data['date']
        new_time = reservation_data['time_in']
        
        # Check if student already has a reservation for the same date and time
        cursor.execute("""
            SELECT COUNT(*) FROM computer_reservation_requests 
            WHERE student_id = ? AND date = ? AND time_in = ? AND status IN ('pending', 'approved')
        """, (student_id, new_date, new_time))
        conflicting_reservations = cursor.fetchone()[0]
        
        if conflicting_reservations > 0:
            raise Exception("You already have a reservation for this date and time. Please choose a different time slot.")
            
        student_name = f"{student['firstname']} {student['lastname']}"
        
        # Create the reservation request
        cursor.execute("""
            INSERT INTO computer_reservation_requests (
                student_id, student_name, lab_room, purpose, date, time_in, computer_number, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            student_id,
            student_name,
            reservation_data['lab'],
            reservation_data['purpose'],
            reservation_data['date'],
            reservation_data['time_in'],
            # Extract computer number from computer_id
            get_computer_number_by_id(reservation_data['computer_id']),
            # Status is pending by default
        ))
        
        # Get the ID of the newly created reservation
        cursor.execute("SELECT last_insert_rowid()")
        request_id = cursor.fetchone()[0]
        
        # If reservation is successful, temporarily mark the computer as 'reserved'
        # We don't update the computer yet, it will be updated when admin approves the reservation
        
        conn.commit()
        
        # Log the reservation creation
        try:
            log_reservation_action(
                request_id, 
                'created', 
                f"Reservation created for {reservation_data['date']} at {reservation_data['time_in']}"
            )
        except Exception as e:
            print(f"Error logging reservation creation: {e}")
            # Don't fail the entire process if logging fails
        
        return True
    except Exception as e:
        print(f"Error creating reservation: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def get_computer_number_by_id(computer_id):
    """Get the PC number for a computer by its ID"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT pc_number FROM computers WHERE id = ?", (computer_id,))
        result = cursor.fetchone()
        return result['pc_number'] if result else None
    except Exception as e:
        print(f"Error getting computer number: {e}")
        return None
    finally:
        conn.close()

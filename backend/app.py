from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
import mysql.connector
import bcrypt
import os
from dotenv import load_dotenv
from datetime import datetime, date
from functools import wraps
from decimal import Decimal

# Load .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__, 
            template_folder='../frontend/templates',
            static_folder='../frontend/static')

app.secret_key = os.environ.get('SECRET_KEY', 'edunexus-secret')
CORS(app, supports_credentials=True)

DB_CONFIG = {
    'host':     os.environ.get('DB_HOST', 'localhost'),
    'port':     int(os.environ.get('DB_PORT', 3306)),
    'user':     os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'railway'),
    'charset':  'utf8mb4',
    'autocommit': True,
}

def get_db():
    """Return a fresh MySQL connection."""
    return mysql.connector.connect(**DB_CONFIG)

def query(sql, params=None, fetchone=False):
    """Execute a query and return results as list of dicts."""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(sql, params or ())
    if sql.strip().upper().startswith('SELECT'):
        result = cursor.fetchone() if fetchone else cursor.fetchall()
    else:
        conn.commit()
        result = cursor.lastrowid
    cursor.close()
    conn.close()
    return result

def serial(obj):
    """Make Decimal / date / datetime JSON-serialisable."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def json_response(data, status=200):
    import json
    return app.response_class(
        response=json.dumps(data, default=serial),
        status=status,
        mimetype='application/json'
    )

# ── AUTH DECORATOR ───────────────────────────────────────────
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                return json_response({'error': 'Unauthorized'}, 401)
            if role and session.get('role') != role:
                return json_response({'error': 'Forbidden'}, 403)
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ── SERVE FRONTEND ───────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

# ============================================================
#  AUTH ROUTES
# ============================================================

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    role     = data.get('role', '')          # 'student' or 'faculty'

    if not username or not password:
        return json_response({'error': 'Username and password required'}, 400)

    user = query(
        "SELECT * FROM users WHERE username=%s AND role=%s",
        (username, role), fetchone=True
    )

    if not user:
        return json_response({'error': 'User not found'}, 404)

    if not bcrypt.checkpw(password.encode(), user['password'].encode()):
        return json_response({'error': 'Invalid password'}, 401)

    # Update last login
    query("UPDATE users SET last_login=NOW() WHERE id=%s", (user['id'],))

    session['user_id'] = user['id']
    session['role']    = user['role']
    session['username'] = user['username']

    # Fetch profile
    if role == 'student':
        profile = query(
            """SELECT s.*, c.name as course_name, c.code as course_code,
                      d.name as dept_name
               FROM students s
               JOIN courses c ON s.course_id = c.id
               JOIN departments d ON c.department_id = d.id
               WHERE s.user_id=%s""",
            (user['id'],), fetchone=True
        )
        session['profile_id'] = profile['id']
    else:
        profile = query(
            """SELECT f.*, d.name as dept_name
               FROM faculty f
               JOIN departments d ON f.department_id = d.id
               WHERE f.user_id=%s""",
            (user['id'],), fetchone=True
        )
        session['profile_id'] = profile['id']

    return json_response({'message': 'Login successful', 'role': role, 'profile': profile})


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return json_response({'message': 'Logged out'})


@app.route('/api/me', methods=['GET'])
@login_required()
def me():
    role = session['role']
    if role == 'student':
        profile = query(
            """SELECT s.*, c.name as course_name, c.code as course_code, d.name as dept_name
               FROM students s JOIN courses c ON s.course_id=c.id
               JOIN departments d ON c.department_id=d.id WHERE s.user_id=%s""",
            (session['user_id'],), fetchone=True
        )
    else:
        profile = query(
            """SELECT f.*, d.name as dept_name FROM faculty f
               JOIN departments d ON f.department_id=d.id WHERE f.user_id=%s""",
            (session['user_id'],), fetchone=True
        )
    return json_response({'role': role, 'profile': profile})

# ============================================================
#  STUDENT ROUTES
# ============================================================

@app.route('/api/student/dashboard', methods=['GET'])
@login_required('student')
def student_dashboard():
    sid = session['profile_id']

    # Latest CGPA
    result = query(
        "SELECT cgpa, sgpa, semester FROM semester_results WHERE student_id=%s ORDER BY semester DESC LIMIT 1",
        (sid,), fetchone=True
    )
    # Overall attendance %
    att = query(
        """SELECT COUNT(*) as total,
                  SUM(CASE WHEN status='present' THEN 1 ELSE 0 END) as present
           FROM attendance WHERE student_id=%s""",
        (sid,), fetchone=True
    )
    att_pct = round((att['present'] / att['total'] * 100), 1) if att['total'] else 0

    # Fee dues
    dues = query(
        "SELECT SUM(amount_due - amount_paid) as due FROM fees WHERE student_id=%s AND status='due'",
        (sid,), fetchone=True
    )
    # Today's classes
    today = datetime.now().strftime('%A')
    classes = query(
        """SELECT s.name as subject, t.start_time, t.end_time, t.room,
                  f.full_name as faculty_name
           FROM timetable t
           JOIN subject_assignments sa ON t.assignment_id = sa.id
           JOIN subjects s ON sa.subject_id = s.id
           JOIN faculty f ON sa.faculty_id = f.id
           JOIN students st ON st.course_id = s.course_id
           WHERE st.id=%s AND t.day_of_week=%s
           ORDER BY t.start_time""",
        (sid, today)
    )
    # Notices
    notices = query(
        """SELECT n.*, f.full_name as posted_by_name FROM notices n
           JOIN faculty f ON n.posted_by=f.id
           ORDER BY n.posted_at DESC LIMIT 5"""
    )
    return json_response({
        'cgpa': result['cgpa'] if result else 0,
        'sgpa': result['sgpa'] if result else 0,
        'current_sem': result['semester'] if result else 1,
        'attendance_pct': att_pct,
        'fee_due': float(dues['due'] or 0),
        'todays_classes': classes,
        'notices': notices
    })


@app.route('/api/student/cgpa', methods=['GET'])
@login_required('student')
def student_cgpa():
    sid = session['profile_id']
    results = query(
        "SELECT * FROM semester_results WHERE student_id=%s ORDER BY semester",
        (sid,)
    )
    return json_response(results)


@app.route('/api/student/report-card', methods=['GET'])
@login_required('student')
def student_report_card():
    sid = session['profile_id']
    sem = request.args.get('semester', 5, type=int)
    marks = query(
        """SELECT s.code, s.name, s.credits, s.type,
                  SUM(CASE WHEN m.assessment_type IN ('internal1','internal2') THEN m.marks_obtained ELSE 0 END) as internal,
                  SUM(CASE WHEN m.assessment_type='external' THEN m.marks_obtained ELSE 0 END) as external,
                  SUM(m.marks_obtained) as total
           FROM marks m
           JOIN subjects s ON m.subject_id = s.id
           WHERE m.student_id=%s AND m.semester=%s
           GROUP BY s.id, s.code, s.name, s.credits, s.type
           ORDER BY s.code""",
        (sid, sem)
    )
    result = query(
        "SELECT * FROM semester_results WHERE student_id=%s AND semester=%s",
        (sid, sem), fetchone=True
    )
    return json_response({'marks': marks, 'result': result, 'semester': sem})


@app.route('/api/student/attendance', methods=['GET'])
@login_required('student')
def student_attendance():
    sid = session['profile_id']
    att = query(
        """SELECT s.name as subject, s.code,
                  COUNT(*) as total,
                  SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) as present,
                  ROUND(SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)/COUNT(*)*100,1) as percentage
           FROM attendance a
           JOIN subjects s ON a.subject_id = s.id
           WHERE a.student_id=%s
           GROUP BY s.id, s.name, s.code
           ORDER BY s.code""",
        (sid,)
    )
    return json_response(att)


@app.route('/api/student/timetable', methods=['GET'])
@login_required('student')
def student_timetable():
    sid = session['profile_id']
    tt = query(
        """SELECT t.day_of_week, t.start_time, t.end_time, t.room,
                  s.name as subject, s.code, f.full_name as faculty
           FROM timetable t
           JOIN subject_assignments sa ON t.assignment_id = sa.id
           JOIN subjects s ON sa.subject_id = s.id
           JOIN faculty f ON sa.faculty_id = f.id
           JOIN students st ON st.course_id = s.course_id
           WHERE st.id=%s
           ORDER BY FIELD(t.day_of_week,'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'),
                    t.start_time""",
        (sid,)
    )
    return json_response(tt)


@app.route('/api/student/subjects', methods=['GET'])
@login_required('student')
def student_subjects():
    sid = session['profile_id']
    subs = query(
        """SELECT s.*, f.full_name as faculty_name
           FROM subjects s
           JOIN subject_assignments sa ON sa.subject_id = s.id
           JOIN faculty f ON sa.faculty_id = f.id
           JOIN students st ON st.course_id = s.course_id
           WHERE st.id=%s AND s.semester=st.current_sem
           ORDER BY s.code""",
        (sid,)
    )
    return json_response(subs)


@app.route('/api/student/modules', methods=['GET'])
@login_required('student')
def student_modules():
    sid = session['profile_id']
    mods = query(
        """SELECT m.*, s.name as subject_name, s.code as subject_code
           FROM modules m
           JOIN subjects s ON m.subject_id = s.id
           JOIN subject_assignments sa ON sa.subject_id = s.id
           JOIN students st ON st.course_id = s.course_id
           WHERE st.id=%s AND s.semester=st.current_sem
           ORDER BY s.code, m.unit_no""",
        (sid,)
    )
    return json_response(mods)


@app.route('/api/student/fees', methods=['GET'])
@login_required('student')
def student_fees():
    sid = session['profile_id']
    fees = query(
        """SELECT f.*, fc.name as category_name
           FROM fees f JOIN fee_categories fc ON f.category_id=fc.id
           WHERE f.student_id=%s ORDER BY f.semester DESC, fc.name""",
        (sid,)
    )
    return json_response(fees)


@app.route('/api/student/notices', methods=['GET'])
@login_required('student')
def student_notices():
    notices = query(
        """SELECT n.*, f.full_name as posted_by_name FROM notices n
           JOIN faculty f ON n.posted_by=f.id
           WHERE n.audience IN ('all','students')
           ORDER BY n.posted_at DESC LIMIT 20"""
    )
    return json_response(notices)

# ============================================================
#  FACULTY ROUTES
# ============================================================

@app.route('/api/faculty/dashboard', methods=['GET'])
@login_required('faculty')
def faculty_dashboard():
    fid = session['profile_id']
    # Courses count
    courses = query(
        "SELECT COUNT(*) as cnt FROM subject_assignments WHERE faculty_id=%s AND academic_year='2024-25'",
        (fid,), fetchone=True
    )
    # Total students
    total_students = query(
        """SELECT COUNT(DISTINCT st.id) as cnt
           FROM subject_assignments sa
           JOIN subjects s ON sa.subject_id=s.id
           JOIN students st ON st.course_id=s.course_id
           WHERE sa.faculty_id=%s AND sa.academic_year='2024-25'""",
        (fid,), fetchone=True
    )
    # Leave balance (casual)
    leaves_used = query(
        "SELECT COALESCE(SUM(days),0) as used FROM leave_applications WHERE faculty_id=%s AND leave_type='casual' AND status='approved'",
        (fid,), fetchone=True
    )
    today = datetime.now().strftime('%A')
    todays_classes = query(
        """SELECT s.name as subject, t.start_time, t.end_time, t.room, sa.section
           FROM timetable t
           JOIN subject_assignments sa ON t.assignment_id=sa.id
           JOIN subjects s ON sa.subject_id=s.id
           WHERE sa.faculty_id=%s AND t.day_of_week=%s
           ORDER BY t.start_time""",
        (fid, today)
    )
    return json_response({
        'total_courses': courses['cnt'],
        'total_students': total_students['cnt'],
        'todays_classes': len(todays_classes),
        'casual_leave_remaining': 12 - int(leaves_used['used']),
        'schedule': todays_classes
    })


@app.route('/api/faculty/timetable', methods=['GET'])
@login_required('faculty')
def faculty_timetable():
    fid = session['profile_id']
    tt = query(
        """SELECT t.day_of_week, t.start_time, t.end_time, t.room,
                  s.name as subject, s.code, sa.section
           FROM timetable t
           JOIN subject_assignments sa ON t.assignment_id=sa.id
           JOIN subjects s ON sa.subject_id=s.id
           WHERE sa.faculty_id=%s AND sa.academic_year='2024-25'
           ORDER BY FIELD(t.day_of_week,'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'),
                    t.start_time""",
        (fid,)
    )
    return json_response(tt)


@app.route('/api/faculty/students', methods=['GET'])
@login_required('faculty')
def faculty_students():
    fid = session['profile_id']
    subject_id = request.args.get('subject_id', type=int)

    sql = """SELECT st.id, st.full_name, st.roll_number, st.enrollment_no,
                    ROUND(
                      COALESCE(SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) / NULLIF(COUNT(a.id),0)*100, 0),1
                    ) as attendance_pct
             FROM students st
             JOIN subject_assignments sa ON 1=1
             JOIN subjects s ON sa.subject_id=s.id AND st.course_id=s.course_id
             LEFT JOIN attendance a ON a.student_id=st.id AND a.subject_id=sa.subject_id AND a.faculty_id=sa.faculty_id
             WHERE sa.faculty_id=%s AND sa.academic_year='2024-25'"""
    params = [fid]
    if subject_id:
        sql += " AND sa.subject_id=%s"
        params.append(subject_id)
    sql += " GROUP BY st.id ORDER BY st.roll_number"

    students = query(sql, params)
    return json_response(students)


@app.route('/api/faculty/attendance', methods=['POST'])
@login_required('faculty')
def mark_attendance():
    fid = session['profile_id']
    data = request.get_json()
    subject_id  = data.get('subject_id')
    date_str    = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    records     = data.get('records', [])   # [{student_id, status}]

    if not subject_id or not records:
        return json_response({'error': 'subject_id and records required'}, 400)

    conn = get_db()
    cursor = conn.cursor()
    saved = 0
    for r in records:
        cursor.execute(
            """INSERT INTO attendance (student_id, subject_id, faculty_id, date, status)
               VALUES (%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE status=%s""",
            (r['student_id'], subject_id, fid, date_str, r['status'], r['status'])
        )
        saved += 1
    conn.commit()
    cursor.close()
    conn.close()
    return json_response({'message': f'Attendance saved for {saved} students'})


@app.route('/api/faculty/marks', methods=['POST'])
@login_required('faculty')
def upload_marks():
    fid = session['profile_id']
    data = request.get_json()
    subject_id      = data.get('subject_id')
    semester        = data.get('semester')
    assessment_type = data.get('assessment_type')
    max_marks       = data.get('max_marks', 30)
    records         = data.get('records', [])   # [{student_id, marks}]

    if not all([subject_id, semester, assessment_type, records]):
        return json_response({'error': 'Missing required fields'}, 400)

    conn = get_db()
    cursor = conn.cursor()
    for r in records:
        cursor.execute(
            """INSERT INTO marks (student_id,subject_id,semester,assessment_type,marks_obtained,max_marks,uploaded_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE marks_obtained=%s, max_marks=%s""",
            (r['student_id'], subject_id, semester, assessment_type,
             r['marks'], max_marks, fid, r['marks'], max_marks)
        )
    conn.commit()
    cursor.close()
    conn.close()
    return json_response({'message': f'Marks uploaded for {len(records)} students'})


@app.route('/api/faculty/leave', methods=['POST'])
@login_required('faculty')
def apply_leave():
    fid = session['profile_id']
    data = request.get_json()
    required = ['leave_type','from_date','to_date','days','reason']
    if not all(data.get(k) for k in required):
        return json_response({'error': 'All fields are required'}, 400)

    lid = query(
        """INSERT INTO leave_applications (faculty_id,leave_type,from_date,to_date,days,reason,substitute,contact)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (fid, data['leave_type'], data['from_date'], data['to_date'],
         data['days'], data['reason'], data.get('substitute',''), data.get('contact',''))
    )
    return json_response({'message': 'Leave application submitted', 'id': lid})


@app.route('/api/faculty/leave', methods=['GET'])
@login_required('faculty')
def get_leaves():
    fid = session['profile_id']
    leaves = query(
        "SELECT * FROM leave_applications WHERE faculty_id=%s ORDER BY applied_on DESC",
        (fid,)
    )
    return json_response(leaves)


@app.route('/api/faculty/notice', methods=['POST'])
@login_required('faculty')
def post_notice():
    fid = session['profile_id']
    data = request.get_json()
    if not data.get('title') or not data.get('body'):
        return json_response({'error': 'Title and body are required'}, 400)

    nid = query(
        "INSERT INTO notices (title,body,posted_by,audience,priority) VALUES (%s,%s,%s,%s,%s)",
        (data['title'], data['body'], fid,
         data.get('audience','all'), data.get('priority','normal'))
    )
    return json_response({'message': 'Notice posted', 'id': nid})


@app.route('/api/faculty/schedule', methods=['GET'])
@login_required('faculty')
def faculty_schedule():
    fid = session['profile_id']
    schedule = query(
        """SELECT s.name as subject, s.code, sa.section,
                  COUNT(cs.id) as total_classes,
                  SUM(CASE WHEN cs.status='completed' THEN 1 ELSE 0 END) as completed
           FROM subject_assignments sa
           JOIN subjects s ON sa.subject_id=s.id
           LEFT JOIN class_schedule cs ON cs.assignment_id=sa.id
           WHERE sa.faculty_id=%s AND sa.academic_year='2024-25'
           GROUP BY s.id, s.name, s.code, sa.section""",
        (fid,)
    )
    return json_response(schedule)


@app.route('/api/faculty/subjects', methods=['GET'])
@login_required('faculty')
def faculty_subjects():
    fid = session['profile_id']
    subs = query(
        """SELECT s.*, sa.section, sa.id as assignment_id
           FROM subject_assignments sa
           JOIN subjects s ON sa.subject_id=s.id
           WHERE sa.faculty_id=%s AND sa.academic_year='2024-25'""",
        (fid,)
    )
    return json_response(subs)

# ============================================================
#  SHARED ROUTES
# ============================================================

@app.route('/api/notices', methods=['GET'])
@login_required()
def all_notices():
    notices = query(
        """SELECT n.*, f.full_name as posted_by_name FROM notices n
           JOIN faculty f ON n.posted_by=f.id
           ORDER BY n.posted_at DESC LIMIT 20"""
    )
    return json_response(notices)


@app.route('/api/college/info', methods=['GET'])
def college_info():
    return json_response({
        'name': 'National Institute of Technology, Dādri',
        'established': 1985,
        'students': '6,400+',
        'naac_grade': 'A+',
        'nirf_rank': 38,
        'departments': 12,
        'address': 'Dādri, Uttar Pradesh, India',
        'about': 'Established in 1985, NIT Dādri is a premier autonomous technical institution offering undergraduate, postgraduate, and doctoral programs across 12 departments.'
    })

# ============================================================
#  ADMIN ROUTES
# ============================================================

# ── ADMIN LOGIN (separate from student/faculty) ──────────────
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data     = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    user = query("SELECT * FROM users WHERE username=%s AND role='admin'",
                 (username,), fetchone=True)
    if not user:
        return json_response({'error': 'Admin not found'}, 404)
    if not bcrypt.checkpw(password.encode(), user['password'].encode()):
        return json_response({'error': 'Invalid password'}, 401)

    query("UPDATE users SET last_login=NOW() WHERE id=%s", (user['id'],))
    session['user_id']  = user['id']
    session['role']     = 'admin'
    session['username'] = user['username']
    return json_response({'message': 'Admin login successful', 'username': user['username']})


# ── DASHBOARD STATS ──────────────────────────────────────────
@app.route('/api/admin/stats', methods=['GET'])
@login_required('admin')
def admin_stats():
    students  = query("SELECT COUNT(*) as c FROM students", fetchone=True)
    faculty   = query("SELECT COUNT(*) as c FROM faculty",  fetchone=True)
    subjects  = query("SELECT COUNT(*) as c FROM subjects", fetchone=True)
    notices   = query("SELECT COUNT(*) as c FROM notices",  fetchone=True)
    leaves    = query("SELECT COUNT(*) as c FROM leave_applications WHERE status='pending'", fetchone=True)
    fees_due  = query("SELECT COALESCE(SUM(amount_due-amount_paid),0) as total FROM fees WHERE status='due'", fetchone=True)
    recent_students = query(
        """SELECT s.full_name, s.roll_number, c.code as course, s.batch_year
           FROM students s JOIN courses c ON s.course_id=c.id
           ORDER BY s.id DESC LIMIT 5""")
    recent_leaves = query(
        """SELECT f.full_name, l.leave_type, l.from_date, l.to_date, l.status
           FROM leave_applications l JOIN faculty f ON l.faculty_id=f.id
           ORDER BY l.applied_on DESC LIMIT 5""")
    return json_response({
        'total_students':  students['c'],
        'total_faculty':   faculty['c'],
        'total_subjects':  subjects['c'],
        'total_notices':   notices['c'],
        'pending_leaves':  leaves['c'],
        'total_fees_due':  float(fees_due['total']),
        'recent_students': recent_students,
        'recent_leaves':   recent_leaves,
    })


# ── STUDENTS CRUD ────────────────────────────────────────────
@app.route('/api/admin/students', methods=['GET'])
@login_required('admin')
def admin_get_students():
    students = query(
        """SELECT s.*, c.name as course_name, c.code as course_code,
                  u.email, u.username
           FROM students s
           JOIN courses c ON s.course_id=c.id
           JOIN users u ON s.user_id=u.id
           ORDER BY s.roll_number""")
    return json_response(students)


@app.route('/api/admin/students', methods=['POST'])
@login_required('admin')
def admin_add_student():
    d = request.get_json()
    required = ['full_name','roll_number','enrollment_no','course_id','current_sem','batch_year','username','password','email']
    if not all(d.get(k) for k in required):
        return json_response({'error': 'All fields are required'}, 400)

    # Check duplicate
    existing = query("SELECT id FROM users WHERE username=%s OR email=%s",
                     (d['username'], d['email']), fetchone=True)
    if existing:
        return json_response({'error': 'Username or email already exists'}, 409)

    hashed = bcrypt.hashpw(d['password'].encode(), bcrypt.gensalt(12)).decode()
    uid = query("INSERT INTO users (username,password,role,email,phone) VALUES (%s,%s,'student',%s,%s)",
                (d['username'], hashed, d['email'], d.get('phone','')))
    query("""INSERT INTO students (user_id,full_name,roll_number,enrollment_no,course_id,
                                   current_sem,batch_year,dob,address,guardian_name,guardian_phone)
             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
          (uid, d['full_name'], d['roll_number'], d['enrollment_no'],
           d['course_id'], d['current_sem'], d['batch_year'],
           d.get('dob'), d.get('address',''), d.get('guardian_name',''), d.get('guardian_phone','')))
    return json_response({'message': f"Student {d['full_name']} added successfully"})


@app.route('/api/admin/students/<int:sid>', methods=['PUT'])
@login_required('admin')
def admin_update_student(sid):
    d = request.get_json()
    query("""UPDATE students SET full_name=%s, current_sem=%s, course_id=%s,
                                  guardian_name=%s, guardian_phone=%s, address=%s
             WHERE id=%s""",
          (d.get('full_name'), d.get('current_sem'), d.get('course_id'),
           d.get('guardian_name'), d.get('guardian_phone'), d.get('address'), sid))
    # update email/phone in users
    student = query("SELECT user_id FROM students WHERE id=%s", (sid,), fetchone=True)
    if student:
        query("UPDATE users SET email=%s, phone=%s WHERE id=%s",
              (d.get('email'), d.get('phone'), student['user_id']))
    return json_response({'message': 'Student updated successfully'})


@app.route('/api/admin/students/<int:sid>', methods=['DELETE'])
@login_required('admin')
def admin_delete_student(sid):
    student = query("SELECT user_id FROM students WHERE id=%s", (sid,), fetchone=True)
    if not student:
        return json_response({'error': 'Student not found'}, 404)
    query("DELETE FROM students WHERE id=%s", (sid,))
    query("DELETE FROM users WHERE id=%s", (student['user_id'],))
    return json_response({'message': 'Student deleted successfully'})


# ── FACULTY CRUD ─────────────────────────────────────────────
@app.route('/api/admin/faculty', methods=['GET'])
@login_required('admin')
def admin_get_faculty():
    faculty = query(
        """SELECT f.*, d.name as dept_name, u.email, u.username, u.phone
           FROM faculty f
           JOIN departments d ON f.department_id=d.id
           JOIN users u ON f.user_id=u.id
           ORDER BY f.full_name""")
    return json_response(faculty)


@app.route('/api/admin/faculty', methods=['POST'])
@login_required('admin')
def admin_add_faculty():
    d = request.get_json()
    required = ['full_name','employee_id','department_id','designation','username','password','email']
    if not all(d.get(k) for k in required):
        return json_response({'error': 'All fields are required'}, 400)

    existing = query("SELECT id FROM users WHERE username=%s OR email=%s",
                     (d['username'], d['email']), fetchone=True)
    if existing:
        return json_response({'error': 'Username or email already exists'}, 409)

    hashed = bcrypt.hashpw(d['password'].encode(), bcrypt.gensalt(12)).decode()
    uid = query("INSERT INTO users (username,password,role,email,phone) VALUES (%s,%s,'faculty',%s,%s)",
                (d['username'], hashed, d['email'], d.get('phone','')))
    query("""INSERT INTO faculty (user_id,full_name,employee_id,department_id,
                                   designation,qualification,specialization,joining_date)
             VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
          (uid, d['full_name'], d['employee_id'], d['department_id'],
           d['designation'], d.get('qualification',''), d.get('specialization',''),
           d.get('joining_date')))
    return json_response({'message': f"Faculty {d['full_name']} added successfully"})


@app.route('/api/admin/faculty/<int:fid>', methods=['PUT'])
@login_required('admin')
def admin_update_faculty(fid):
    d = request.get_json()
    query("""UPDATE faculty SET full_name=%s, department_id=%s, designation=%s,
                                 qualification=%s, specialization=%s
             WHERE id=%s""",
          (d.get('full_name'), d.get('department_id'), d.get('designation'),
           d.get('qualification'), d.get('specialization'), fid))
    fac = query("SELECT user_id FROM faculty WHERE id=%s", (fid,), fetchone=True)
    if fac:
        query("UPDATE users SET email=%s, phone=%s WHERE id=%s",
              (d.get('email'), d.get('phone'), fac['user_id']))
    return json_response({'message': 'Faculty updated successfully'})


@app.route('/api/admin/faculty/<int:fid>', methods=['DELETE'])
@login_required('admin')
def admin_delete_faculty(fid):
    fac = query("SELECT user_id FROM faculty WHERE id=%s", (fid,), fetchone=True)
    if not fac:
        return json_response({'error': 'Faculty not found'}, 404)
    query("DELETE FROM faculty WHERE id=%s", (fid,))
    query("DELETE FROM users WHERE id=%s", (fac['user_id'],))
    return json_response({'message': 'Faculty deleted successfully'})


# ── SUBJECTS CRUD ────────────────────────────────────────────
@app.route('/api/admin/subjects', methods=['GET'])
@login_required('admin')
def admin_get_subjects():
    subjects = query(
        """SELECT s.*, c.name as course_name FROM subjects s
           JOIN courses c ON s.course_id=c.id ORDER BY s.course_id, s.semester, s.code""")
    return json_response(subjects)


@app.route('/api/admin/subjects', methods=['POST'])
@login_required('admin')
def admin_add_subject():
    d = request.get_json()
    required = ['code','name','course_id','semester','credits','type']
    if not all(d.get(k) for k in required):
        return json_response({'error': 'All fields are required'}, 400)
    query("""INSERT INTO subjects (code,name,course_id,semester,credits,type,max_internal,max_external)
             VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
          (d['code'], d['name'], d['course_id'], d['semester'], d['credits'],
           d['type'], d.get('max_internal',30), d.get('max_external',70)))
    return json_response({'message': f"Subject {d['name']} added successfully"})


@app.route('/api/admin/subjects/<int:sid>', methods=['DELETE'])
@login_required('admin')
def admin_delete_subject(sid):
    query("DELETE FROM subjects WHERE id=%s", (sid,))
    return json_response({'message': 'Subject deleted'})


# ── SEMESTER RESULTS ─────────────────────────────────────────
@app.route('/api/admin/results', methods=['GET'])
@login_required('admin')
def admin_get_results():
    results = query(
        """SELECT r.*, s.full_name, s.roll_number
           FROM semester_results r JOIN students s ON r.student_id=s.id
           ORDER BY s.roll_number, r.semester""")
    return json_response(results)


@app.route('/api/admin/results', methods=['POST'])
@login_required('admin')
def admin_add_result():
    d = request.get_json()
    required = ['student_id','semester','sgpa','cgpa','credits_earned','status']
    if not all(str(d.get(k,'')) for k in required):
        return json_response({'error': 'All fields required'}, 400)
    query("""INSERT INTO semester_results (student_id,semester,sgpa,cgpa,credits_earned,status,declared_on)
             VALUES (%s,%s,%s,%s,%s,%s,%s)
             ON DUPLICATE KEY UPDATE sgpa=%s, cgpa=%s, credits_earned=%s, status=%s, declared_on=%s""",
          (d['student_id'], d['semester'], d['sgpa'], d['cgpa'], d['credits_earned'],
           d['status'], d.get('declared_on'), d['sgpa'], d['cgpa'],
           d['credits_earned'], d['status'], d.get('declared_on')))
    return json_response({'message': 'Result saved successfully'})


# ── FEE MANAGEMENT ───────────────────────────────────────────
@app.route('/api/admin/fees', methods=['GET'])
@login_required('admin')
def admin_get_fees():
    fees = query(
        """SELECT f.*, s.full_name, s.roll_number, fc.name as category_name
           FROM fees f JOIN students s ON f.student_id=s.id
           JOIN fee_categories fc ON f.category_id=fc.id
           ORDER BY f.status DESC, s.roll_number""")
    return json_response(fees)


@app.route('/api/admin/fees', methods=['POST'])
@login_required('admin')
def admin_add_fee():
    d = request.get_json()
    query("""INSERT INTO fees (student_id,category_id,semester,academic_year,amount_due,due_date,status)
             VALUES (%s,%s,%s,%s,%s,%s,'due')""",
          (d['student_id'], d['category_id'], d['semester'],
           d['academic_year'], d['amount_due'], d.get('due_date')))
    return json_response({'message': 'Fee record added'})


@app.route('/api/admin/fees/<int:fid>/pay', methods=['PUT'])
@login_required('admin')
def admin_mark_fee_paid(fid):
    d = request.get_json()
    query("""UPDATE fees SET amount_paid=%s, paid_date=%s, status='paid', transaction_id=%s
             WHERE id=%s""",
          (d.get('amount_paid'), d.get('paid_date', date.today().isoformat()),
           d.get('transaction_id',''), fid))
    return json_response({'message': 'Fee marked as paid'})


# ── LEAVE MANAGEMENT ─────────────────────────────────────────
@app.route('/api/admin/leaves', methods=['GET'])
@login_required('admin')
def admin_get_leaves():
    leaves = query(
        """SELECT l.*, f.full_name as faculty_name, f.employee_id
           FROM leave_applications l JOIN faculty f ON l.faculty_id=f.id
           ORDER BY l.applied_on DESC""")
    return json_response(leaves)


@app.route('/api/admin/leaves/<int:lid>', methods=['PUT'])
@login_required('admin')
def admin_review_leave(lid):
    d = request.get_json()
    status = d.get('status')
    if status not in ('approved', 'rejected'):
        return json_response({'error': 'Status must be approved or rejected'}, 400)
    query("""UPDATE leave_applications SET status=%s, reviewed_on=NOW()
             WHERE id=%s""", (status, lid))
    return json_response({'message': f'Leave {status} successfully'})


# ── DEPARTMENTS & COURSES (for dropdowns) ────────────────────
@app.route('/api/admin/departments', methods=['GET'])
@login_required('admin')
def admin_departments():
    return json_response(query("SELECT * FROM departments ORDER BY name"))


@app.route('/api/admin/courses', methods=['GET'])
@login_required('admin')
def admin_courses():
    return json_response(query(
        """SELECT c.*, d.name as dept_name FROM courses c
           JOIN departments d ON c.department_id=d.id ORDER BY c.name"""))


# ── RESET PASSWORD ───────────────────────────────────────────
@app.route('/api/admin/reset-password', methods=['POST'])
@login_required('admin')
def admin_reset_password():
    d = request.get_json()
    user_id  = d.get('user_id')
    new_pass = d.get('new_password','')
    if not user_id or len(new_pass) < 6:
        return json_response({'error': 'user_id and password (min 6 chars) required'}, 400)
    hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt(12)).decode()
    query("UPDATE users SET password=%s WHERE id=%s", (hashed, user_id))
    return json_response({'message': 'Password reset successfully'})


# ── ALL USERS LIST ───────────────────────────────────────────
@app.route('/api/admin/users', methods=['GET'])
@login_required('admin')
def admin_users():
    users = query(
        "SELECT id, username, role, email, phone, created_at, last_login FROM users ORDER BY role, username")
    return json_response(users)

# ============================================================

if __name__ == '__main__':
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
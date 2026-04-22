CREATE DATABASE IF NOT EXISTS edunexus;
USE edunexus;

-- ── DEPARTMENTS ──────────────────────────────────────────────
CREATE TABLE departments (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    code        VARCHAR(10)  NOT NULL UNIQUE,
    hod_name    VARCHAR(100),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── COURSES (degree programs) ────────────────────────────────
CREATE TABLE courses (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    code            VARCHAR(20)  NOT NULL UNIQUE,
    department_id   INT NOT NULL,
    total_semesters INT DEFAULT 8,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

-- ── USERS (shared auth table) ────────────────────────────────
CREATE TABLE users (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    username     VARCHAR(50)  NOT NULL UNIQUE,   -- enrollment / emp id
    password     VARCHAR(255) NOT NULL,           -- bcrypt hash
    role         ENUM('student','faculty','admin') NOT NULL,
    email        VARCHAR(100) UNIQUE,
    phone        VARCHAR(15),
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login   TIMESTAMP NULL
);

-- ── STUDENTS ─────────────────────────────────────────────────
CREATE TABLE students (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL UNIQUE,
    full_name       VARCHAR(100) NOT NULL,
    roll_number     VARCHAR(20)  NOT NULL UNIQUE,
    enrollment_no   VARCHAR(20)  NOT NULL UNIQUE,
    course_id       INT NOT NULL,
    current_sem     INT NOT NULL DEFAULT 1,
    batch_year      YEAR NOT NULL,
    dob             DATE,
    address         TEXT,
    guardian_name   VARCHAR(100),
    guardian_phone  VARCHAR(15),
    photo_url       VARCHAR(255),
    FOREIGN KEY (user_id)   REFERENCES users(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

-- ── FACULTY ──────────────────────────────────────────────────
CREATE TABLE faculty (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL UNIQUE,
    full_name       VARCHAR(100) NOT NULL,
    employee_id     VARCHAR(20)  NOT NULL UNIQUE,
    department_id   INT NOT NULL,
    designation     VARCHAR(100),
    qualification   VARCHAR(200),
    specialization  VARCHAR(200),
    joining_date    DATE,
    FOREIGN KEY (user_id)        REFERENCES users(id),
    FOREIGN KEY (department_id)  REFERENCES departments(id)
);

-- ── SUBJECTS ─────────────────────────────────────────────────
CREATE TABLE subjects (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    code          VARCHAR(20)  NOT NULL UNIQUE,
    name          VARCHAR(150) NOT NULL,
    course_id     INT NOT NULL,
    semester      INT NOT NULL,
    credits       INT NOT NULL DEFAULT 3,
    type          ENUM('theory','lab','elective','project') DEFAULT 'theory',
    max_internal  INT DEFAULT 30,
    max_external  INT DEFAULT 70,
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

-- ── SUBJECT ASSIGNMENTS (faculty → subject) ──────────────────
CREATE TABLE subject_assignments (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    faculty_id  INT NOT NULL,
    subject_id  INT NOT NULL,
    section     VARCHAR(10) DEFAULT 'A',
    academic_year VARCHAR(10) NOT NULL,   -- e.g. 2024-25
    UNIQUE KEY uq_assign (faculty_id, subject_id, section, academic_year),
    FOREIGN KEY (faculty_id)  REFERENCES faculty(id),
    FOREIGN KEY (subject_id)  REFERENCES subjects(id)
);

-- ── TIMETABLE ────────────────────────────────────────────────
CREATE TABLE timetable (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    assignment_id INT NOT NULL,
    day_of_week   ENUM('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday') NOT NULL,
    start_time    TIME NOT NULL,
    end_time      TIME NOT NULL,
    room          VARCHAR(20),
    FOREIGN KEY (assignment_id) REFERENCES subject_assignments(id)
);

-- ── ATTENDANCE ───────────────────────────────────────────────
CREATE TABLE attendance (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    student_id    INT NOT NULL,
    subject_id    INT NOT NULL,
    faculty_id    INT NOT NULL,
    date          DATE NOT NULL,
    status        ENUM('present','absent','late') NOT NULL,
    marked_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_att (student_id, subject_id, date),
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    FOREIGN KEY (faculty_id) REFERENCES faculty(id)
);

-- ── MARKS ────────────────────────────────────────────────────
CREATE TABLE marks (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    student_id      INT NOT NULL,
    subject_id      INT NOT NULL,
    semester        INT NOT NULL,
    assessment_type ENUM('internal1','internal2','midsem','assignment','external','practical') NOT NULL,
    marks_obtained  DECIMAL(5,2) NOT NULL,
    max_marks       DECIMAL(5,2) NOT NULL,
    uploaded_by     INT NOT NULL,   -- faculty user id
    uploaded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_marks (student_id, subject_id, assessment_type, semester),
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    FOREIGN KEY (uploaded_by) REFERENCES faculty(id)
);

-- ── SEMESTER RESULTS (final) ─────────────────────────────────
CREATE TABLE semester_results (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    student_id  INT NOT NULL,
    semester    INT NOT NULL,
    sgpa        DECIMAL(4,2),
    cgpa        DECIMAL(4,2),
    credits_earned INT,
    status      ENUM('passed','failed','detained','ongoing') DEFAULT 'ongoing',
    declared_on DATE,
    UNIQUE KEY uq_result (student_id, semester),
    FOREIGN KEY (student_id) REFERENCES students(id)
);

-- ── FEES ─────────────────────────────────────────────────────
CREATE TABLE fee_categories (
    id    INT AUTO_INCREMENT PRIMARY KEY,
    name  VARCHAR(100) NOT NULL,   -- Tuition, Hostel, Exam, etc.
    amount DECIMAL(10,2) NOT NULL
);

CREATE TABLE fees (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    student_id      INT NOT NULL,
    category_id     INT NOT NULL,
    semester        INT NOT NULL,
    academic_year   VARCHAR(10) NOT NULL,
    amount_due      DECIMAL(10,2) NOT NULL,
    amount_paid     DECIMAL(10,2) DEFAULT 0,
    due_date        DATE,
    paid_date       DATE,
    status          ENUM('paid','due','partial','waived') DEFAULT 'due',
    transaction_id  VARCHAR(100),
    FOREIGN KEY (student_id)  REFERENCES students(id),
    FOREIGN KEY (category_id) REFERENCES fee_categories(id)
);

-- ── NOTICES ──────────────────────────────────────────────────
CREATE TABLE notices (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    body        TEXT NOT NULL,
    posted_by   INT NOT NULL,   -- faculty id
    audience    ENUM('all','students','faculty','department','class') DEFAULT 'all',
    priority    ENUM('normal','important','urgent') DEFAULT 'normal',
    posted_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATE,
    FOREIGN KEY (posted_by) REFERENCES faculty(id)
);

-- ── LEAVE APPLICATIONS ───────────────────────────────────────
CREATE TABLE leave_applications (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    faculty_id      INT NOT NULL,
    leave_type      ENUM('casual','medical','earned','duty','maternity','paternity') NOT NULL,
    from_date       DATE NOT NULL,
    to_date         DATE NOT NULL,
    days            INT NOT NULL,
    reason          TEXT,
    substitute      VARCHAR(100),
    contact         VARCHAR(15),
    status          ENUM('pending','approved','rejected') DEFAULT 'pending',
    applied_on      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_by     INT,
    reviewed_on     TIMESTAMP NULL,
    FOREIGN KEY (faculty_id)  REFERENCES faculty(id)
);

-- ── MODULES (syllabus units) ─────────────────────────────────
CREATE TABLE modules (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    subject_id  INT NOT NULL,
    unit_no     INT NOT NULL,
    title       VARCHAR(200) NOT NULL,
    description TEXT,
    status      ENUM('pending','in_progress','completed') DEFAULT 'pending',
    FOREIGN KEY (subject_id) REFERENCES subjects(id)
);

-- ── CLASS SCHEDULE (lecture log) ─────────────────────────────
CREATE TABLE class_schedule (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    assignment_id INT NOT NULL,
    date          DATE NOT NULL,
    topic_covered TEXT,
    module_id     INT,
    status        ENUM('scheduled','completed','cancelled') DEFAULT 'scheduled',
    FOREIGN KEY (assignment_id) REFERENCES subject_assignments(id),
    FOREIGN KEY (module_id)     REFERENCES modules(id)
);

-- ============================================================
--  SEED DATA
-- ============================================================

INSERT INTO departments VALUES
(1,'Computer Science & Engineering','CSE','Dr. R.K. Sharma',NOW()),
(2,'Electronics & Communication','ECE','Dr. P. Mehta',NOW()),
(3,'Mechanical Engineering','ME','Dr. A. Singh',NOW());

INSERT INTO courses VALUES
(1,'B.Tech Computer Science','BTCS',1,8),
(2,'B.Tech Electronics','BTEC',2,8);

-- Passwords are bcrypt of "password123"
INSERT INTO users (username,password,role,email) VALUES
('2022CS001','$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMeSSXo5yWR/IlFuQ4pKVX2sPi','student','aarav@college.edu'),
('2022CS002','$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMeSSXo5yWR/IlFuQ4pKVX2sPi','student','priya@college.edu'),
('2022CS003','$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMeSSXo5yWR/IlFuQ4pKVX2sPi','student','rohan@college.edu'),
('FAC001','$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMeSSXo5yWR/IlFuQ4pKVX2sPi','faculty','sharma@college.edu'),
('FAC002','$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMeSSXo5yWR/IlFuQ4pKVX2sPi','faculty','mehta@college.edu');

INSERT INTO students (user_id,full_name,roll_number,enrollment_no,course_id,current_sem,batch_year,dob) VALUES
(1,'Aarav Sharma','CS22001','2022CS001',1,6,2022,'2003-05-12'),
(2,'Priya Mehta','CS22002','2022CS002',1,6,2022,'2003-08-23'),
(3,'Rohan Verma','CS22003','2022CS003',1,6,2022,'2003-11-01');

INSERT INTO faculty (user_id,full_name,employee_id,department_id,designation,joining_date) VALUES
(4,'Dr. Priya Sharma','FAC001',1,'Assistant Professor','2018-07-01'),
(5,'Prof. Rajesh Mehta','FAC002',1,'Associate Professor','2015-01-10');

INSERT INTO subjects (code,name,course_id,semester,credits,type,max_internal,max_external) VALUES
('CS601','Compiler Design',1,6,4,'theory',30,70),
('CS602','Distributed Systems',1,6,3,'theory',30,70),
('CS603','Machine Learning',1,6,4,'elective',30,70),
('CS604','Cloud Computing',1,6,3,'elective',30,70),
('CS605','ML Lab',1,6,2,'lab',50,50),
('CS606','Major Project',1,6,6,'project',100,0),
('CS501','Data Structures',1,5,4,'theory',30,70),
('CS502','Operating Systems',1,5,3,'theory',30,70),
('CS503','Computer Networks',1,5,3,'theory',30,70),
('CS504','Software Engineering',1,5,3,'theory',30,70),
('CS505','DBMS Lab',1,5,2,'lab',50,50),
('CS506','Mini Project',1,5,2,'project',100,0);

INSERT INTO subject_assignments (faculty_id,subject_id,section,academic_year) VALUES
(1,1,'A','2024-25'),(1,3,'A','2024-25'),(1,5,'B','2024-25'),(1,6,'A','2024-25'),
(2,2,'A','2024-25'),(2,4,'A','2024-25');

INSERT INTO fee_categories (name,amount) VALUES
('Tuition Fee',45000),('Hostel Fee',28000),('Lab & Exam Fee',5500),('Alumni Fee',1000);

INSERT INTO fees (student_id,category_id,semester,academic_year,amount_due,amount_paid,due_date,paid_date,status,transaction_id) VALUES
(1,1,6,'2024-25',45000,45000,'2024-07-31','2024-07-12','paid','TXN20240712001'),
(1,2,6,'2024-25',28000,28000,'2024-07-01','2024-07-01','paid','TXN20240701002'),
(1,3,6,'2024-25',5500,5500,'2024-07-31','2024-07-12','paid','TXN20240712003'),
(1,4,6,'2024-25',1000,0,'2025-11-30',NULL,'due',NULL);

INSERT INTO semester_results (student_id,semester,sgpa,cgpa,credits_earned,status,declared_on) VALUES
(1,1,8.2,8.2,22,'passed','2022-12-15'),
(1,2,8.5,8.35,24,'passed','2023-06-20'),
(1,3,9.1,8.6,22,'passed','2023-12-18'),
(1,4,8.4,8.55,24,'passed','2024-06-22'),
(1,5,8.8,8.6,22,'passed','2024-12-10'),
(1,6,NULL,NULL,0,'ongoing',NULL);

INSERT INTO marks (student_id,subject_id,semester,assessment_type,marks_obtained,max_marks,uploaded_by) VALUES
(1,7,5,'internal1',26,30,1),(1,7,5,'internal2',25,30,1),(1,7,5,'external',62,70,1),
(1,8,5,'internal1',24,30,1),(1,8,5,'internal2',22,30,1),(1,8,5,'external',58,70,1),
(1,9,5,'internal1',25,30,2),(1,9,5,'internal2',23,30,2),(1,9,5,'external',55,70,2),
(1,10,5,'internal1',22,30,2),(1,10,5,'internal2',20,30,2),(1,10,5,'external',52,70,2);

INSERT INTO notices (title,body,posted_by,audience,priority) VALUES
('End Semester Exam Schedule Released','Exams commence 15 Nov 2025. Hall tickets available on the portal from 1 Nov. Students must carry valid ID.',1,'all','urgent'),
('Campus Placement Drive — TCS & Infosys','Register before Nov 3rd. Eligible: 7.0+ CGPA, no active backlogs. Venue: Seminar Hall A.',1,'students','important'),
('Library Timings Extended','Library will remain open till 10 PM from Nov 1 to support exam preparation.',2,'all','normal');

INSERT INTO modules (subject_id,unit_no,title,description,status) VALUES
(1,1,'Introduction to Compilers','Phases of compilation, symbol table, error handling','completed'),
(1,2,'Lexical Analysis','Regular expressions, DFA, NFA, lex tool','completed'),
(1,3,'Syntax Analysis','CFG, top-down & bottom-up parsing','completed'),
(1,4,'Semantic Analysis','Type checking, attribute grammars','in_progress'),
(1,5,'Code Generation & Optimization','Intermediate code, DAG, peephole optimization','pending');

INSERT INTO attendance (student_id,subject_id,faculty_id,date,status) VALUES
(1,1,1,'2024-10-28','present'),(1,1,1,'2024-10-29','present'),(1,1,1,'2024-10-30','absent'),
(1,3,1,'2024-10-28','present'),(1,3,1,'2024-10-29','present'),(1,3,1,'2024-10-30','present');
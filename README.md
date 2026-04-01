# EduNexus LMS — Setup Guide

## Project Structure
```
lms/
├── backend/
│   ├── app.py              ← Flask server (all API routes)
│   ├── requirements.txt    ← Python dependencies
│   └── .env                ← Your DB credentials (edit this!)
├── frontend/
│   ├── templates/
│   │   └── index.html      ← Main HTML (served by Flask)
│   └── static/
│       ├── css/style.css
│       └── js/app.js
└── database/
    └── schema.sql          ← Run this first in MySQL
```

---

## Step 1 — Set Up the Database

Open your terminal and run:

```bash
mysql -u root -p < database/schema.sql
```

This creates the `edunexus` database with all tables and demo data.

---

## Step 2 — Configure Your DB Password

Edit `backend/.env` and set your MySQL root password:

```
DB_PASSWORD=your_actual_mysql_password
```

---

## Step 3 — Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

---

## Step 4 — Run the Flask Server

```bash
cd backend
python app.py
```

You should see:
```
🚀 EduNexus LMS Backend starting on http://localhost:5000
```

---

## Step 5 — Open in Browser

Visit: **http://localhost:5000**

---

## Demo Login Credentials

| Role    | Username   | Password    |
|---------|------------|-------------|
| Student | 2022CS001  | password123 |
| Student | 2022CS002  | password123 |
| Faculty | FAC001     | password123 |
| Faculty | FAC002     | password123 |

---

## API Endpoints Summary

### Auth
| Method | Endpoint      | Description       |
|--------|--------------|-------------------|
| POST   | /api/login   | Login             |
| POST   | /api/logout  | Logout            |
| GET    | /api/me      | Current user info |

### Student
| Method | Endpoint                      | Description      |
|--------|------------------------------|------------------|
| GET    | /api/student/dashboard       | Dashboard stats  |
| GET    | /api/student/cgpa            | CGPA history     |
| GET    | /api/student/report-card     | Marks            |
| GET    | /api/student/attendance      | Attendance %     |
| GET    | /api/student/timetable       | Weekly schedule  |
| GET    | /api/student/subjects        | Enrolled subjects|
| GET    | /api/student/modules         | Course modules   |
| GET    | /api/student/fees            | Fee details      |
| GET    | /api/student/notices         | Notices          |

### Faculty
| Method | Endpoint                    | Description         |
|--------|-----------------------------|---------------------|
| GET    | /api/faculty/dashboard      | Dashboard stats     |
| GET    | /api/faculty/timetable      | Teaching schedule   |
| GET    | /api/faculty/students       | Student list        |
| POST   | /api/faculty/attendance     | Mark attendance     |
| POST   | /api/faculty/marks          | Upload marks        |
| GET    | /api/faculty/leave          | Leave history       |
| POST   | /api/faculty/leave          | Apply for leave     |
| POST   | /api/faculty/notice         | Post notice         |
| GET    | /api/faculty/schedule       | Syllabus progress   |
| GET    | /api/faculty/subjects       | Teaching subjects   |

---

## Troubleshooting

**MySQL connection error?**
- Make sure MySQL is running: `mysql -u root -p`
- Check your password in `backend/.env`

**Module not found?**
- Run: `pip install -r requirements.txt`

**Port 5000 already in use?**
- Change port at bottom of `app.py`: `app.run(port=5001)`

// ============================================================
//  EduNexus LMS  ·  app.js
//  All API calls go to Flask backend at /api/...
// ============================================================

const API = '';   // same origin — Flask serves both frontend & API
let currentRole  = 'student';
let currentUser  = null;
let attState     = {};   // {index: 'present'|'absent'}
let subjectsList = [];   // cached subjects for faculty

// ── UTILS ────────────────────────────────────────────────────
async function api(path, options = {}) {
  const res = await fetch(API + path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

function showToast(msg, isError = false) {
  const t = document.getElementById('toast');
  t.textContent = (isError ? '✗ ' : '✓ ') + msg;
  t.className = 'toast show' + (isError ? ' error' : '');
  setTimeout(() => t.className = 'toast', 3000);
}

function loading(show) {
  document.getElementById('loading-overlay').style.display = show ? 'flex' : 'none';
}

function fmt(time) {
  // "09:00:00" → "9:00 AM"
  if (!time) return '';
  const [h, m] = time.split(':');
  const hr = parseInt(h);
  return `${hr > 12 ? hr - 12 : hr || 12}:${m} ${hr >= 12 ? 'PM' : 'AM'}`;
}

function fmtDate(str) {
  if (!str) return '—';
  return new Date(str).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function timeAgo(str) {
  if (!str) return '';
  const diff = Date.now() - new Date(str).getTime();
  const d = Math.floor(diff / 86400000);
  return d === 0 ? 'Today' : d === 1 ? 'Yesterday' : `${d} days ago`;
}

// ── NAVIGATION ───────────────────────────────────────────────
function showLogin(role) {
  currentRole = role;
  document.getElementById('landing').style.display = 'none';
  const l = document.getElementById('login');
  l.classList.add('visible');
  document.getElementById('login-title').textContent = role === 'student' ? 'Student Login' : 'Faculty Login';
  document.getElementById('login-sub').textContent = role === 'student'
    ? 'Enter your enrollment ID and password'
    : 'Enter your employee ID and password';
  const btn = document.getElementById('login-btn');
  btn.className = 'login-submit ' + role;
  document.getElementById('login-error').style.display = 'none';
}

function showLanding() {
  document.getElementById('login').classList.remove('visible');
  document.getElementById('landing').style.display = 'flex';
}

async function doLogin() {
  const username = document.getElementById('login-id').value.trim();
  const password = document.getElementById('login-pass').value.trim();
  const errEl    = document.getElementById('login-error');
  const btn      = document.getElementById('login-btn');

  if (!username || !password) {
    errEl.textContent = 'Please enter your ID and password.';
    errEl.style.display = 'block';
    return;
  }
  btn.disabled = true;
  btn.textContent = 'Logging in…';
  errEl.style.display = 'none';

  try {
    const data = await api('/api/login', {
      method: 'POST',
      body: JSON.stringify({ username, password, role: currentRole })
    });
    currentUser = data.profile;
    setupDashboard(currentRole, data.profile);
    document.getElementById('login').classList.remove('visible');
    document.getElementById('dashboard').classList.add('visible');
  } catch (err) {
    errEl.textContent = err.message;
    errEl.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Login →';
  }
}

async function doLogout() {
  await api('/api/logout', { method: 'POST' });
  currentUser = null;
  document.getElementById('dashboard').classList.remove('visible');
  document.getElementById('landing').style.display = 'flex';
  document.getElementById('login-id').value = '';
  document.getElementById('login-pass').value = '';
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
}

// ── DASHBOARD SETUP ──────────────────────────────────────────
function setupDashboard(role, profile) {
  document.getElementById('student-nav').style.display = role === 'student' ? 'block' : 'none';
  document.getElementById('faculty-nav').style.display = role === 'faculty' ? 'block' : 'none';

  const name = profile.full_name || 'User';
  document.getElementById('user-name').textContent = name;
  document.getElementById('user-avatar').textContent = name[0].toUpperCase();
  document.getElementById('user-avatar').style.background = role === 'student' ? 'var(--accent)' : 'var(--accent3)';

  if (role === 'student') {
    document.getElementById('user-role').textContent = `${profile.course_code} · Sem ${profile.current_sem}`;
    loadPanel('s-home', document.querySelector('#student-nav .nav-item'));
  } else {
    document.getElementById('user-role').textContent = profile.designation || 'Faculty';
    loadPanel('f-home', document.querySelector('#faculty-nav .nav-item'));
  }

  document.getElementById('curr-date').textContent = new Date().toLocaleDateString('en-IN', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
  });
}

// ── PANEL LOADER ─────────────────────────────────────────────
const panelTitles = {
  's-home': 'Dashboard', 's-cgpa': 'CGPA & Results', 's-report': 'Report Card',
  's-att': 'Attendance', 's-tt': 'Timetable', 's-sub': 'Subjects',
  's-modules': 'Modules', 's-fees': 'Fee Details', 's-about': 'About College', 's-notices': 'Notices',
  'f-home': 'Faculty Dashboard', 'f-tt': 'My Timetable', 'f-att': 'Mark Attendance',
  'f-leave': 'Apply Leave', 'f-marks': 'Upload Marks', 'f-notices': 'Post Notice',
  'f-students': 'My Students', 'f-schedule': 'Class Schedule'
};

const panelBuilders = {
  's-home': buildStudentHome, 's-cgpa': buildCgpa, 's-report': buildReport,
  's-att': buildStudentAtt, 's-tt': buildStudentTT, 's-sub': buildSubjects,
  's-modules': buildModules, 's-fees': buildFees, 's-about': buildAbout, 's-notices': buildStudentNotices,
  'f-home': buildFacultyHome, 'f-tt': buildFacultyTT, 'f-att': buildMarkAtt,
  'f-leave': buildLeave, 'f-marks': buildMarks, 'f-notices': buildFacultyNotices,
  'f-students': buildStudentsPanel, 'f-schedule': buildSchedule
};

async function loadPanel(panelId, navEl) {
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active', 'fac-active'));
  if (navEl) { navEl.classList.add('active'); if (currentRole === 'faculty') navEl.classList.add('fac'); }
  document.getElementById('panel-title').textContent = panelTitles[panelId] || '';
  document.getElementById('sidebar').classList.remove('open');

  const content = document.getElementById('panel-content');
  content.innerHTML = '<div class="empty">Loading…</div>';

  try {
    const html = await panelBuilders[panelId]();
    content.innerHTML = html;
    content.classList.add('fade-up');
    setTimeout(() => content.classList.remove('fade-up'), 400);
    // Post-render hooks
    if (panelId === 's-cgpa') renderCgpaChart(window._cgpaData);
    if (panelId === 'f-att') renderAttStudents(window._attStudents);
    if (panelId === 'f-marks') renderMarksTable(window._marksStudents);
  } catch (err) {
    content.innerHTML = `<div class="empty">⚠ ${err.message}</div>`;
  }
}

// ── STUDENT PANELS ───────────────────────────────────────────

async function buildStudentHome() {
  const d = await api('/api/student/dashboard');
  const classes = d.todays_classes.map(c => `
    <div class="class-item" style="border-left:3px solid var(--accent)">
      <div class="class-info">
        <div class="cname">${c.subject}</div>
        <div class="cmeta">${fmt(c.start_time)} · Room ${c.room} · ${c.faculty_name}</div>
      </div>
    </div>`).join('') || '<div class="empty">No classes today 🎉</div>';

  const notices = d.notices.slice(0,3).map(n => `
    <div class="notice-item">
      <div class="notice-dot" style="background:${n.priority==='urgent'?'var(--red)':n.priority==='important'?'var(--yellow)':'var(--accent)'}"></div>
      <div><h4>${n.title}</h4><p>${n.body.substring(0,100)}…</p>
      <div class="ndate">${timeAgo(n.posted_at)}</div></div>
    </div>`).join('');

  return `
    <div class="stats-row">
      <div class="stat-card blue"><div class="stat-label">CGPA</div><div class="stat-value">${d.cgpa||'—'}</div><div class="stat-sub">Sem ${d.current_sem}</div></div>
      <div class="stat-card green"><div class="stat-label">Attendance</div><div class="stat-value">${d.attendance_pct}%</div><div class="stat-sub">This semester</div></div>
      <div class="stat-card purple"><div class="stat-label">Semester</div><div class="stat-value">${d.current_sem}</div></div>
      <div class="stat-card ${d.fee_due>0?'yellow':'cyan'}"><div class="stat-label">Fee Due</div><div class="stat-value">₹${d.fee_due.toLocaleString('en-IN')}</div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;flex-wrap:wrap">
      <div class="section-card"><div class="section-head"><h3>Today's Classes</h3></div>
        <div style="padding:1.2rem;display:flex;flex-direction:column;gap:.7rem">${classes}</div></div>
      <div class="section-card"><div class="section-head"><h3>Recent Notices</h3></div>
        <div class="notice-list">${notices}</div></div>
    </div>`;
}

async function buildCgpa() {
  const results = await api('/api/student/cgpa');
  window._cgpaData = results;
  const rows = results.map(r => `
    <tr><td>Semester ${r.semester}</td><td>${r.sgpa||'—'}</td><td>${r.credits_earned||0}</td>
    <td><span class="badge ${r.status==='passed'?'green':r.status==='ongoing'?'blue':'red'}">${r.status}</span></td>
    <td>${r.cgpa||'—'}</td></tr>`).join('');

  const current = results.filter(r => r.cgpa).pop();
  return `
    <div class="stats-row">
      <div class="stat-card blue"><div class="stat-label">Overall CGPA</div><div class="stat-value">${current?.cgpa||'—'}</div></div>
      <div class="stat-card green"><div class="stat-label">Best SGPA</div><div class="stat-value">${Math.max(...results.map(r=>r.sgpa||0)).toFixed(1)}</div></div>
      <div class="stat-card purple"><div class="stat-label">Credits Earned</div><div class="stat-value">${results.reduce((a,r)=>a+(r.credits_earned||0),0)}</div></div>
    </div>
    <div class="section-card">
      <div class="section-head"><h3>CGPA Trend</h3></div>
      <div class="cgpa-chart" id="cgpa-chart"></div>
    </div>
    <div class="section-card">
      <div class="section-head"><h3>Semester-wise Performance</h3></div>
      <table><thead><tr><th>Semester</th><th>SGPA</th><th>Credits</th><th>Status</th><th>CGPA</th></tr></thead>
      <tbody>${rows}</tbody></table>
    </div>`;
}

function renderCgpaChart(results) {
  const c = document.getElementById('cgpa-chart');
  if (!c || !results) return;
  const colors = ['var(--accent)','var(--accent2)','var(--accent3)','var(--green)','var(--yellow)','var(--accent)'];
  const max = 10; const h = 120;
  c.innerHTML = results.map((r, i) => {
    const v = r.sgpa || 0;
    return `<div class="cgpa-bar-wrap">
      <div class="cgpa-val" style="color:${colors[i%6]}">${v||'—'}</div>
      <div class="cgpa-bar" style="height:${(v/max)*h}px;background:${colors[i%6]}"></div>
      <div class="cgpa-label">S${r.semester}</div>
    </div>`;
  }).join('');
}

async function buildReport() {
  const data = await api('/api/student/report-card?semester=5');
  const rows = data.marks.map(m => {
    const total = (m.internal||0) + (m.external||0);
    const grade = total >= 90 ? 'A+' : total >= 80 ? 'A' : total >= 70 ? 'B+' : total >= 60 ? 'B' : 'C';
    const cls = total >= 80 ? 'green' : total >= 60 ? 'yellow' : 'red';
    return `<tr><td>${m.name}</td><td>${m.internal||'—'}</td><td>${m.external||'—'}</td>
      <td>${total||'—'}</td><td><span class="badge ${cls}">${grade}</span></td><td>${m.credits}</td></tr>`;
  }).join('') || '<tr><td colspan="6" style="text-align:center;color:var(--muted)">No marks found</td></tr>';

  return `
    <div class="section-card">
      <div class="section-head"><h3>Report Card — Semester 5</h3>
        ${data.result ? `<span class="badge green">SGPA: ${data.result.sgpa}</span>` : ''}
      </div>
      <table><thead><tr><th>Subject</th><th>Internal (30)</th><th>External (70)</th><th>Total</th><th>Grade</th><th>Credits</th></tr></thead>
      <tbody>${rows}</tbody></table>
    </div>`;
}

async function buildStudentAtt() {
  const att = await api('/api/student/attendance');
  const total_present = att.reduce((a,s)=>a+(s.present||0),0);
  const total_classes = att.reduce((a,s)=>a+(s.total||0),0);
  const pct = total_classes ? Math.round(total_present/total_classes*100) : 0;

  const rows = att.map(s => {
    const p = parseFloat(s.percentage)||0;
    const cls = p >= 75 ? 'ok' : p >= 60 ? 'warn' : 'low';
    return `<div class="att-item ${cls}">
      <div class="att-top"><span>${s.name} <small style="color:var(--muted)">(${s.code})</small></span><span class="att-pct">${p}%</span></div>
      <div class="prog-bar"><div class="prog-fill" style="width:${p}%"></div></div>
    </div>`;
  }).join('') || '<div class="empty">No attendance data yet</div>';

  return `
    <div class="stats-row">
      <div class="stat-card green"><div class="stat-label">Overall</div><div class="stat-value">${pct}%</div></div>
      <div class="stat-card blue"><div class="stat-label">Classes Attended</div><div class="stat-value">${total_present}</div></div>
      <div class="stat-card red"><div class="stat-label">Classes Missed</div><div class="stat-value">${total_classes-total_present}</div></div>
    </div>
    <div class="section-card">
      <div class="section-head"><h3>Subject-wise Attendance</h3></div>
      <div class="att-list">${rows}</div>
    </div>`;
}

async function buildStudentTT() {
  const tt = await api('/api/student/timetable');
  return `
    <div class="section-card">
      <div class="section-head"><h3>Weekly Timetable</h3></div>
      <div style="padding:1.2rem;overflow-x:auto">${renderTimetable(tt, 'student')}</div>
    </div>`;
}

async function buildSubjects() {
  const subs = await api('/api/student/subjects');
  const rows = subs.map(s => `
    <tr><td>${s.code}</td><td>${s.name}</td><td>${s.faculty_name||'—'}</td><td>${s.credits}</td>
    <td><span class="badge ${s.type==='lab'?'yellow':s.type==='elective'?'purple':s.type==='project'?'green':'blue'}">${s.type}</span></td></tr>`
  ).join('') || '<tr><td colspan="5" style="text-align:center;color:var(--muted)">No subjects found</td></tr>';

  return `
    <div class="section-card">
      <div class="section-head"><h3>Enrolled Subjects</h3></div>
      <table><thead><tr><th>Code</th><th>Subject</th><th>Faculty</th><th>Credits</th><th>Type</th></tr></thead>
      <tbody>${rows}</tbody></table>
    </div>`;
}

async function buildModules() {
  const mods = await api('/api/student/modules');
  const grouped = {};
  mods.forEach(m => {
    if (!grouped[m.subject_code]) grouped[m.subject_code] = { name: m.subject_name, items: [] };
    grouped[m.subject_code].items.push(m);
  });

  const cards = Object.entries(grouped).map(([code, sub]) => {
    const total = sub.items.length;
    const done  = sub.items.filter(m => m.status === 'completed').length;
    return `<div class="mod-card">
      <h4>📘 ${sub.name}</h4>
      <p>${sub.items.map(m => `Unit ${m.unit_no}: ${m.title}`).join(' · ')}</p>
      <div class="mod-footer">
        <span class="badge blue">${total} Units</span>
        <span style="font-size:.78rem;color:${done===total?'var(--green)':'var(--yellow)'}">✓ ${done}/${total} done</span>
      </div>
    </div>`;
  }).join('') || '<div class="empty">No modules found</div>';

  return `<div class="section-card"><div class="section-head"><h3>Course Modules</h3></div>
    <div class="module-grid">${cards}</div></div>`;
}

async function buildFees() {
  const fees = await api('/api/student/fees');
  const cards = fees.map(f => {
    const statusCls = f.status === 'paid' ? 'paid' : f.status === 'due' ? 'due' : 'partial';
    const badge = f.status === 'paid' ? 'green' : f.status === 'due' ? 'red' : 'yellow';
    return `<div class="fee-card ${statusCls}">
      <div style="font-size:.72rem;color:var(--muted)">${(f.category_name||'').toUpperCase()} · SEM ${f.semester}</div>
      <div class="amt">₹${parseFloat(f.amount_due).toLocaleString('en-IN')}</div>
      <span class="badge ${badge}">${f.status === 'paid' ? `Paid — ${fmtDate(f.paid_date)}` : `Due — ${fmtDate(f.due_date)}`}</span>
    </div>`;
  }).join('') || '<div class="empty">No fee records found</div>';

  return `<div class="section-card"><div class="section-head"><h3>Fee Details</h3></div>
    <div class="fees-grid">${cards}</div></div>`;
}

async function buildAbout() {
  const info = await api('/api/college/info');
  return `
    <div class="section-card">
      <div class="section-head"><h3>About the College</h3></div>
      <div style="padding:1.5rem;line-height:1.9;color:var(--muted);font-size:.9rem">
        <h4 style="color:var(--text);font-family:var(--font-head);font-size:1.2rem;margin-bottom:.5rem">🏛️ ${info.name}</h4>
        <p style="margin-bottom:1rem">${info.about}</p>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.8rem;margin-top:1rem">
          ${Object.entries({Established:info.established,'Total Students':info.students,'NAAC Grade':info.naac_grade,'NIRF Rank':'#'+info.nirf_rank,Departments:info.departments}).map(([k,v])=>`
          <div style="background:var(--surface);border-radius:10px;padding:1rem">
            <div style="font-size:.72rem;color:var(--muted);margin-bottom:.3rem">${k.toUpperCase()}</div>
            <div style="font-weight:600">${v}</div>
          </div>`).join('')}
        </div>
      </div>
    </div>`;
}

async function buildStudentNotices() {
  const notices = await api('/api/student/notices');
  const items = notices.map(n => `
    <div class="notice-item">
      <div class="notice-dot" style="background:${n.priority==='urgent'?'var(--red)':n.priority==='important'?'var(--yellow)':'var(--accent)'}"></div>
      <div><h4>${n.title}</h4><p>${n.body}</p>
        <div class="ndate">${fmtDate(n.posted_at)} · ${n.posted_by_name}</div>
      </div>
    </div>`).join('') || '<div class="empty">No notices</div>';

  return `<div class="section-card"><div class="section-head"><h3>College Notices</h3>
    <span class="badge blue">${notices.length} Active</span></div>
    <div class="notice-list">${items}</div></div>`;
}

// ── FACULTY PANELS ───────────────────────────────────────────

async function buildFacultyHome() {
  const d = await api('/api/faculty/dashboard');
  const sched = d.schedule.map(c => `
    <div class="class-item" style="border-left:3px solid var(--accent3)">
      <div class="class-info">
        <div class="cname">${c.subject}</div>
        <div class="cmeta">${fmt(c.start_time)} – ${fmt(c.end_time)} · Room ${c.room} · Section ${c.section}</div>
      </div>
    </div>`).join('') || '<div class="empty">No classes today 🎉</div>';

  const actions = [
    ['f-att','✅','Mark Attendance'],['f-leave','🏖️','Apply Leave'],
    ['f-marks','📝','Upload Marks'],['f-notices','📢','Post Notice']
  ].map(([panel,icon,label]) =>
    `<div class="quick-btn" onclick="loadPanel('${panel}',null)"><div class="qi">${icon}</div><div class="ql">${label}</div></div>`
  ).join('');

  return `
    <div class="stats-row">
      <div class="stat-card purple"><div class="stat-label">My Courses</div><div class="stat-value">${d.total_courses}</div></div>
      <div class="stat-card blue"><div class="stat-label">Total Students</div><div class="stat-value">${d.total_students}</div></div>
      <div class="stat-card green"><div class="stat-label">Classes Today</div><div class="stat-value">${d.todays_classes}</div></div>
      <div class="stat-card yellow"><div class="stat-label">Leave Remaining</div><div class="stat-value">${d.casual_leave_remaining}</div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
      <div class="section-card"><div class="section-head"><h3>Today's Schedule</h3></div>
        <div style="padding:1.2rem;display:flex;flex-direction:column;gap:.7rem">${sched}</div></div>
      <div class="section-card"><div class="section-head"><h3>Quick Actions</h3></div>
        <div class="quick-grid">${actions}</div></div>
    </div>`;
}

async function buildFacultyTT() {
  const tt = await api('/api/faculty/timetable');
  return `
    <div class="section-card">
      <div class="section-head"><h3>My Teaching Timetable</h3></div>
      <div style="padding:1.2rem;overflow-x:auto">${renderTimetable(tt, 'faculty')}</div>
    </div>`;
}

async function buildMarkAtt() {
  const subs = await api('/api/faculty/subjects');
  subjectsList = subs;
  const students = await api('/api/faculty/students');
  window._attStudents = students;

  const subOpts = subs.map(s => `<option value="${s.id}">${s.name} (${s.code})</option>`).join('');

  return `
    <div class="section-card">
      <div class="section-head"><h3>Mark Attendance</h3></div>
      <div class="form-grid" style="padding-bottom:0">
        <div class="form-field">
          <label>SUBJECT</label>
          <select id="att-subject">${subOpts}</select>
        </div>
        <div class="form-field">
          <label>DATE</label>
          <input type="date" id="att-date" value="${new Date().toISOString().slice(0,10)}"/>
        </div>
      </div>
      <div class="student-list" id="att-student-list"></div>
      <div style="padding:0 1.4rem 1.4rem;display:flex;gap:1rem;flex-wrap:wrap">
        <button onclick="markAll('present')" style="padding:.7rem 1.5rem;background:var(--green);color:#fff;border:none;border-radius:8px;cursor:pointer;font-family:var(--font-body)">✓ All Present</button>
        <button onclick="markAll('absent')" style="padding:.7rem 1.5rem;background:var(--red);color:#fff;border:none;border-radius:8px;cursor:pointer;font-family:var(--font-body)">✗ All Absent</button>
        <button onclick="saveAttendance()" style="padding:.7rem 1.5rem;background:var(--accent3);color:#fff;border:none;border-radius:8px;cursor:pointer;font-family:var(--font-head);font-weight:700;margin-left:auto">Save Attendance</button>
      </div>
    </div>`;
}

function renderAttStudents(students) {
  const list = document.getElementById('att-student-list');
  if (!list) return;
  attState = {};
  list.innerHTML = students.map((s, i) => `
    <div class="student-row">
      <div><div class="sname">${s.full_name}</div><div class="sroll">${s.roll_number}</div></div>
      <div class="att-toggle">
        <button id="p-${i}" onclick="toggleAtt(${i},'present',${s.id})">Present</button>
        <button id="a-${i}" onclick="toggleAtt(${i},'absent',${s.id})">Absent</button>
      </div>
    </div>`).join('') || '<div class="empty">No students found</div>';
}

function toggleAtt(i, status, student_id) {
  document.getElementById(`p-${i}`).className = status === 'present' ? 'present' : '';
  document.getElementById(`a-${i}`).className = status === 'absent' ? 'absent' : '';
  attState[student_id] = status;
}

function markAll(status) {
  (window._attStudents || []).forEach((s, i) => toggleAtt(i, status, s.id));
}

async function saveAttendance() {
  const subject_id = document.getElementById('att-subject')?.value;
  const date       = document.getElementById('att-date')?.value;
  const records    = Object.entries(attState).map(([student_id, status]) => ({ student_id: parseInt(student_id), status }));

  if (!records.length) { showToast('Mark at least one student', true); return; }

  try {
    const res = await api('/api/faculty/attendance', {
      method: 'POST',
      body: JSON.stringify({ subject_id: parseInt(subject_id), date, records })
    });
    showToast(res.message);
  } catch (err) {
    showToast(err.message, true);
  }
}

async function buildLeave() {
  const leaves = await api('/api/faculty/leave');
  const hist = leaves.map(l => `
    <tr><td>${l.leave_type}</td><td>${fmtDate(l.from_date)}</td><td>${fmtDate(l.to_date)}</td>
    <td>${l.days}</td><td>${l.reason?.substring(0,40)}…</td>
    <td><span class="badge ${l.status==='approved'?'green':l.status==='rejected'?'red':'yellow'}">${l.status}</span></td></tr>`
  ).join('') || '<tr><td colspan="6" style="text-align:center;color:var(--muted)">No applications yet</td></tr>';

  return `
    <div class="section-card">
      <div class="section-head"><h3>Apply for Leave</h3></div>
      <div class="form-grid">
        <div class="form-field"><label>LEAVE TYPE</label>
          <select id="l-type"><option value="casual">Casual Leave</option><option value="medical">Medical Leave</option>
          <option value="earned">Earned Leave</option><option value="duty">Duty Leave</option></select></div>
        <div class="form-field"><label>NO. OF DAYS</label><input type="number" id="l-days" placeholder="e.g. 2" min="1"/></div>
        <div class="form-field"><label>FROM DATE</label><input type="date" id="l-from"/></div>
        <div class="form-field"><label>TO DATE</label><input type="date" id="l-to"/></div>
        <div class="form-field"><label>SUBSTITUTE FACULTY</label><input type="text" id="l-sub" placeholder="Name"/></div>
        <div class="form-field"><label>CONTACT</label><input type="tel" id="l-contact" placeholder="+91 XXXXX XXXXX"/></div>
        <div class="form-field full"><label>REASON</label><textarea id="l-reason" rows="4" placeholder="Reason for leave…"></textarea></div>
      </div>
      <button class="submit-btn" onclick="submitLeave()">Submit Application</button>
    </div>
    <div class="section-card">
      <div class="section-head"><h3>Leave History</h3></div>
      <table><thead><tr><th>Type</th><th>From</th><th>To</th><th>Days</th><th>Reason</th><th>Status</th></tr></thead>
      <tbody>${hist}</tbody></table>
    </div>`;
}

async function submitLeave() {
  const body = {
    leave_type: document.getElementById('l-type').value,
    from_date:  document.getElementById('l-from').value,
    to_date:    document.getElementById('l-to').value,
    days:       document.getElementById('l-days').value,
    reason:     document.getElementById('l-reason').value,
    substitute: document.getElementById('l-sub').value,
    contact:    document.getElementById('l-contact').value,
  };
  try {
    const res = await api('/api/faculty/leave', { method: 'POST', body: JSON.stringify(body) });
    showToast(res.message);
    loadPanel('f-leave', null);
  } catch (err) {
    showToast(err.message, true);
  }
}

async function buildMarks() {
  const subs = await api('/api/faculty/subjects');
  const students = await api('/api/faculty/students');
  window._marksStudents = students;
  const subOpts = subs.map(s => `<option value="${s.id}">${s.name} (${s.code})</option>`).join('');

  return `
    <div class="section-card">
      <div class="section-head"><h3>Upload Internal Marks</h3></div>
      <div class="form-grid" style="padding-bottom:0">
        <div class="form-field"><label>SUBJECT</label><select id="m-subject">${subOpts}</select></div>
        <div class="form-field"><label>ASSESSMENT TYPE</label>
          <select id="m-type">
            <option value="internal1">Internal Assessment 1</option>
            <option value="internal2">Internal Assessment 2</option>
            <option value="midsem">Mid-Semester</option>
            <option value="assignment">Assignment</option>
          </select>
        </div>
        <div class="form-field"><label>MAX MARKS</label><input type="number" id="m-max" value="30"/></div>
        <div class="form-field"><label>SEMESTER</label><input type="number" id="m-sem" value="6" min="1" max="8"/></div>
      </div>
      <div id="marks-table-wrap" style="padding:1.2rem 1.4rem"></div>
      <button class="submit-btn" onclick="uploadMarks()">Upload Marks</button>
    </div>`;
}

function renderMarksTable(students) {
  const wrap = document.getElementById('marks-table-wrap');
  if (!wrap) return;
  wrap.innerHTML = `<table>
    <thead><tr><th>Roll No.</th><th>Name</th><th>Marks</th></tr></thead>
    <tbody>${(students||[]).map(s => `
      <tr><td>${s.roll_number}</td><td>${s.full_name}</td>
      <td><input type="number" id="mk-${s.id}" min="0" max="100" placeholder="—"
        style="background:var(--surface);border:1px solid var(--border);color:var(--text);padding:.4rem .6rem;border-radius:6px;width:80px;font-family:var(--font-body);outline:none"/></td>
      </tr>`).join('')}
    </tbody></table>`;
}

async function uploadMarks() {
  const students = window._marksStudents || [];
  const records = students.map(s => ({
    student_id: s.id,
    marks: parseFloat(document.getElementById(`mk-${s.id}`)?.value || 0)
  })).filter(r => r.marks > 0);

  if (!records.length) { showToast('Enter at least one mark', true); return; }

  try {
    const res = await api('/api/faculty/marks', {
      method: 'POST',
      body: JSON.stringify({
        subject_id:      parseInt(document.getElementById('m-subject').value),
        semester:        parseInt(document.getElementById('m-sem').value),
        assessment_type: document.getElementById('m-type').value,
        max_marks:       parseFloat(document.getElementById('m-max').value),
        records
      })
    });
    showToast(res.message);
  } catch (err) {
    showToast(err.message, true);
  }
}

async function buildFacultyNotices() {
  return `
    <div class="section-card">
      <div class="section-head"><h3>Post a Notice</h3></div>
      <div class="form-grid">
        <div class="form-field full"><label>NOTICE TITLE</label><input type="text" id="n-title" placeholder="e.g. Unit Test scheduled for Nov 5"/></div>
        <div class="form-field"><label>AUDIENCE</label>
          <select id="n-audience"><option value="all">All</option><option value="students">Students</option><option value="faculty">Faculty</option></select></div>
        <div class="form-field"><label>PRIORITY</label>
          <select id="n-priority"><option value="normal">Normal</option><option value="important">Important</option><option value="urgent">Urgent</option></select></div>
        <div class="form-field full"><label>NOTICE BODY</label><textarea id="n-body" rows="5" placeholder="Write the full notice here…"></textarea></div>
      </div>
      <button class="submit-btn" onclick="postNotice()">Post Notice</button>
    </div>`;
}

async function postNotice() {
  const body = {
    title:    document.getElementById('n-title').value,
    body:     document.getElementById('n-body').value,
    audience: document.getElementById('n-audience').value,
    priority: document.getElementById('n-priority').value
  };
  try {
    const res = await api('/api/faculty/notice', { method: 'POST', body: JSON.stringify(body) });
    showToast(res.message);
    document.getElementById('n-title').value = '';
    document.getElementById('n-body').value  = '';
  } catch (err) {
    showToast(err.message, true);
  }
}

async function buildStudentsPanel() {
  const students = await api('/api/faculty/students');
  const rows = students.map(s => `
    <tr><td>${s.roll_number}</td><td>${s.full_name}</td>
    <td><span class="badge ${s.attendance_pct>=75?'green':s.attendance_pct>=60?'yellow':'red'}">${s.attendance_pct}%</span></td>
    <td><span class="badge green">Regular</span></td></tr>`
  ).join('') || '<tr><td colspan="4" style="text-align:center;color:var(--muted)">No students found</td></tr>';

  return `
    <div class="section-card">
      <div class="section-head"><h3>My Students</h3><span class="badge blue">${students.length} Students</span></div>
      <table><thead><tr><th>Roll No.</th><th>Name</th><th>Attendance</th><th>Status</th></tr></thead>
      <tbody>${rows}</tbody></table>
    </div>`;
}

async function buildSchedule() {
  const sched = await api('/api/faculty/schedule');
  const rows = sched.map(s => {
    const pct = s.total_classes > 0 ? Math.round((s.completed/s.total_classes)*100) : 0;
    return `<tr><td>${s.subject}</td><td>${s.section}</td><td>${s.total_classes||0}</td><td>${s.completed||0}</td>
      <td><div class="prog-bar" style="width:140px"><div class="prog-fill" style="width:${pct}%;background:var(--accent3)"></div></div></td></tr>`;
  }).join('') || '<tr><td colspan="5" style="text-align:center;color:var(--muted)">No data</td></tr>';

  return `
    <div class="section-card">
      <div class="section-head"><h3>Class Schedule & Syllabus Progress</h3></div>
      <table><thead><tr><th>Subject</th><th>Section</th><th>Total Lectures</th><th>Completed</th><th>Progress</th></tr></thead>
      <tbody>${rows}</tbody></table>
    </div>`;
}

// ── TIMETABLE RENDERER ───────────────────────────────────────
function renderTimetable(tt, type) {
  const days  = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const dayShort = ['MON','TUE','WED','THU','FRI','SAT'];
  const times = ['09:00','10:00','11:00','12:00','14:00','15:00','16:00'];
  const cols  = ['c1','c2','c3','c4','c5','c6'];

  // Build lookup: day+time → cell data
  const lookup = {};
  tt.forEach(entry => {
    const key = `${entry.day_of_week}-${(entry.start_time||'').slice(0,5)}`;
    lookup[key] = entry;
  });

  let html = '<div class="timetable">';
  html += '<div class="tt-head"></div>';
  dayShort.forEach(d => html += `<div class="tt-head">${d}</div>`);

  times.forEach(t => {
    const [h] = t.split(':');
    const label = parseInt(h) > 12 ? `${parseInt(h)-12}:00 PM` : `${parseInt(h)}:00 AM`;
    html += `<div class="tt-time">${label}</div>`;
    days.forEach((day, di) => {
      const key = `${day}-${t}`;
      const entry = lookup[key];
      if (entry) {
        const name = entry.subject || entry.code || '—';
        html += `<div class="tt-cell filled ${cols[di]}">
          <span class="sub">${name.split(' ').slice(0,2).join(' ')}</span>
          <span class="room">${entry.room || 'TBD'}</span>
        </div>`;
      } else {
        html += '<div class="tt-cell"></div>';
      }
    });
  });

  html += '</div>';
  return html;
}

// ── INIT ─────────────────────────────────────────────────────
document.getElementById('curr-date').textContent = new Date().toLocaleDateString('en-IN', {
  weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
});

// Check if already logged in
(async () => {
  try {
    const data = await api('/api/me');
    currentRole = data.role;
    currentUser = data.profile;
    setupDashboard(data.role, data.profile);
    document.getElementById('landing').style.display = 'none';
    document.getElementById('dashboard').classList.add('visible');
  } catch (_) {
    // Not logged in — show landing
  }
})();

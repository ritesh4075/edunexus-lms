USE edunexus;

-- Remove existing admin if any
DELETE FROM users WHERE username='admin' AND role='admin';

-- Insert admin (password = admin123, bcrypt hashed)
-- We use a placeholder hash; run fix_admin_password.py to set it properly
INSERT INTO users (username, password, role, email)
VALUES ('admin', 'PLACEHOLDER', 'admin', 'admin@college.edu');

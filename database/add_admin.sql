USE edunexus;

-- Remove existing admin if any
DELETE FROM users WHERE username='admin' AND role='admin';


INSERT INTO users (username, password, role, email)
VALUES ('admin', 'PLACEHOLDER', 'admin', 'admin@college.edu');
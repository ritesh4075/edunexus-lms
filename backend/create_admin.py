from dotenv import load_dotenv
load_dotenv()
import bcrypt
import mysql.connector
import os


DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
}

ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
ADMIN_EMAIL    = os.getenv('ADMIN_EMAIL')

# ─────────────────────────────────────────────────────────────
def main():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Hash the password
        hashed = bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt(12)).decode()

        # Remove old admin if exists
        cursor.execute("DELETE FROM users WHERE username=%s AND role='admin'", (ADMIN_USERNAME,))

        # Insert fresh admin
        cursor.execute(
            "INSERT INTO users (username, password, role, email) VALUES (%s, %s, 'admin', %s)",
            (ADMIN_USERNAME, hashed, ADMIN_EMAIL)
        )
        conn.commit()

        print(f"✅ Admin user created successfully!")
        print(f"   Username : {ADMIN_USERNAME}")
        print(f"   Password : {ADMIN_PASSWORD}")
        print(f"   URL      : http://localhost:5000/admin")

        cursor.close()
        conn.close()

    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")
        print("   Make sure MySQL is running and DB_CONFIG is correct")

if __name__ == '__main__':
    main()

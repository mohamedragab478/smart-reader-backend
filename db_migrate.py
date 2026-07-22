import sqlite3

def run_migration():
    conn = sqlite3.connect('smart_reader.db')
    cursor = conn.cursor()

    # Check if 'email' column exists in 'users' table
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'email' not in columns:
        print("Adding 'email' column to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(100)")
        cursor.execute("CREATE UNIQUE INDEX ix_users_email ON users (email)")

    if 'hashed_password' not in columns:
        print("Adding 'hashed_password' column to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN hashed_password VARCHAR(255)")

    conn.commit()
    conn.close()
    print("Migration finished successfully.")

if __name__ == "__main__":
    run_migration()

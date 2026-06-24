# One-time CLI script for creating staff accounts.
#
# This is the ONLY way a staff_users row is ever created. There is no
# public registration endpoint, and there never will be — accounts are
# provisioned manually by a developer who has direct access to this
# script and the database file.
#
# Usage:
#   python seed_staff.py <username> <display_name>
#   (you will be prompted to enter and confirm a password)

import sys
import getpass

from db import init_db, get_db, generate_id, now_iso
from werkzeug.security import generate_password_hash


def create_staff_user(username, password, display_name):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM staff_users WHERE username = ?", (username,))

    if cur.fetchone():
        conn.close()
        print(f"A staff user with username '{username}' already exists.")
        return False

    cur.execute(
        """
        INSERT INTO staff_users (id, username, password_hash, display_name, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (generate_id(), username, generate_password_hash(password), display_name, now_iso()),
    )
    conn.commit()
    conn.close()

    print(f"Staff user '{username}' created.")
    return True


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python seed_staff.py <username> <display_name>")
        sys.exit(1)

    init_db()

    username = sys.argv[1]
    display_name = sys.argv[2]

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Passwords do not match.")
        sys.exit(1)

    create_staff_user(username, password, display_name)

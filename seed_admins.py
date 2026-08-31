"""建立/重設後台帳號。跑法：venv/bin/python3 seed_admins.py
總管理員(chapter_id=None) + 每個分會各一組，全部預設帳號Admin密碼88888，
沿用bni-chapters既有慣例，之後教練可自行在後台登入更換。
"""
from werkzeug.security import generate_password_hash

import db

DEFAULT_USERNAME = "Admin"
DEFAULT_PASSWORD = "88888"


def main():
    db.init_db()
    conn = db.get_conn()
    pw_hash = generate_password_hash(DEFAULT_PASSWORD)

    db.upsert_admin(conn, DEFAULT_USERNAME, pw_hash, chapter_id=None)
    print(f"總管理員: {DEFAULT_USERNAME}/{DEFAULT_PASSWORD}")

    for c in db.list_chapters(conn):
        db.upsert_admin(conn, DEFAULT_USERNAME, pw_hash, chapter_id=c["id"])
        print(f"{c['name_zh']} (/admin/{c['slug']}/login): {DEFAULT_USERNAME}/{DEFAULT_PASSWORD}")

    conn.close()


if __name__ == "__main__":
    main()

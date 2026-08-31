import os
import secrets
import sqlite3
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(__file__), "team.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

# 順序即顯示順序：官網/FB/IG/Threads/YouTube/GJW(乾淨世界)/LINE/Podcast/部落格
MEMBER_LINK_FIELDS = (
    ("website_url", "website_label", "官網"),
    ("fb_url", "fb_label", "FB"),
    ("ig_url", "ig_label", "IG"),
    ("threads_url", "threads_label", "Threads"),
    ("youtube_url", "youtube_label", "YouTube"),
    ("gjw_url", "gjw_label", "GJW"),
    ("line_url", "line_label", "LINE"),
    ("podcast_url", "podcast_label", "Podcast"),
    ("blog_url", "blog_label", "部落格"),
)
MEMBER_LINK_COLUMNS = tuple(url_col for url_col, _, _ in MEMBER_LINK_FIELDS)
MEMBER_LABEL_COLUMNS = tuple(label_col for _, label_col, _ in MEMBER_LINK_FIELDS)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def get_super_admin(conn, username):
    return conn.execute(
        "SELECT * FROM admins WHERE username = ? AND chapter_id IS NULL", (username,)
    ).fetchone()


def get_chapter_admin(conn, chapter_id, username):
    return conn.execute(
        "SELECT * FROM admins WHERE username = ? AND chapter_id = ?", (username, chapter_id)
    ).fetchone()


def upsert_admin(conn, username, password_hash, chapter_id=None):
    existing = (
        get_super_admin(conn, username)
        if chapter_id is None
        else get_chapter_admin(conn, chapter_id, username)
    )
    if existing:
        conn.execute("UPDATE admins SET password_hash = ? WHERE id = ?", (password_hash, existing["id"]))
    else:
        conn.execute(
            "INSERT INTO admins (username, password_hash, chapter_id) VALUES (?, ?, ?)",
            (username, password_hash, chapter_id),
        )
    conn.commit()


def list_chapters(conn):
    return conn.execute("SELECT * FROM chapters ORDER BY sort_order ASC, id ASC").fetchall()


def get_chapter(conn, chapter_id):
    return conn.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,)).fetchone()


def get_chapter_by_slug(conn, slug):
    return conn.execute("SELECT * FROM chapters WHERE slug = ?", (slug,)).fetchone()


def get_notices(conn, chapter_id):
    return conn.execute(
        "SELECT * FROM chapter_notices WHERE chapter_id = ? ORDER BY sort_order ASC, id ASC",
        (chapter_id,),
    ).fetchall()


MAX_VALUES = 9


def get_values(conn, chapter_id):
    return conn.execute(
        "SELECT * FROM chapter_values WHERE chapter_id = ? ORDER BY sort_order ASC, id ASC",
        (chapter_id,),
    ).fetchall()


def count_values(conn, chapter_id):
    return conn.execute(
        "SELECT COUNT(*) FROM chapter_values WHERE chapter_id = ?", (chapter_id,)
    ).fetchone()[0]


def add_value(conn, chapter_id, title, body):
    if count_values(conn, chapter_id) >= MAX_VALUES:
        return False
    max_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) FROM chapter_values WHERE chapter_id = ?",
        (chapter_id,),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO chapter_values (chapter_id, title, body, sort_order) VALUES (?, ?, ?, ?)",
        (chapter_id, title, body, max_order + 1),
    )
    conn.commit()
    return True


def delete_value(conn, value_id, chapter_id):
    conn.execute(
        "DELETE FROM chapter_values WHERE id = ? AND chapter_id = ?", (value_id, chapter_id)
    )
    conn.commit()


def get_stats(conn, chapter_id):
    return conn.execute(
        "SELECT * FROM chapter_stats WHERE chapter_id = ? ORDER BY sort_order ASC, id ASC",
        (chapter_id,),
    ).fetchall()


def get_links(conn, chapter_id):
    return conn.execute(
        "SELECT * FROM chapter_links WHERE chapter_id = ? ORDER BY sort_order ASC, id ASC",
        (chapter_id,),
    ).fetchall()


def update_chapter(conn, chapter_id, fields: dict):
    cols = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [chapter_id]
    conn.execute(
        f"UPDATE chapters SET {cols}, updated_at = datetime('now','localtime') WHERE id = ?",
        values,
    )
    conn.commit()


def add_notice(conn, chapter_id, title, body):
    max_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) FROM chapter_notices WHERE chapter_id = ?",
        (chapter_id,),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO chapter_notices (chapter_id, title, body, sort_order) VALUES (?, ?, ?, ?)",
        (chapter_id, title, body, max_order + 1),
    )
    conn.commit()


def delete_notice(conn, notice_id, chapter_id):
    conn.execute(
        "DELETE FROM chapter_notices WHERE id = ? AND chapter_id = ?", (notice_id, chapter_id)
    )
    conn.commit()


def add_stat(conn, chapter_id, num, label):
    max_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) FROM chapter_stats WHERE chapter_id = ?",
        (chapter_id,),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO chapter_stats (chapter_id, num, label, sort_order) VALUES (?, ?, ?, ?)",
        (chapter_id, num, label, max_order + 1),
    )
    conn.commit()


def delete_stat(conn, stat_id, chapter_id):
    conn.execute(
        "DELETE FROM chapter_stats WHERE id = ? AND chapter_id = ?", (stat_id, chapter_id)
    )
    conn.commit()


def add_link(conn, chapter_id, label, url):
    max_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) FROM chapter_links WHERE chapter_id = ?",
        (chapter_id,),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO chapter_links (chapter_id, label, url, sort_order) VALUES (?, ?, ?, ?)",
        (chapter_id, label, url, max_order + 1),
    )
    conn.commit()


def update_link(conn, link_id, chapter_id, label, url):
    conn.execute(
        "UPDATE chapter_links SET label = ?, url = ? WHERE id = ? AND chapter_id = ?",
        (label, url, link_id, chapter_id),
    )
    conn.commit()


def delete_link(conn, link_id, chapter_id):
    conn.execute(
        "DELETE FROM chapter_links WHERE id = ? AND chapter_id = ?", (link_id, chapter_id)
    )
    conn.commit()


def list_members(conn, chapter_id):
    return conn.execute(
        "SELECT * FROM chapter_members WHERE chapter_id = ? ORDER BY id ASC", (chapter_id,)
    ).fetchall()


def get_member_by_token(conn, chapter_id, token):
    if not token:
        return None
    return conn.execute(
        "SELECT * FROM chapter_members WHERE chapter_id = ? AND edit_token = ?", (chapter_id, token)
    ).fetchone()


def member_links(member) -> list[dict]:
    """回傳這位夥伴已填的連結，依指定顯示順序，label留空則用預設按鈕文字。"""
    result = []
    for url_col, label_col, default_label in MEMBER_LINK_FIELDS:
        url = member[url_col]
        if url:
            result.append({"label": member[label_col] or default_label, "url": url})
    return result


def insert_member(conn, chapter_id, name, company_title, role_tag, bio, photo_filename, links: dict) -> tuple[int, str]:
    token = secrets.token_urlsafe(16)
    cols = ["chapter_id", "name", "company_title", "role_tag", "bio", "photo_filename",
            *MEMBER_LINK_COLUMNS, *MEMBER_LABEL_COLUMNS, "edit_token"]
    values = [chapter_id, name, company_title, role_tag or None, bio, photo_filename,
              *[links.get(c) or None for c in MEMBER_LINK_COLUMNS],
              *[links.get(c) or None for c in MEMBER_LABEL_COLUMNS], token]
    placeholders = ", ".join("?" for _ in cols)
    cur = conn.execute(f"INSERT INTO chapter_members ({', '.join(cols)}) VALUES ({placeholders})", values)
    conn.commit()
    return cur.lastrowid, token


def update_member(conn, member_id, name, company_title, role_tag, bio, links: dict, photo_filename=None):
    cols = ["name", "company_title", "role_tag", "bio", *MEMBER_LINK_COLUMNS, *MEMBER_LABEL_COLUMNS]
    values = [name, company_title, role_tag or None, bio,
              *[links.get(c) or None for c in MEMBER_LINK_COLUMNS],
              *[links.get(c) or None for c in MEMBER_LABEL_COLUMNS]]
    if photo_filename:
        cols.append("photo_filename")
        values.append(photo_filename)
    set_clause = ", ".join(f"{c} = ?" for c in cols)
    values.append(member_id)
    conn.execute(f"UPDATE chapter_members SET {set_clause} WHERE id = ?", values)
    conn.commit()


def delete_member(conn, member_id, chapter_id):
    conn.execute(
        "DELETE FROM chapter_members WHERE id = ? AND chapter_id = ?", (member_id, chapter_id)
    )
    conn.commit()

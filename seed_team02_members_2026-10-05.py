"""第二分會（team-02）夥伴座位匯入（2026-10-05 教練 14:59 給的名單）。

名單與專業類別照教練給的（第二分會沒有戰情表可對照）：鄧智文 大圖輸出、廖允菁 會計師、陳晏綜 勞資顧問、何琬菁 人壽保險、
翁郁琇 電子針灸儀（教練寫成「翁郁琇-電子針灸儀」，姓名在前）。
注意：陳晏綜同時在第一分會戰情表（team01）裡；教練名單把他放第二分會，歸屬待教練確認（確認後把另一邊的座位刪掉）。
重跑安全：同名的座位已存在就略過。
"""
import db

CHAPTER_SLUG = "team-02"
MEMBERS = [("鄧智文", "大圖輸出"), ("廖允菁", "會計師"), ("陳晏綜", "勞資顧問"), ("何琬菁", "人壽保險"), ("翁郁琇", "電子針灸儀")]


def main():
    db.init_db()
    conn = db.get_conn()
    chapter = db.get_chapter_by_slug(conn, CHAPTER_SLUG)
    have = {r["name"] for r in conn.execute("SELECT name FROM chapter_members WHERE chapter_id = ?", (chapter["id"],))}
    added = []
    for name, category in MEMBERS:
        if name in have:
            continue
        member_id, _ = db.insert_member(conn, chapter["id"], name, "", category, "", "", {})
        conn.execute("UPDATE chapter_members SET claim_phones = '', source = 'seed-team02-20261005' WHERE id = ?", (member_id,))
        conn.commit()
        added.append(f"{name}（{category}）")
    conn.close()
    print(f"新增座位 {len(added)} 位：{'、'.join(added)}" if added else "沒有新增（都已存在）")


if __name__ == "__main__":
    main()

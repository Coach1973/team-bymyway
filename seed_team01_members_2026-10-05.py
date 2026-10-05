"""第一分會（team-01）夥伴座位匯入（2026-10-05 教練交辦）。

名單＝戰情表（team01.bymyway.com，資料在 ~/github_repos/team01-guests/team01_guests.db 的 members）上的姓名，
扣掉陳佩君（啟動董顧）、陳宜璟（支持與成長董顧）——兩位等分會正式立會才寫上去（教練 10/05 14:52）。
專業類別：教練給的名單裡姓名跟戰情表對得上才寫；對不上的是新增的夥伴，專業類別留給本人自己補（教練 14:52 規則）。
教練 14:54 補充「以戰情表上的姓名為主」：教練名單的「陳漳豪（產險）」對到戰情表同一個位置、同樣的名字讀音的「謝漳濠」，
採用戰情表的寫法。座位沒有照片與連結，本人到分會頁按「我是○○・補上照片」認領後自己補。
重跑安全：同名的座位已存在就略過。
"""
import sqlite3
from pathlib import Path

import db

CHAPTER_SLUG = "team-01"
WAR_ROOM_DB = Path.home() / "github_repos" / "team01-guests" / "team01_guests.db"
EXCLUDE = {"陳佩君", "陳宜璟"}
# 教練 10/05 給的名單（姓名以戰情表寫法為準）
CATEGORY = {"鄭季顓": "人壽保險", "謝漳濠": "產險", "簡美惠": "保健食品", "林芸安": "美白牙齒",
            "黃乙純": "高級訂製服", "李星慕": "汽車零件外銷",
            "陳晏綜": "勞資顧問"}  # 陳晏綜：教練第二分會名單也有他，15:01 說重複以戰情表為主→留第一分會，類別取自教練名單
# 教練名單裡戰情表上沒有的姓名＝新增的夥伴（專業類別等本人自己補；教練名單寫的是投資型保單、行動美容）
NEW_PARTNERS = ["陳迎薰", "王純藝"]


def war_room_names():
    c = sqlite3.connect(WAR_ROOM_DB)
    rows = c.execute("SELECT name FROM members WHERE name <> '' AND left_chapter = 0 ORDER BY sort_order").fetchall()
    c.close()
    return [r[0] for r in rows if r[0] not in EXCLUDE]


def main():
    db.init_db()  # 補上 claim_phones 欄位（舊資料庫）
    conn = db.get_conn()
    chapter = db.get_chapter_by_slug(conn, CHAPTER_SLUG)
    have = {r["name"] for r in conn.execute("SELECT name FROM chapter_members WHERE chapter_id = ?", (chapter["id"],))}
    added = []
    for name in [*war_room_names(), *NEW_PARTNERS]:
        if name in have:
            continue
        member_id, _ = db.insert_member(conn, chapter["id"], name, "", CATEGORY.get(name), "", "", {})
        conn.execute("UPDATE chapter_members SET claim_phones = '', source = 'seed-team01-20261005' WHERE id = ?", (member_id,))
        conn.commit()
        added.append(name + (f"（{CATEGORY[name]}）" if name in CATEGORY else ""))
    conn.close()
    print(f"新增座位 {len(added)} 位：{'、'.join(added)}" if added else "沒有新增（都已存在）")


if __name__ == "__main__":
    main()

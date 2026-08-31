"""team.bymyway.com 初始資料灌入。
架構複製自 bni-chapters/seed.py（chapters.bymyway.com），分會改用通用編號命名（第一/第二/第三分會）。

跑法：python seed.py（重複執行會先清空 chapters 表再重灌，僅供建置階段使用）

⚠️ 啟動提醒：
- 種子資料是「可運行的最小示範」，內容文案是佔位用，教練之後在後台增修即可。
- 顏色/字級等視覺規格全部在 base.html，跟 BNI 紅黑色系已徹底切換成 teal 主題。
- show_traditions 旗標（對應 bni-chapters 六項傳統與道德規範區塊）已預設關閉，這個區塊不會渲染。
"""
import db

CHAPTERS = [
    {
        "slug": "team-01",
        "name_zh": "第一分會",
        "name_en": "Team 01",
        "status": "active",
        "sort_order": 1,
        "hero_title": "第一分會",
        "hero_desc": "通用分會示範・team.bymyway.com — 服務對象是還沒正式加入 BNI 的朋友，用 BNI 模式運作的分會雛形",
        "cta_label": "預約參訪",
        "about_tag": "Before You Visit",
        "about_title": "參訪須知",
        "about_desc": "歡迎您來第一分會參訪，請提前準備以下事項，讓這次商務交流更順暢。",
        "footer_slogan": "第一分會・通用示範",
        "show_traditions": 0,
        "values": [
            ("Givers Gain．付出者收穫", "會員彼此做專業交流、建立信任關係，在信任的基礎上互相引薦生意，唯一限制是一個專業僅有一個代表。"),
            ("真誠待人．長期共贏", "用真心對待每一位夥伴，用專業累積口碑，讓引薦成為自然發生的結果。"),
        ],
        "notices": [
            ("請著正式服裝", "展現專業商務形象"),
            ("準備名片", "與全體會員交換聯繫"),
            ("20秒自我介紹", "精彩簡介您的專業"),
            ("餐費自理", "依各分會公告為準"),
        ],
        "stats": [
            ("40+", "在籍會員・涵蓋多元專業產業"),
            ("每週聚會", "固定時間・固定地點"),
            ("籌備中", "招募創始會員中"),
        ],
        "links": [("Facebook", "#"), ("Line官方帳號", "#"), ("聯絡我們", "#")],
    },
    {
        "slug": "team-02",
        "name_zh": "第二分會",
        "name_en": "Team 02",
        "status": "active",
        "sort_order": 2,
        "hero_title": "第二分會",
        "hero_desc": "通用分會示範・team.bymyway.com — 示範分會第二個，內容由後台管理員自行編輯",
        "cta_label": "預約參訪",
        "footer_slogan": "第二分會",
        "show_traditions": 0,
        "values": [
            ("Givers Gain．付出者收穫", "會員彼此做專業交流、建立信任關係，在信任的基礎上互相引薦生意，唯一限制是一個專業僅有一個代表。"),
        ],
        "notices": [],
        "stats": [],
        "links": [],
    },
    {
        "slug": "team-03",
        "name_zh": "第三分會",
        "name_en": "Team 03",
        "status": "active",
        "sort_order": 3,
        "hero_title": "第三分會",
        "hero_desc": "通用分會示範・team.bymyway.com — 示範分會第三個，內容由後台管理員自行編輯",
        "cta_label": "預約參訪",
        "footer_slogan": "第三分會",
        "show_traditions": 0,
        "values": [
            ("Givers Gain．付出者收穫", "會員彼此做專業交流、建立信任關係，在信任的基礎上互相引薦生意，唯一限制是一個專業僅有一個代表。"),
        ],
        "notices": [],
        "stats": [],
        "links": [],
    },
]


def main():
    db.init_db()
    conn = db.get_conn()
    conn.execute("DELETE FROM chapters")
    conn.commit()

    for c in CHAPTERS:
        values = c.pop("values")
        notices = c.pop("notices")
        stats = c.pop("stats")
        links = c.pop("links")
        cols = ", ".join(c.keys())
        placeholders = ", ".join("?" for _ in c)
        cur = conn.execute(
            f"INSERT INTO chapters ({cols}) VALUES ({placeholders})", list(c.values())
        )
        chapter_id = cur.lastrowid
        for title, body in values:
            db.add_value(conn, chapter_id, title, body)
        for title, body in notices:
            db.add_notice(conn, chapter_id, title, body)
        for num, label in stats:
            db.add_stat(conn, chapter_id, num, label)
        for label, url in links:
            db.add_link(conn, chapter_id, label, url)
        print(f"seeded: {c['name_zh']} (id={chapter_id}, slug={c['slug']})")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()

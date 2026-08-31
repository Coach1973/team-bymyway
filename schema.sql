CREATE TABLE IF NOT EXISTS chapters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT NOT NULL UNIQUE,
    name_zh       TEXT NOT NULL,
    name_en       TEXT,
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','forming')),
    badge_text    TEXT,
    hero_title    TEXT,
    hero_desc     TEXT,
    cta_label     TEXT NOT NULL DEFAULT '預約參訪',
    about_tag     TEXT,
    about_title   TEXT,
    about_desc    TEXT,
    footer_slogan TEXT,
    show_traditions INTEGER NOT NULL DEFAULT 1,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 參訪須知／招募資格這類4卡區塊，管理員可自行新增刪除
CREATE TABLE IF NOT EXISTS chapter_notices (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    body       TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0
);

-- 後台帳號。chapter_id為NULL＝總管理員(可管全部分會)，有值＝只能管該分會
-- username在同一個chapter_id範圍內唯一即可，允許不同分會都叫Admin
CREATE TABLE IF NOT EXISTS admins (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    chapter_id    INTEGER REFERENCES chapters(id) ON DELETE CASCADE,
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(chapter_id, username)
);

-- 核心價值卡，管理員可自行新增刪除，最多3項(app.py強制)
CREATE TABLE IF NOT EXISTS chapter_values (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    body       TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0
);

-- 分會之光數據卡，管理員可自行新增刪除
CREATE TABLE IF NOT EXISTS chapter_stats (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    num        TEXT NOT NULL,
    label      TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

-- 社群/外部連結(官網/FB/LINE/報名表單等)，管理員可自行新增刪除＝「新增欄目」
CREATE TABLE IF NOT EXISTS chapter_links (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    label      TEXT NOT NULL,
    url        TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

-- 分會夥伴自助簡介卡：會員自己填寫送出，立刻上架顯示在分會頁面(不經審核)
-- edit_token讓會員憑連結自己修改/刪除，仿mentor100百人導師第一階段自助送出設計
CREATE TABLE IF NOT EXISTS chapter_members (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id     INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    company_title  TEXT NOT NULL,
    role_tag       TEXT,
    bio            TEXT NOT NULL,
    photo_filename TEXT NOT NULL,
    website_url    TEXT, website_label TEXT,
    fb_url         TEXT, fb_label TEXT,
    ig_url         TEXT, ig_label TEXT,
    threads_url    TEXT, threads_label TEXT,
    youtube_url    TEXT, youtube_label TEXT,
    gjw_url        TEXT, gjw_label TEXT,
    line_url       TEXT, line_label TEXT,
    podcast_url    TEXT, podcast_label TEXT,
    blog_url       TEXT, blog_label TEXT,
    edit_token     TEXT NOT NULL UNIQUE,
    source         TEXT NOT NULL DEFAULT 'self-submit',
    created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 「預約參訪」/「登記成為創始會員」表單（2026-09-01教練交辦，不分分會狀態一律適用）：
-- 送出後即時Telegram通知教練，比照bni-chapters籌備會的founder_signups設計
CREATE TABLE IF NOT EXISTS visit_signups (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    phone      TEXT NOT NULL,
    email      TEXT,
    company    TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

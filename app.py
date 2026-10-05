"""
team.bymyway.com — 通用分會系統
架構複製自 bni-chapters（chapters.bymyway.com），拿掉 BNI 品牌元素（LOGO/紅黑色系/核心價值文案/六項傳統與道德規範）。
分會命名改用通用編號（第一分會/第二分會/第三分會……），服務對象是「還沒正式加入 BNI 的朋友」。

跑法：python app.py（預設 port 5073）
公開頁：/ 分會列表、/<slug> 分會頁面
後台帳號分兩層：
- 總管理員／admin/login，登入後可管理全部分會(session admin_scope="super")
- 各分會獨立管理員／admin/<slug>/login，登入後只能管自己那個分會
  (session admin_scope=該分會chapter_id)，網址跟帳密都各自獨立。
"""
import os
import re
import subprocess
import time
from collections import defaultdict
from functools import wraps
from io import BytesIO
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, session, url_for
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.security import check_password_hash

import db

app = Flask(__name__)
app.secret_key = os.environ.get("TEAM_SECRET_KEY", "")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads")
ALLOWED_EXTS = {"jpg", "jpeg", "png", "webp"}
MAX_PHOTO_EDGE = 1200
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8MB

_rate_limit_log: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 3600  # 1 小時

NOTIFY_SCRIPT = Path.home() / ".openclaw" / "workspace" / "scripts" / "notify_coach.sh"


def _notify_coach(msg: str) -> None:
    """統一走workspace共用的notify_coach.sh（打Telegram），失敗只記log不影響送出體驗。"""
    try:
        subprocess.run(["bash", str(NOTIFY_SCRIPT), msg], capture_output=True, text=True, timeout=15)
    except Exception:
        pass


db.init_db()
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _sanitize_filename(raw: str) -> str:
    """保留中文檔名，只擋掉路徑穿越與危險字元。"""
    name = os.path.basename(raw).replace("\x00", "")
    name = re.sub(r'[/\\:*?"<>|]', "", name)
    return name.strip() or "file"


def _process_and_save_photo(file_storage) -> str | None:
    """驗證是不是真的圖片、轉正方向、縮圖存檔。回傳存檔後的檔名；失敗回傳None。
    消毒後一律加隨機後綴，避免不同夥伴上傳同名檔案互相覆蓋。"""
    raw_name = _sanitize_filename(file_storage.filename or "photo.jpg")
    ext = raw_name.rsplit(".", 1)[-1].lower() if "." in raw_name else ""
    if ext not in ALLOWED_EXTS:
        ext = "jpg"

    try:
        data = file_storage.read()
        img = Image.open(BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        return None

    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((MAX_PHOTO_EDGE, MAX_PHOTO_EDGE))

    filename = f"{os.urandom(8).hex()}_{raw_name.rsplit('.', 1)[0]}.jpg"
    img.save(os.path.join(UPLOAD_DIR, filename), "JPEG", quality=85)
    return filename


def _check_rate_limit(ip: str) -> bool:
    """回傳True代表可以送出，False代表這個IP這小時已經送太多次。"""
    now = time.time()
    log = _rate_limit_log[ip]
    log[:] = [t for t in log if now - t < RATE_LIMIT_WINDOW]
    if len(log) >= RATE_LIMIT_MAX:
        return False
    log.append(now)
    return True


def _extract_member_links(form) -> dict:
    cols = (*db.MEMBER_LINK_COLUMNS, *db.MEMBER_LABEL_COLUMNS)
    return {col: (form.get(col) or "").strip() for col in cols}


def login_required(view):
    """未登入導去總登入頁；分會範圍帳號只能碰自己chapter_id的route，否則403。"""

    @wraps(view)
    def wrapped(*args, **kwargs):
        admin_scope = session.get("admin_scope")
        if admin_scope is None:
            return redirect(url_for("admin_login", next=request.path))
        if admin_scope != "super":
            target_id = kwargs.get("chapter_id")
            if target_id is None or int(admin_scope) != int(target_id):
                abort(403)
        return view(*args, **kwargs)

    return wrapped


# ---------- 公開頁 ----------

@app.route("/")
def index():
    conn = db.get_conn()
    chapters = db.list_chapters(conn)
    conn.close()
    first_chapter_slug = chapters[0]["slug"] if chapters else ""
    return render_template("index.html", chapters=chapters, first_chapter_slug=first_chapter_slug)


@app.route("/<slug>")
def chapter_page(slug):
    conn = db.get_conn()
    chapter = db.get_chapter_by_slug(conn, slug)
    if not chapter:
        conn.close()
        abort(404)
    notices = db.get_notices(conn, chapter["id"])
    values = db.get_values(conn, chapter["id"])
    stats = db.get_stats(conn, chapter["id"])
    links = db.get_links(conn, chapter["id"])
    members = db.list_members(conn, chapter["id"])
    conn.close()
    return render_template(
        "chapter.html",
        chapter=chapter,
        notices=notices,
        values=values,
        stats=stats,
        links=links,
        members=members,
        member_links=db.member_links,
    )


# ---------- 分會夥伴自助簡介（送出後立刻上架，不經審核） ----------

@app.route("/<slug>/join", methods=["GET"])
def member_join_form(slug):
    conn = db.get_conn()
    chapter = db.get_chapter_by_slug(conn, slug)
    if not chapter:
        conn.close()
        abort(404)
    # 已經事先建好座位的分會（第一分會起）：先請本人認座位，名單上沒有的才走新建表單
    seats = db.list_claimable_members(conn, chapter["id"])
    conn.close()
    if seats and request.args.get("new") != "1":
        picked = int(request.args["seat"]) if (request.args.get("seat") or "").isdigit() else None
        return render_template("member_claim.html", chapter=chapter, seats=seats, error=None, picked=picked)
    return render_template("member_join.html", chapter=chapter, error=None, form={})


@app.route("/<slug>/claim", methods=["POST"])
def member_claim_submit(slug):
    """選名字就進到自己的座位：姓名以戰情表為準，本人補照片、公司/專業類別、簡介與連結。"""
    conn = db.get_conn()
    chapter = db.get_chapter_by_slug(conn, slug)
    if not chapter:
        conn.close()
        abort(404)
    try:
        member_id = int(request.form.get("member_id") or 0)
    except ValueError:
        member_id = 0
    member = db.get_seeded_member(conn, chapter["id"], member_id)
    if not member:
        seats = db.list_claimable_members(conn, chapter["id"])
        conn.close()
        return render_template(
            "member_claim.html", chapter=chapter, seats=seats, picked=None, error="請先選擇您的名字",
        ), 400
    conn.close()
    return redirect(url_for("member_join_edit", slug=slug, token=member["edit_token"]))


@app.route("/<slug>/join", methods=["POST"])
def member_join_submit(slug):
    conn = db.get_conn()
    chapter = db.get_chapter_by_slug(conn, slug)
    if not chapter:
        conn.close()
        abort(404)

    # honeypot：一般人看不到這個欄位，機器人才會填
    if (request.form.get("website") or "").strip():
        conn.close()
        return redirect(url_for("member_join_thanks", slug=slug))

    ip = request.headers.get("CF-Connecting-IP") or request.remote_addr or "unknown"
    if not _check_rate_limit(ip):
        conn.close()
        return render_template(
            "member_join.html", chapter=chapter,
            error="這個小時送出次數太多了，請稍後再試一次", form=request.form,
        ), 429

    name = (request.form.get("name") or "").strip()
    company_title = (request.form.get("company_title") or "").strip()
    role_tag = (request.form.get("role_tag") or "").strip()
    bio = (request.form.get("bio") or "").strip()
    links = _extract_member_links(request.form)
    photo = request.files.get("photo")

    error = None
    if not name:
        error = "請填寫姓名"
    elif not company_title:
        error = "請填寫公司/職稱"
    elif not bio:
        error = "請填寫簡介"
    elif not photo or not photo.filename:
        error = "請上傳一張照片"

    filename = None
    if not error:
        filename = _process_and_save_photo(photo)
        if not filename:
            error = "這張照片打不開，麻煩改存成 jpg 或 png 格式再上傳一次"

    if error:
        conn.close()
        return render_template(
            "member_join.html", chapter=chapter, error=error,
            form={"name": name, "company_title": company_title, "role_tag": role_tag,
                  "bio": bio, **links},
        ), 400

    _, token = db.insert_member(conn, chapter["id"], name, company_title, role_tag, bio, filename, links)
    conn.close()
    return redirect(url_for("member_join_thanks", slug=slug, token=token))


@app.route("/<slug>/join/thanks")
def member_join_thanks(slug):
    conn = db.get_conn()
    chapter = db.get_chapter_by_slug(conn, slug)
    conn.close()
    if not chapter:
        abort(404)
    token = request.args.get("token") or ""
    edit_url = url_for("member_join_edit", slug=slug, token=token, _external=True) if token else None
    return render_template("member_join_thanks.html", chapter=chapter, edit_url=edit_url)


@app.route("/<slug>/visit-signup", methods=["GET"])
def visit_signup_form(slug):
    """「預約參訪」／「登記成為創始會員」表單（2026-09-01教練交辦，不分分會狀態，按鈕一律連到這裡）。"""
    conn = db.get_conn()
    chapter = db.get_chapter_by_slug(conn, slug)
    conn.close()
    if not chapter:
        abort(404)
    return render_template("visit_signup.html", chapter=chapter, form={})


@app.route("/<slug>/visit-signup", methods=["POST"])
def visit_signup_submit(slug):
    conn = db.get_conn()
    chapter = db.get_chapter_by_slug(conn, slug)
    if not chapter:
        conn.close()
        abort(404)

    # honeypot：一般人看不到這個欄位，機器人才會填
    if (request.form.get("website") or "").strip():
        conn.close()
        return redirect(url_for("visit_signup_thanks", slug=slug))

    ip = request.headers.get("CF-Connecting-IP") or request.remote_addr or "unknown"
    if not _check_rate_limit(ip):
        conn.close()
        return render_template(
            "visit_signup.html", chapter=chapter,
            error="這個小時送出次數太多了，請稍後再試一次", form=request.form,
        ), 429

    name = (request.form.get("name") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    email = (request.form.get("email") or "").strip()
    company = (request.form.get("company") or "").strip()

    error = None
    if not name:
        error = "請填寫姓名"
    elif not phone:
        error = "請填寫電話"

    if error:
        conn.close()
        return render_template(
            "visit_signup.html", chapter=chapter, error=error,
            form={"name": name, "phone": phone, "email": email, "company": company},
        ), 400

    db.insert_visit_signup(conn, chapter["id"], name, phone, email, company)
    conn.close()

    _notify_coach(
        f"🎯【{chapter['cta_label'] or '預約參訪'}】{chapter['name_zh']}\n"
        f"姓名：{name}\n電話：{phone}\nEmail：{email or '未填'}\n公司：{company or '未填'}"
    )

    return redirect(url_for("visit_signup_thanks", slug=slug))


@app.route("/<slug>/visit-signup/thanks")
def visit_signup_thanks(slug):
    conn = db.get_conn()
    chapter = db.get_chapter_by_slug(conn, slug)
    conn.close()
    if not chapter:
        abort(404)
    return render_template("visit_signup_thanks.html", chapter=chapter)


@app.route("/<slug>/join/edit/<token>", methods=["GET"])
def member_join_edit(slug, token):
    conn = db.get_conn()
    chapter = db.get_chapter_by_slug(conn, slug)
    if not chapter:
        conn.close()
        abort(404)
    member = db.get_member_by_token(conn, chapter["id"], token)
    conn.close()
    if not member:
        abort(404)
    saved = request.args.get("saved") == "1"
    return render_template(
        "member_join_edit.html", chapter=chapter, member=member, error=None, form=None,
        token=token, saved=saved,
    )


@app.route("/<slug>/join/edit/<token>", methods=["POST"])
def member_join_edit_submit(slug, token):
    conn = db.get_conn()
    chapter = db.get_chapter_by_slug(conn, slug)
    if not chapter:
        conn.close()
        abort(404)
    member = db.get_member_by_token(conn, chapter["id"], token)
    if not member:
        conn.close()
        abort(404)

    # 事先建好的座位：姓名以戰情表為準不能改；公司、簡介可以先空著，不能因此卡住
    seeded = member["claim_phones"] is not None
    name = member["name"] if seeded else (request.form.get("name") or "").strip()
    company_title = (request.form.get("company_title") or "").strip()
    role_tag = (request.form.get("role_tag") or "").strip()
    bio = (request.form.get("bio") or "").strip()
    links = _extract_member_links(request.form)
    photo = request.files.get("photo")

    error = None
    if not name or (not seeded and (not company_title or not bio)):
        error = "姓名、公司/職稱、簡介都要填"

    filename = None
    if not error and photo and photo.filename:
        filename = _process_and_save_photo(photo)
        if not filename:
            error = "這張照片打不開，麻煩改存成 jpg 或 png 格式再上傳一次"

    if error:
        conn.close()
        return render_template(
            "member_join_edit.html", chapter=chapter, member=member, error=error, token=token,
            form={"name": name, "company_title": company_title, "role_tag": role_tag,
                  "bio": bio, **links},
        ), 400

    if seeded:
        db.log_member_edit(conn, member, request.headers.get("CF-Connecting-IP") or request.remote_addr)
    db.update_member(conn, member["id"], name, company_title, role_tag, bio, links, filename)
    conn.close()
    return redirect(url_for("member_join_edit", slug=slug, token=token, saved=1))


@app.route("/<slug>/join/edit/<token>/delete", methods=["POST"])
def member_join_edit_delete(slug, token):
    conn = db.get_conn()
    chapter = db.get_chapter_by_slug(conn, slug)
    if not chapter:
        conn.close()
        abort(404)
    member = db.get_member_by_token(conn, chapter["id"], token)
    if not member or member["claim_phones"] is not None:
        # 事先建好的座位沒有密碼，不開放從前台刪除（要下架請找管理員）
        conn.close()
        abort(404)
    db.delete_member(conn, member["id"], chapter["id"])
    conn.close()
    return redirect(url_for("chapter_page", slug=slug))


# ---------- 後台登入 ----------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        conn = db.get_conn()
        admin = db.get_super_admin(conn, username)
        conn.close()
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin_scope"] = "super"
            next_url = request.args.get("next") or url_for("admin_list")
            return redirect(next_url)
        error = "帳號或密碼錯誤"
    return render_template("login.html", error=error, title="team.bymyway.com・總管理後台")


@app.route("/admin/<slug>/login", methods=["GET", "POST"])
def chapter_admin_login(slug):
    conn = db.get_conn()
    chapter = db.get_chapter_by_slug(conn, slug)
    if not chapter:
        conn.close()
        abort(404)

    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        admin = db.get_chapter_admin(conn, chapter["id"], username)
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin_scope"] = chapter["id"]
            conn.close()
            return redirect(url_for("admin_edit", chapter_id=chapter["id"]))
        error = "帳號或密碼錯誤"
    conn.close()
    return render_template("login.html", error=error, title=f"{chapter['name_zh']}・後台登入")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_scope", None)
    return redirect(url_for("admin_login"))


# ---------- 後台管理 ----------

@app.route("/admin")
@login_required
def admin_list():
    conn = db.get_conn()
    chapters = db.list_chapters(conn)
    conn.close()
    return render_template("admin_list.html", chapters=chapters)


@app.route("/admin/chapters/<int:chapter_id>/edit", methods=["GET", "POST"])
@login_required
def admin_edit(chapter_id):
    conn = db.get_conn()
    chapter = db.get_chapter(conn, chapter_id)
    if not chapter:
        conn.close()
        abort(404)

    if request.method == "POST":
        fields = {
            "name_zh": request.form.get("name_zh", "").strip(),
            "name_en": request.form.get("name_en", "").strip(),
            "status": request.form.get("status", "active"),
            "badge_text": request.form.get("badge_text", "").strip(),
            "hero_title": request.form.get("hero_title", "").strip(),
            "hero_desc": request.form.get("hero_desc", "").strip(),
            "cta_label": request.form.get("cta_label", "預約參訪").strip(),
            "about_tag": request.form.get("about_tag", "").strip(),
            "about_title": request.form.get("about_title", "").strip(),
            "about_desc": request.form.get("about_desc", "").strip(),
            "footer_slogan": request.form.get("footer_slogan", "").strip(),
            "show_traditions": 1 if request.form.get("show_traditions") else 0,
        }
        db.update_chapter(conn, chapter_id, fields)
        conn.close()
        return redirect(url_for("admin_edit", chapter_id=chapter_id, saved=1))

    notices = db.get_notices(conn, chapter_id)
    values = db.get_values(conn, chapter_id)
    stats = db.get_stats(conn, chapter_id)
    links = db.get_links(conn, chapter_id)
    members = db.list_members(conn, chapter_id)
    conn.close()
    return render_template(
        "admin_edit.html",
        chapter=chapter,
        notices=notices,
        values=values,
        stats=stats,
        links=links,
        members=members,
        saved=request.args.get("saved"),
    )


@app.route("/admin/chapters/<int:chapter_id>/values/add", methods=["POST"])
@login_required
def admin_value_add(chapter_id):
    conn = db.get_conn()
    db.add_value(
        conn, chapter_id, request.form.get("title", "").strip(), request.form.get("body", "").strip()
    )
    conn.close()
    return redirect(url_for("admin_edit", chapter_id=chapter_id))


@app.route("/admin/chapters/<int:chapter_id>/values/<int:value_id>/delete", methods=["POST"])
@login_required
def admin_value_delete(chapter_id, value_id):
    conn = db.get_conn()
    db.delete_value(conn, value_id, chapter_id)
    conn.close()
    return redirect(url_for("admin_edit", chapter_id=chapter_id))


@app.route("/admin/chapters/<int:chapter_id>/notices/add", methods=["POST"])
@login_required
def admin_notice_add(chapter_id):
    conn = db.get_conn()
    db.add_notice(
        conn, chapter_id, request.form.get("title", "").strip(), request.form.get("body", "").strip()
    )
    conn.close()
    return redirect(url_for("admin_edit", chapter_id=chapter_id))


@app.route("/admin/chapters/<int:chapter_id>/notices/<int:notice_id>/delete", methods=["POST"])
@login_required
def admin_notice_delete(chapter_id, notice_id):
    conn = db.get_conn()
    db.delete_notice(conn, notice_id, chapter_id)
    conn.close()
    return redirect(url_for("admin_edit", chapter_id=chapter_id))


@app.route("/admin/chapters/<int:chapter_id>/stats/add", methods=["POST"])
@login_required
def admin_stat_add(chapter_id):
    conn = db.get_conn()
    db.add_stat(
        conn, chapter_id, request.form.get("num", "").strip(), request.form.get("label", "").strip()
    )
    conn.close()
    return redirect(url_for("admin_edit", chapter_id=chapter_id))


@app.route("/admin/chapters/<int:chapter_id>/stats/<int:stat_id>/delete", methods=["POST"])
@login_required
def admin_stat_delete(chapter_id, stat_id):
    conn = db.get_conn()
    db.delete_stat(conn, stat_id, chapter_id)
    conn.close()
    return redirect(url_for("admin_edit", chapter_id=chapter_id))


@app.route("/admin/chapters/<int:chapter_id>/links/add", methods=["POST"])
@login_required
def admin_link_add(chapter_id):
    conn = db.get_conn()
    db.add_link(
        conn, chapter_id, request.form.get("label", "").strip(), request.form.get("url", "").strip()
    )
    conn.close()
    return redirect(url_for("admin_edit", chapter_id=chapter_id))


@app.route("/admin/chapters/<int:chapter_id>/links/<int:link_id>/edit", methods=["POST"])
@login_required
def admin_link_edit(chapter_id, link_id):
    conn = db.get_conn()
    db.update_link(
        conn, link_id, chapter_id, request.form.get("label", "").strip(), request.form.get("url", "").strip()
    )
    conn.close()
    return redirect(url_for("admin_edit", chapter_id=chapter_id))


@app.route("/admin/chapters/<int:chapter_id>/links/<int:link_id>/delete", methods=["POST"])
@login_required
def admin_link_delete(chapter_id, link_id):
    conn = db.get_conn()
    db.delete_link(conn, link_id, chapter_id)
    conn.close()
    return redirect(url_for("admin_edit", chapter_id=chapter_id))


@app.route("/admin/chapters/<int:chapter_id>/members/<int:member_id>/delete", methods=["POST"])
@login_required
def admin_member_delete(chapter_id, member_id):
    conn = db.get_conn()
    db.delete_member(conn, member_id, chapter_id)
    conn.close()
    return redirect(url_for("admin_edit", chapter_id=chapter_id))


@app.route("/admin/chapters/<int:chapter_id>/members/<int:member_id>/edit", methods=["GET", "POST"])
@login_required
def admin_member_edit(chapter_id, member_id):
    conn = db.get_conn()
    chapter = db.get_chapter(conn, chapter_id)
    if not chapter:
        conn.close()
        abort(404)
    member = conn.execute(
        "SELECT * FROM chapter_members WHERE id = ? AND chapter_id = ?", (member_id, chapter_id)
    ).fetchone()
    if not member:
        conn.close()
        abort(404)

    if request.method == "GET":
        conn.close()
        saved = request.args.get("saved") == "1"
        return render_template(
            "admin_member_edit.html", chapter=chapter, member=member, error=None, form=None, saved=saved,
        )

    name = (request.form.get("name") or "").strip()
    company_title = (request.form.get("company_title") or "").strip()
    role_tag = (request.form.get("role_tag") or "").strip()
    bio = (request.form.get("bio") or "").strip()
    links = _extract_member_links(request.form)
    photo = request.files.get("photo")

    error = None
    if not name or not company_title or not bio:
        error = "姓名、公司/職稱、簡介都要填"

    filename = None
    if not error and photo and photo.filename:
        filename = _process_and_save_photo(photo)
        if not filename:
            error = "這張照片打不開，麻煩改存成 jpg 或 png 格式再上傳一次"

    if error:
        conn.close()
        return render_template(
            "admin_member_edit.html", chapter=chapter, member=member, error=error, saved=False,
            form={"name": name, "company_title": company_title, "role_tag": role_tag,
                  "bio": bio, **links},
        ), 400

    db.update_member(conn, member_id, name, company_title, role_tag, bio, links, filename)
    conn.close()
    return redirect(url_for("admin_member_edit", chapter_id=chapter_id, member_id=member_id, saved=1))


if __name__ == "__main__":
    port = int(os.environ.get("TEAM_PORT", 5073))
    app.run(host="0.0.0.0", port=port)

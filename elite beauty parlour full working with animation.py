from __future__ import annotations

import base64
import html
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

try:
    from google.cloud import firestore
except ImportError:
    firestore = None


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Elite Beauty Studio",
    page_icon="💎",
    layout="centered",
    initial_sidebar_state="collapsed",
)


# ============================================================
# CONFIGURATION
# ============================================================

SALON_NAME = "Elite Beauty Studio"
TAGLINE = "HIGH-END BEAUTY STUDIO"
SALON_ID = "elite-beauty-studio"

# Keep the same collection used by the existing system.
COLLECTION_NAME = "beauty_glow_feedback"

BASE_DIR = Path(__file__).resolve().parent

LOGO_FILE = BASE_DIR / "Logo.png"
AVATAR_LOGO_FILE = BASE_DIR / "avatar_logo.png"
AVATAR_BLINK_FILE = BASE_DIR / "avatar_blink.png"
STYLE_FILE = BASE_DIR / "style.css"


# ============================================================
# 7-DAY DEMO
# ============================================================

DEMO_START_DATE = os.getenv(
    "DEMO_START_DATE",
    "2026-09-10",
).strip()

try:
    DEMO_DAYS = int(
        os.getenv("DEMO_DAYS", "7")
    )
except (TypeError, ValueError):
    DEMO_DAYS = 7

if DEMO_DAYS < 1:
    DEMO_DAYS = 7


INDIA_TZ = timezone(
    timedelta(hours=5, minutes=30)
)

try:
    demo_start_date = datetime.strptime(
        DEMO_START_DATE,
        "%Y-%m-%d",
    ).date()
except ValueError:
    demo_start_date = datetime(
        2026,
        9,
        10,
    ).date()


DEMO_START_DATETIME = datetime(
    demo_start_date.year,
    demo_start_date.month,
    demo_start_date.day,
    tzinfo=INDIA_TZ,
)

DEMO_EXPIRES_AT = (
    DEMO_START_DATETIME
    + timedelta(days=DEMO_DAYS)
)

DEMO_LAST_DAY = (
    DEMO_EXPIRES_AT
    - timedelta(days=1)
).date()


def demo_is_active() -> bool:
    now = (
        datetime.now(timezone.utc)
        .astimezone(INDIA_TZ)
    )

    return now < DEMO_EXPIRES_AT


# ============================================================
# FEEDBACK OPTIONS
# ============================================================

SERVICE_OPTIONS = [
    ("✨ Skin Care", "Skin Care"),
    ("💇 Hair Spa & Styling", "Hair Spa & Styling"),
    ("💅 Manicure & Pedicure", "Manicure & Pedicure"),
    ("👰 Bridal Makeup", "Bridal Makeup"),
    ("🌸 Waxing & Threading", "Waxing & Threading"),
    ("🌿 Facial Treatment", "Facial Treatment"),
]


STAFF_OPTIONS = [
    "Friendly & Polite",
    "Skilled & Professional",
    "Attentive & Warm",
    "Excellent Care",
]


# ============================================================
# SESSION STATE
# ============================================================

def initialize_session() -> None:

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(
            uuid.uuid4()
        )

    if "completed" not in st.session_state:
        st.session_state.completed = False

    if "saved" not in st.session_state:
        st.session_state.saved = False

    if "save_started" not in st.session_state:
        st.session_state.save_started = False

    if "saved_record_id" not in st.session_state:
        st.session_state.saved_record_id = ""

    if "final_answers" not in st.session_state:
        st.session_state.final_answers = {}


initialize_session()


# ============================================================
# ASSET HELPERS
# ============================================================

@st.cache_data(show_spinner=False)
def image_to_data_uri(path_string: str):

    path = Path(path_string)

    if not path.exists():
        return None

    try:
        encoded = base64.b64encode(
            path.read_bytes()
        ).decode("utf-8")

        return (
            "data:image/png;base64,"
            + encoded
        )

    except Exception:
        return None


@st.cache_data(show_spinner=False)
def load_css(path_string: str) -> str:

    path = Path(path_string)

    if not path.exists():
        return ""

    try:
        return path.read_text(
            encoding="utf-8"
        )

    except Exception:
        return ""


LOGO_DATA = image_to_data_uri(
    str(LOGO_FILE)
)

AVATAR_LOGO_DATA = image_to_data_uri(
    str(AVATAR_LOGO_FILE)
)

AVATAR_BLINK_DATA = image_to_data_uri(
    str(AVATAR_BLINK_FILE)
)

CUSTOM_CSS = load_css(
    str(STYLE_FILE)
)


# ============================================================
# FIRESTORE
# ============================================================

@st.cache_resource
def get_firestore_client():

    if firestore is None:
        return None

    try:
        return firestore.Client()

    except Exception as exc:
        print(
            "Firestore initialization error:",
            exc,
        )

        return None


db = get_firestore_client()


# ============================================================
# BACKGROUND FIRESTORE WORKER
# ============================================================

# One small executor is enough.
#
# IMPORTANT:
# The customer-facing page NEVER waits for this executor.
#
# The final feedback screen is displayed immediately.
# Firestore saving happens independently.

SAVE_EXECUTOR = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="elite-feedback-save",
)


def save_feedback_background(
    feedback: dict,
) -> tuple[bool, str]:

    """
    Save feedback to Firestore.

    This function is intentionally executed in a
    background worker.

    There is NO document.get() here.

    A deterministic document ID is used so that the
    same submission can safely be retried without
    intentionally creating another document.
    """

    if db is None:
        print(
            "Firestore is unavailable."
        )
        return False, ""

    submission_id = str(
        feedback.get(
            "submission_id",
            "",
        )
    ).strip()

    if not submission_id:
        submission_id = (
            "EBS-"
            + uuid.uuid4().hex[:12].upper()
        )

    else:

        cleaned = "".join(
            ch
            for ch in submission_id.upper()
            if ch.isalnum()
            or ch in "-_"
        )

        submission_id = (
            "EBS-"
            + cleaned[:80]
        )

    try:

        document_ref = (
            db
            .collection(COLLECTION_NAME)
            .document(submission_id)
        )

        now_utc = datetime.now(
            timezone.utc
        )

        record = {
            "id": submission_id,

            "session_id": str(
                feedback.get(
                    "session_id",
                    "",
                )
            ),

            "salon_id": SALON_ID,

            "salon_name": SALON_NAME,

            "customer_name": str(
                feedback.get(
                    "customer_name",
                    "",
                )
            ).strip(),

            "beauty_service": str(
                feedback.get(
                    "beauty_service",
                    "",
                )
            ).strip(),

            "rating": int(
                feedback.get(
                    "rating",
                    0,
                )
            ),

            "staff_experience": str(
                feedback.get(
                    "staff_experience",
                    "",
                )
            ).strip(),

            "timestamp": now_utc,

            "formatted_time": (
                now_utc
                .astimezone(INDIA_TZ)
                .strftime(
                    "%B %d, %Y - %I:%M %p"
                )
            ),

            "created_at":
                now_utc.isoformat(),
        }

        # IMPORTANT:
        #
        # Direct set.
        #
        # NO .get()
        #
        # This is much faster than the old
        # get -> check -> set sequence.

        document_ref.set(
            record,
            merge=False,
        )

        print(
            "Firestore feedback saved:",
            submission_id,
        )

        return True, submission_id

    except Exception as exc:

        print(
            "Firestore background save error:",
            exc,
        )

        return False, ""


def start_background_save(
    feedback: dict,
) -> str:

    """
    Starts Firestore saving and immediately returns.

    The customer never waits for this function.
    """

    submission_id = str(
        feedback.get(
            "submission_id",
            "",
        )
    ).strip()

    if not submission_id:

        submission_id = (
            "EBS-"
            + uuid.uuid4().hex[:12].upper()
        )

        feedback = dict(feedback)
        feedback["submission_id"] = (
            submission_id
        )

    try:

        SAVE_EXECUTOR.submit(
            save_feedback_background,
            dict(feedback),
        )

        print(
            "Background Firestore save started:",
            submission_id,
        )

        return submission_id

    except Exception as exc:

        print(
            "Could not start background save:",
            exc,
        )

        return ""


# ============================================================
# RECEIVE FINAL SUBMISSION
# ============================================================

qp = st.query_params

final_submission = str(
    qp.get("submit", "")
).strip()

q_name = str(
    qp.get("customer_name", "")
).strip()

q_service = str(
    qp.get("beauty_service", "")
).strip()

q_rating = str(
    qp.get("rating", "")
).strip()

q_staff = str(
    qp.get("staff_experience", "")
).strip()

q_submission_id = str(
    qp.get("submission_id", "")
).strip()


# ============================================================
# FINAL SUBMISSION PROCESSING
# ============================================================

if (
    final_submission == "1"
    and not st.session_state.save_started
):

    try:
        rating_value = int(q_rating)

    except ValueError:
        rating_value = 0


    valid_submission = (
        demo_is_active()
        and bool(q_name)
        and bool(q_service)
        and 1 <= rating_value <= 5
        and bool(q_staff)
    )


    if valid_submission:

        if not q_submission_id:
            q_submission_id = (
                "ebs-"
                + uuid.uuid4().hex
            )


        feedback_record = {

            "submission_id":
                q_submission_id,

            "session_id":
                st.session_state.session_id,

            "customer_name":
                q_name,

            "beauty_service":
                q_service,

            "rating":
                rating_value,

            "staff_experience":
                q_staff,
        }


        # ====================================================
        # CRITICAL:
        #
        # Start Firestore save in background.
        #
        # DO NOT wait for result.
        # ====================================================

        record_id = start_background_save(
            feedback_record
        )


        st.session_state.save_started = True

        # We intentionally consider the feedback
        # submitted from the customer's point of view.
        #
        # Firestore is saving independently.

        st.session_state.saved = True

        st.session_state.saved_record_id = (
            record_id
            or q_submission_id
        )

        st.session_state.completed = True

        st.session_state.final_answers = {
            "customer_name": q_name,
            "beauty_service": q_service,
            "rating": rating_value,
            "staff_experience": q_staff,
        }


        # Remove query parameters.
        #
        # This is now only URL cleanup.
        # Firestore is already running in background.

        try:
            st.query_params.clear()

        except Exception:
            pass


# ============================================================
# EXPIRED DEMO
# ============================================================

if not demo_is_active():

    last_day_text = (
        DEMO_LAST_DAY.strftime(
            "%B %d, %Y"
        )
    )

    expiry_text = (
        DEMO_EXPIRES_AT.strftime(
            "%B %d, %Y at %I:%M %p IST"
        )
    )


    st.markdown(
        f"""
        <style>
        {CUSTOM_CSS}

        .elite-expired {{
            width:100%;
            max-width:620px;
            margin:40px auto;
            padding:35px 25px;
            border:1px solid #ecd2da;
            border-radius:18px;
            background:#fff;
            text-align:center;
            box-shadow:
                0 8px 25px
                rgba(116,65,80,.08);
        }}

        .expired-icon {{
            font-size:45px;
            margin-bottom:15px;
        }}

        .expired-title {{
            color:#472730;
            font-family:
                Georgia,
                serif;
            font-size:28px;
            font-weight:700;
            margin-bottom:10px;
        }}

        .expired-desc {{
            color:#76545e;
            font-size:13px;
            line-height:1.6;
        }}

        .expired-box {{
            margin-top:20px;
            border:1px solid #efd7df;
            border-radius:13px;
            overflow:hidden;
            text-align:left;
        }}

        .expired-row {{
            display:flex;
            justify-content:space-between;
            gap:15px;
            padding:12px;
            border-bottom:1px solid #f0e0e5;
            color:#8a6c74;
            font-size:11px;
        }}

        .expired-row:last-child {{
            border-bottom:0;
        }}

        .expired-row strong {{
            color:#542b37;
        }}
        </style>

        <div class="elite-expired">

            <div class="expired-icon">
                🔒
            </div>

            <div class="expired-title">
                Demo Period Expired
            </div>

            <div class="expired-desc">
                This 7-day demonstration ended
                after
                <strong>
                    {html.escape(last_day_text)}
                </strong>.
            </div>

            <div class="expired-box">

                <div class="expired-row">
                    <span>Last usable day</span>
                    <strong>
                        {html.escape(last_day_text)}
                    </strong>
                </div>

                <div class="expired-row">
                    <span>Access ended</span>
                    <strong>
                        {html.escape(expiry_text)}
                    </strong>
                </div>

            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    st.stop()


# ============================================================
# HTML HELPERS
# ============================================================

def esc(value: str) -> str:
    return html.escape(
        str(value),
        quote=True,
    )


def js_json(value: str) -> str:

    return (
        value
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace(
            "${",
            "\\${",
        )
    )


# ============================================================
# IMAGE HTML
# ============================================================

logo_html = (

    f'<img '
    f'src="{esc(LOGO_DATA)}" '
    f'alt="Elite Beauty Studio">'

    if LOGO_DATA

    else
    '<div class="logo-fallback">'
    'EBS'
    '</div>'
)


avatar_normal = (

    f'<img '
    f'class="avatar-normal" '
    f'src="{esc(AVATAR_LOGO_DATA)}" '
    f'alt="Beauty Assistant">'

    if AVATAR_LOGO_DATA

    else
    '<div class="avatar-fallback">'
    '💕'
    '</div>'
)


avatar_blink = (

    f'<img '
    f'class="avatar-blink" '
    f'src="{esc(AVATAR_BLINK_DATA)}" '
    f'alt="Beauty Assistant">'

    if AVATAR_BLINK_DATA

    else ""
)


# ============================================================
# SERVICE BUTTONS
# ============================================================

service_buttons = "".join(

    f'''
    <button
        class="quick-btn"
        data-service="{esc(value)}"
        type="button"
    >
        {esc(label)}
    </button>
    '''

    for label, value in SERVICE_OPTIONS
)


# ============================================================
# STAFF BUTTONS
# ============================================================

staff_buttons = "".join(

    f'''
    <button
        class="quick-btn"
        data-staff="{esc(option)}"
        type="button"
    >
        {esc(option)}
    </button>
    '''

    for option in STAFF_OPTIONS
)


# ============================================================
# DEMO TEXT
# ============================================================

last_day_text = (
    DEMO_LAST_DAY.strftime(
        "%B %d, %Y"
    )
)

expiry_text = (
    DEMO_EXPIRES_AT.strftime(
        "%B %d, %Y at %I:%M %p IST"
    )
)


# ============================================================
# FAST FRONTEND CSS
# ============================================================

FRONTEND_CSS = r"""

.elite-fast-root {
    width:100%;
    max-width:620px;
    margin:0 auto;
    color:#332226;
    font-family:
        "Plus Jakarta Sans",
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
}

.elite-fast-root * {
    box-sizing:border-box;
}


.elite-fast-brand {
    display:flex;
    align-items:center;
    gap:15px;
    margin-bottom:15px;
    padding-bottom:14px;
    border-bottom:1px solid #edd9d1;
}


.elite-fast-logo {
    width:82px;
    height:82px;
    min-width:82px;
    overflow:hidden;

    display:flex;
    align-items:center;
    justify-content:center;

    border:1px solid #e4c4ae;
    border-radius:18px;

    background:#fbf6ee;

    box-shadow:
        0 7px 20px
        rgba(151,105,68,.10);
}


.elite-fast-logo img {
    width:100%;
    height:100%;
    object-fit:contain;
    display:block;
}


.elite-fast-logo .logo-fallback {
    font-family:Georgia,serif;
    font-size:28px;
    font-weight:700;
    color:#a47c4a;
}


.elite-fast-name {
    color:#3a2028;
    font-family:
        "Cormorant Garamond",
        Georgia,
        serif;

    font-size:30px;
    font-weight:700;
    line-height:1;
    letter-spacing:.5px;
}


.elite-fast-tagline {
    margin-top:5px;
    color:#a47c4a;

    font-family:
        "Cormorant Garamond",
        Georgia,
        serif;

    font-size:13px;
    font-weight:700;

    line-height:1;
    letter-spacing:3px;
}


.elite-fast-pill {
    display:inline-flex;
    align-items:center;
    gap:7px;

    margin-top:9px;
    padding:6px 11px;

    border:1px solid #e8b7c6;
    border-radius:999px;

    background:#fff0f4;
    color:#a8405d;

    font-size:10.5px;
    font-weight:700;
}


.elite-fast-dot {
    width:8px;
    height:8px;

    border-radius:50%;

    background:#27ae60;

    box-shadow:
        0 0 0 3px #e8f7ef;
}


.elite-fast-intro {
    margin:14px 0;
}


.elite-fast-intro-title {
    color:#472730;
    font-size:15px;
    font-weight:700;
    line-height:1.4;
}


.elite-fast-intro-sub {
    margin-top:4px;
    color:#76545e;
    font-size:12px;
    line-height:1.5;
}


.elite-fast-demo {
    width:100%;

    padding:10px 13px;
    margin:0 0 14px;

    border:1px solid #edc1cd;
    border-radius:13px;

    background:
        linear-gradient(
            135deg,
            #fff7fa,
            #fffaf4
        );

    color:#6f4652;

    font-size:10.5px;
    line-height:1.5;
    text-align:center;

    box-shadow:
        0 5px 14px
        rgba(121,67,82,.045);
}


.elite-fast-demo strong {
    color:#8e3f5b;
}


.elite-fast-sound {
    display:flex;
    align-items:center;
    justify-content:space-between;

    margin:0 0 14px;

    color:#8a7078;
    font-size:11px;
}


.sound-toggle {
    width:42px;
    height:38px;

    border:1px solid #e1d0d6;
    border-radius:9px;

    background:#fff;

    cursor:pointer;
    font-size:17px;

    box-shadow:
        0 3px 10px
        rgba(121,67,82,.05);
}


.sound-toggle:active {
    transform:scale(.97);
}


.elite-fast-progress {
    padding:12px 13px 13px;
    margin-bottom:14px;

    border:1px solid #ecd0d8;
    border-radius:14px;

    background:#fff;

    box-shadow:
        0 5px 15px
        rgba(121,67,82,.055);
}


.progress-top {
    display:flex;
    justify-content:space-between;
    align-items:center;

    gap:10px;

    margin-bottom:8px;

    color:#63404a;

    font-size:11px;
    font-weight:700;
}


.progress-status {
    padding:5px 9px;

    border:1px solid #bce7d2;
    border-radius:7px;

    background:#effbf5;
    color:#189967;

    font-size:10px;
}


.progress-track {
    width:100%;
    height:6px;

    overflow:hidden;

    border-radius:999px;

    background:#f0dce2;
}


.progress-fill {
    height:100%;

    border-radius:999px;

    background:
        linear-gradient(
            90deg,
            #b96c83,
            #d67893,
            #d2a06e
        );

    transition:
        width .25s ease;
}


.elite-fast-chat {
    width:100%;
    height:440px;

    overflow-x:hidden;
    overflow-y:auto;

    padding:17px 13px 22px 12px;

    border:1px solid #eccdd6;
    border-radius:16px;

    background:#fff;

    box-shadow:
        0 7px 20px
        rgba(116,65,80,.075);

    margin-bottom:14px;

    scroll-behavior:smooth;
    overscroll-behavior:contain;

    scrollbar-width:thin;
    scrollbar-color:
        #d89bad
        #fbf0f3;
}


.elite-fast-chat::-webkit-scrollbar {
    width:8px;
}


.elite-fast-chat::-webkit-scrollbar-track {
    margin:8px 1px;

    background:#fbf0f3;

    border-radius:999px;
}


.elite-fast-chat::-webkit-scrollbar-thumb {
    background:
        linear-gradient(
            180deg,
            #e1a5b6,
            #ce849c
        );

    border:1px solid #fff;

    border-radius:999px;
}


.chat-row {
    display:flex;
    width:100%;

    margin-bottom:16px;

    animation:
        fastMessageIn
        .22s
        ease-out;
}


.chat-row.ai {
    justify-content:flex-start;
    align-items:flex-end;
    gap:8px;
}


.chat-row.user {
    justify-content:flex-end;
}


.fast-avatar {
    position:relative;

    width:38px;
    height:38px;
    min-width:38px;

    overflow:hidden;

    border-radius:50%;
    border:1px solid #e5b8c5;

    background:#fff6f8;

    box-shadow:
        0 4px 12px
        rgba(130,67,88,.12);
}


.fast-avatar img {
    position:absolute;

    inset:0;

    width:100%;
    height:100%;

    object-fit:cover;

    display:block;
}


.fast-avatar .avatar-normal {
    opacity:1;

    animation:
        avatarNormalFast
        3.8s
        infinite;
}


.fast-avatar .avatar-blink {
    opacity:0;

    animation:
        avatarBlinkFast
        3.8s
        infinite;
}


.chat-bubble {
    position:relative;

    max-width:82%;

    padding:12px 13px 21px;

    font-size:14px;
    line-height:1.55;

    word-break:break-word;
}


.chat-bubble.ai {
    color:#40262f;

    background:
        linear-gradient(
            135deg,
            #fffafb,
            #fcf5f7
        );

    border:1px solid #efd6de;

    border-radius:
        7px 17px 17px 17px;

    box-shadow:
        0 2px 7px
        rgba(112,61,77,.035);
}


.chat-bubble.user {
    color:#421d28;

    background:
        linear-gradient(
            135deg,
            #fdf0f4,
            #fbe2ea
        );

    border:1px solid #efc4d0;

    border-radius:
        17px 7px 17px 17px;

    box-shadow:
        0 3px 8px
        rgba(112,61,77,.055);
}


.bubble-symbol {
    color:#cb5f7d;
    margin-right:6px;
    font-weight:700;
}


.chat-time {
    position:absolute;

    right:10px;
    bottom:5px;

    color:#b18a94;

    font-size:8px;
    line-height:1;
}


.typing-row {
    display:flex;
    align-items:flex-end;

    gap:8px;

    margin-bottom:16px;
}


.typing-bubble {
    padding:12px 14px;

    border:1px solid #efd6de;

    border-radius:
        7px 17px 17px 17px;

    background:#fffafb;
}


.typing-dots {
    display:flex;
    gap:4px;
    align-items:center;

    height:16px;
}


.typing-dot {
    width:6px;
    height:6px;

    border-radius:50%;

    background:#c96d87;

    animation:
        fastDot
        1s
        infinite;
}


.typing-dot:nth-child(2) {
    animation-delay:.14s;
}


.typing-dot:nth-child(3) {
    animation-delay:.28s;
}


.elite-fast-input {
    width:100%;

    padding:14px;
    margin-bottom:12px;

    border:1px solid #ecd2da;
    border-radius:15px;

    background:#fff;

    box-shadow:
        0 5px 14px
        rgba(121,67,82,.045);
}


.input-title {
    text-align:center;

    color:#603b47;

    font-size:13px;
    font-weight:700;
    line-height:1.45;
}


.input-hint {
    margin:4px 0 10px;

    text-align:center;

    color:#886770;

    font-size:11px;
    line-height:1.5;
}


.fast-text-input {
    width:100%;

    min-height:48px;

    padding:10px 14px;

    border:1px solid #e7c7d0;
    border-radius:11px;

    background:#fffafb;

    color:#43242d;

    font:
        14px
        "Plus Jakarta Sans",
        sans-serif;

    outline:none;
}


.fast-text-input:focus {
    border-color:#d47792;

    box-shadow:
        0 0 0 3px
        rgba(212,119,146,.10);

    background:#fff;
}


.fast-primary {
    width:100%;

    min-height:46px;

    padding:10px 12px;

    margin-top:8px;

    border:0;
    border-radius:11px;

    cursor:pointer;

    background:
        linear-gradient(
            135deg,
            #d56c88,
            #b94968
        );

    color:#fff;

    font:
        700
        12px
        "Plus Jakarta Sans",
        sans-serif;

    box-shadow:
        0 6px 16px
        rgba(185,73,104,.19);
}


.fast-primary:active {
    transform:scale(.99);
}


.quick-grid {
    display:grid;

    grid-template-columns:
        1fr 1fr;

    gap:7px;
}


.rating-grid {
    display:grid;

    grid-template-columns:
        repeat(5,1fr);

    gap:6px;
}


.quick-btn {
    min-height:46px;

    padding:10px 8px;

    border:1px solid #e2b4c2;
    border-radius:11px;

    background:#fcedf2;

    color:#4b1f2b;

    cursor:pointer;

    font:
        650
        12px
        "Plus Jakarta Sans",
        sans-serif;

    line-height:1.3;

    transition:
        transform .12s ease,
        background .12s ease;
}


.quick-btn:hover {
    transform:translateY(-1px);
    background:#f8dfe7;
}


.quick-btn:active {
    transform:scale(.99);
}


.fast-other {
    margin-top:8px;
}


.elite-fast-complete {
    padding:28px 16px 20px;

    margin-bottom:12px;

    border:1px solid #ecd2da;
    border-radius:17px;

    background:#fff;

    box-shadow:
        0 7px 20px
        rgba(116,65,80,.075);

    text-align:center;

    animation:
        completeIn
        .25s
        ease-out;
}


.fast-check {
    width:58px;
    height:58px;

    margin:0 auto 12px;

    display:flex;
    align-items:center;
    justify-content:center;

    border:2px solid #e8afc0;
    border-radius:50%;

    background:#fff4f7;

    font-size:27px;
}


.fast-thank {
    color:#472730;

    font-family:
        "Cormorant Garamond",
        Georgia,
        serif;

    font-size:27px;
    font-weight:700;
}


.fast-desc {
    margin:7px 0 17px;

    color:#76545e;

    font-size:11px;
    line-height:1.55;
}


.fast-summary {
    border:1px solid #efd7df;
    border-radius:13px;

    overflow:hidden;

    text-align:left;
}


.fast-summary-row {
    display:flex;

    justify-content:space-between;

    gap:15px;

    padding:11px 12px;

    border-bottom:
        1px solid #f0e0e5;

    color:#8a6c74;

    font-size:11px;
}


.fast-summary-row:last-child {
    border-bottom:0;
}


.fast-summary-row .value {
    color:#542b37;

    font-weight:700;

    text-align:right;
}


.fast-saved {
    margin:8px 0 12px;

    padding:10px;

    border:1px solid #bce7d2;
    border-radius:10px;

    background:#effbf5;

    color:#168b5d;

    text-align:center;

    font-size:11px;
    font-weight:700;
}


.fast-footer {
    padding:18px 0 24px;

    border-top:1px solid #ead8dd;

    color:#9a7b84;

    text-align:center;

    font-size:10px;

    line-height:1.8;
}


.fast-footer strong {
    color:#70414e;
}


@keyframes fastMessageIn {

    from {
        opacity:0;
        transform:translateY(4px);
    }

    to {
        opacity:1;
        transform:translateY(0);
    }

}


@keyframes completeIn {

    from {
        opacity:0;
        transform:translateY(7px)
        scale(.99);
    }

    to {
        opacity:1;
        transform:translateY(0)
        scale(1);
    }

}


@keyframes fastDot {

    0%,60%,100% {
        transform:translateY(0);
        opacity:.45;
    }

    30% {
        transform:translateY(-4px);
        opacity:1;
    }

}


@keyframes avatarNormalFast {

    0%,86%,100% {
        opacity:1;
    }

    90%,96% {
        opacity:0;
    }

}


@keyframes avatarBlinkFast {

    0%,86%,100% {
        opacity:0;
    }

    90%,96% {
        opacity:1;
    }

}


@media (max-width:650px) {

    .elite-fast-brand {
        gap:10px;
    }

    .elite-fast-logo {
        width:70px;
        height:70px;
        min-width:70px;
        border-radius:15px;
    }

    .elite-fast-name {
        font-size:24px;
    }

    .elite-fast-tagline {
        font-size:11px;
        letter-spacing:2px;
    }

    .elite-fast-chat {
        height:400px;
    }

    .chat-bubble {
        max-width:90%;
        font-size:12.5px;
    }

    .quick-btn {
        min-height:48px;
        font-size:12px;
    }

}
"""


# ============================================================
# MAIN FRONTEND HTML
# ============================================================

HTML = f"""
<style>

{CUSTOM_CSS}

{FRONTEND_CSS}

</style>


<div
    class="elite-fast-root"
    id="elite-fast-root"
>


    <!-- BRAND -->

    <div class="elite-fast-brand">

        <div class="elite-fast-logo">
            {logo_html}
        </div>


        <div>

            <div class="elite-fast-name">
                Elite Beauty Studio
            </div>

            <div class="elite-fast-tagline">
                HIGH-END BEAUTY STUDIO
            </div>

            <div class="elite-fast-pill">

                <span
                    class="elite-fast-dot"
                ></span>

                AI Customer Feedback Assistant

            </div>

        </div>

    </div>


    <!-- INTRO -->

    <div class="elite-fast-intro">

        <div class="elite-fast-intro-title">
            Your experience matters to us. 💕
        </div>

        <div class="elite-fast-intro-sub">
            Take a moment to share your thoughts.
            It only takes a few seconds.
        </div>

    </div>


    <!-- DEMO -->

    <div class="elite-fast-demo">

        ⏳
        <strong>
            7-Day Demo Active
        </strong>

        • Available through

        <strong>
            {esc(last_day_text)}
        </strong>

        • Access ends automatically on

        <strong>
            {esc(expiry_text)}
        </strong>

    </div>


    <!-- SOUND -->

    <div class="elite-fast-sound">

        <span>
            🔔 Soft glass chime for assistant replies
        </span>

        <button
            class="sound-toggle"
            id="sound-toggle"
            type="button"
            aria-label="Toggle assistant sound"
        >
            🔊
        </button>

    </div>


    <!-- PROGRESS -->

    <div class="elite-fast-progress">

        <div class="progress-top">

            <span>
                Feedback journey
            </span>

            <span
                class="progress-status"
                id="progress-status"
            >
                0%
            </span>

        </div>


        <div class="progress-track">

            <div
                class="progress-fill"
                id="progress-fill"
                style="width:0%"
            ></div>

        </div>

    </div>


    <!-- CHAT -->

    <div
        class="elite-fast-chat"
        id="elite-fast-chat"
    ></div>


    <!-- INPUT -->

    <div
        id="elite-fast-input"
    ></div>


    <!-- FOOTER -->

    <div class="fast-footer">

        ✨<br>

        <strong>
            Powered by Elite Beauty Studio AI
        </strong>

        <br>

        🛡️ Your feedback is securely recorded.

    </div>


</div>


<script>

(function(){{

    const root =
        document.getElementById(
            'elite-fast-root'
        );


    const chat =
        document.getElementById(
            'elite-fast-chat'
        );


    const input =
        document.getElementById(
            'elite-fast-input'
        );


    const progressFill =
        document.getElementById(
            'progress-fill'
        );


    const progressStatus =
        document.getElementById(
            'progress-status'
        );


    const soundButton =
        document.getElementById(
            'sound-toggle'
        );


    const avatarNormal =
        `{js_json(avatar_normal)}`;


    const avatarBlink =
        `{js_json(avatar_blink)}`;


    let soundEnabled = true;

    let step = 1;

    let busy = false;


    let answers = {{

        customer_name: '',

        beauty_service: '',

        rating: 0,

        staff_experience: ''

    }};


    const welcome =
        "Welcome to Elite Beauty Studio! 💕 I'm your Beauty Feedback Assistant. I'd love to hear about your experience.";


    // ========================================================
    // TIME
    // ========================================================

    function nowTime(){{

        return new Intl.DateTimeFormat(
            'en-IN',
            {{
                hour:'numeric',
                minute:'2-digit',
                hour12:true
            }}
        ).format(new Date());

    }}


    // ========================================================
    // SCROLL
    // ========================================================

    function scrollChat(){{

        chat.scrollTop =
            chat.scrollHeight;

    }}


    // ========================================================
    // SOUND
    // ========================================================

    function playChime(){{

        if (!soundEnabled) return;

        try {{

            const AudioCtx =
                window.AudioContext ||
                window.webkitAudioContext;


            if (!AudioCtx) return;


            const ctx =
                new AudioCtx();


            const gain =
                ctx.createGain();


            gain.connect(
                ctx.destination
            );


            const osc1 =
                ctx.createOscillator();


            const osc2 =
                ctx.createOscillator();


            osc1.type = 'sine';

            osc2.type = 'sine';


            osc1.frequency.setValueAtTime(
                1046.5,
                ctx.currentTime
            );


            osc2.frequency.setValueAtTime(
                1568.0,
                ctx.currentTime + 0.035
            );


            gain.gain.setValueAtTime(
                0.0001,
                ctx.currentTime
            );


            gain.gain.exponentialRampToValueAtTime(
                0.055,
                ctx.currentTime + 0.018
            );


            gain.gain.exponentialRampToValueAtTime(
                0.0001,
                ctx.currentTime + 0.48
            );


            osc1.connect(gain);

            osc2.connect(gain);


            osc1.start();

            osc2.start(
                ctx.currentTime + 0.035
            );


            osc1.stop(
                ctx.currentTime + 0.5
            );


            osc2.stop(
                ctx.currentTime + 0.52
            );


            setTimeout(
                () => {{
                    try {{
                        ctx.close();
                    }} catch(e) {{}}
                }},
                650
            );

        }} catch(e) {{}}

    }}


    soundButton.addEventListener(
        'click',
        function(){{

            soundEnabled =
                !soundEnabled;


            soundButton.textContent =
                soundEnabled
                ? '🔊'
                : '🔇';


            if (soundEnabled) {{
                playChime();
            }}

        }}
    );


    // ========================================================
    // MESSAGE
    // ========================================================

    function addMessage(
        sender,
        text,
        playSound
    ){{

        const row =
            document.createElement(
                'div'
            );


        row.className =
            'chat-row '
            + (
                sender === 'ai'
                ? 'ai'
                : 'user'
            );


        const bubble =
            document.createElement(
                'div'
            );


        bubble.className =
            'chat-bubble '
            + (
                sender === 'ai'
                ? 'ai'
                : 'user'
            );


        const symbol =
            document.createElement(
                'span'
            );


        symbol.className =
            'bubble-symbol';


        symbol.textContent =
            sender === 'ai'
            ? '✦'
            : '';


        const message =
            document.createElement(
                'span'
            );


        message.textContent =
            text;


        const time =
            document.createElement(
                'span'
            );


        time.className =
            'chat-time';


        time.textContent =
            nowTime();


        if (sender === 'ai'){{

            const avatar =
                document.createElement(
                    'div'
                );


            avatar.className =
                'fast-avatar';


            avatar.innerHTML =
                avatarNormal
                + avatarBlink;


            row.appendChild(
                avatar
            );


            bubble.appendChild(
                symbol
            );


            bubble.appendChild(
                message
            );


            bubble.appendChild(
                time
            );


            row.appendChild(
                bubble
            );

        }} else {{

            bubble.appendChild(
                message
            );


            const heart =
                document.createElement(
                    'span'
                );


            heart.textContent =
                ' ♡';


            bubble.appendChild(
                heart
            );


            bubble.appendChild(
                time
            );


            row.appendChild(
                bubble
            );

        }}


        chat.appendChild(
            row
        );


        scrollChat();


        if (
            sender === 'ai'
            && playSound
        ) {{

            playChime();

        }}

    }}


    // ========================================================
    // TYPING
    // ========================================================

    function showTyping(){{

        const row =
            document.createElement(
                'div'
            );


        row.className =
            'typing-row';


        row.id =
            'fast-typing';


        const avatar =
            document.createElement(
                'div'
            );


        avatar.className =
            'fast-avatar';


        avatar.innerHTML =
            avatarNormal
            + avatarBlink;


        const bubble =
            document.createElement(
                'div'
            );


        bubble.className =
            'typing-bubble';


        bubble.innerHTML =
            '<div class="typing-dots">'
            + '<span class="typing-dot"></span>'
            + '<span class="typing-dot"></span>'
            + '<span class="typing-dot"></span>'
            + '</div>';


        row.appendChild(
            avatar
        );


        row.appendChild(
            bubble
        );


        chat.appendChild(
            row
        );


        scrollChat();

    }}


    function hideTyping(){{

        const el =
            document.getElementById(
                'fast-typing'
            );


        if (el) {{
            el.remove();
        }}

    }}


    // ========================================================
    // FAST AI REPLY
    // ========================================================

    function reply(
        text,
        next
    ){{

        busy = true;

        clearInput();

        showTyping();


        // ONLY 280ms.
        //
        // There is NO network call here.
        //
        // This is intentionally short.

        setTimeout(
            function(){{

                hideTyping();

                addMessage(
                    'ai',
                    text,
                    true
                );

                busy = false;


                if (next) {{
                    next();
                }}

            }},
            280
        );

    }}


    // ========================================================
    // PROGRESS
    // ========================================================

    function setProgress(
        value,
        label
    ){{

        progressFill.style.width =
            value + '%';


        progressStatus.textContent =
            label ||
            (value + '%');

    }}


    // ========================================================
    // INPUT
    // ========================================================

    function clearInput(){{

        input.innerHTML = '';

    }}


    function renderInput(
        title,
        hint
    ){{

        input.innerHTML =

            '<div class="elite-fast-input">'
            + '<div class="input-title">'
            + title
            + '</div>'
            + '<div class="input-hint">'
            + hint
            + '</div>'
            + '</div>';

    }}


    // ========================================================
    // NAME
    // ========================================================

    function renderName(){{

        setProgress(
            0,
            '0%'
        );


        renderInput(
            'Please enter your name',
            "We'd love to know who we're thanking. 💕"
        );


        const card =
            input.querySelector(
                '.elite-fast-input'
            );


        card.insertAdjacentHTML(
            'beforeend',

            '<input '
            + 'id="fast-name" '
            + 'class="fast-text-input" '
            + 'type="text" '
            + 'maxlength="80" '
            + 'autocomplete="name" '
            + 'placeholder="Enter your name">'
            + '<button '
            + 'id="fast-name-btn" '
            + 'class="fast-primary" '
            + 'type="button">'
            + 'Continue →'
            + '</button>'
        );


        const field =
            document.getElementById(
                'fast-name'
            );


        /*
         * IMPORTANT: Do NOT autofocus the name field here.
         *
         * Streamlit renders this component inside an iframe.
         * Autofocusing an input near the bottom of the component
         * can make the browser scroll the whole customer page down
         * to the input, hiding the welcome/header section.
         *
         * The customer can tap the field normally. After Continue,
         * only the internal chat area is scrolled by scrollChat().
         */


        document
            .getElementById(
                'fast-name-btn'
            )
            .addEventListener(
                'click',
                submitName
            );


        field.addEventListener(
            'keydown',
            e => {{

                if (
                    e.key === 'Enter'
                ) {{

                    submitName();

                }}

            }}
        );

    }}


    function submitName(){{

        if (busy) return;


        const field =
            document.getElementById(
                'fast-name'
            );


        const name =
            field
            ? field.value.trim()
            : '';


        if (!name) {{

            if (field) {{
                field.focus();
            }}

            return;

        }}


        answers.customer_name =
            name;


        addMessage(
            'user',
            name,
            false
        );


        step = 2;


        const firstName =
            name
                .split(/\s+/)[0]
                .replace(
                    /^./,
                    c => c.toUpperCase()
                );


        reply(

            'Lovely to meet you, '
            + firstName
            + '! 💕 Which beauty service did you receive today?',

            renderService

        );

    }}


    // ========================================================
    // SERVICE
    // ========================================================

    function renderService(){{

        setProgress(
            25,
            '25%'
        );


        renderInput(
            'Which beauty service did you receive?',
            'Tap a service below or enter another service.'
        );


        const card =
            input.querySelector(
                '.elite-fast-input'
            );


        card.insertAdjacentHTML(
            'beforeend',

            '<div class="quick-grid">'
            + `{service_buttons}`
            + '</div>'

            + '<div class="fast-other">'

            + '<input '
            + 'id="fast-other-service" '
            + 'class="fast-text-input" '
            + 'type="text" '
            + 'maxlength="100" '
            + 'placeholder="Or type another service...">'

            + '<button '
            + 'id="fast-other-service-btn" '
            + 'class="fast-primary" '
            + 'type="button">'
            + 'Continue →'
            + '</button>'

            + '</div>'
        );


        card
            .querySelectorAll(
                '[data-service]'
            )
            .forEach(
                btn => btn.addEventListener(
                    'click',
                    function(){{

                        submitService(
                            this.getAttribute(
                                'data-service'
                            )
                        );

                    }}
                )
            );


        document
            .getElementById(
                'fast-other-service-btn'
            )
            .addEventListener(
                'click',
                function(){{

                    const v =
                        document
                            .getElementById(
                                'fast-other-service'
                            )
                            .value
                            .trim();


                    if (v) {{
                        submitService(v);
                    }}

                }}
            );

    }}


    function serviceReply(
        service
    ){{

        const s =
            service.toLowerCase();


        if (
            s.includes('facial')
        ) {{

            return (
                'That sounds wonderfully relaxing! 🌿 '
                + 'How would you rate your experience from 1 to 5?'
            );

        }}


        if (
            s.includes('hair')
        ) {{

            return (
                'Beautiful choice! ✨ '
                + 'How would you rate your experience from 1 to 5?'
            );

        }}


        if (
            s.includes('bridal')
        ) {{

            return (
                'How exciting! 👰✨ '
                + 'How would you rate your experience from 1 to 5?'
            );

        }}


        if (
            s.includes('manicure')
            || s.includes('pedicure')
        ) {{

            return (
                'Lovely! 💅 '
                + 'How would you rate your experience from 1 to 5?'
            );

        }}


        if (
            s.includes('skin')
        ) {{

            return (
                'Wonderful choice for a little self-care. 🌸 '
                + 'How would you rate your experience from 1 to 5?'
            );

        }}


        if (
            s.includes('waxing')
            || s.includes('threading')
        ) {{

            return (
                'Thank you for sharing! 🌷 '
                + 'How would you rate your experience from 1 to 5?'
            );

        }}


        return (
            'Thank you for choosing '
            + service
            + '! ✨ '
            + 'How would you rate your experience from 1 to 5?'
        );

    }}


    function submitService(
        service
    ){{

        if (
            busy
            || !service
        ) return;


        answers.beauty_service =
            service;


        addMessage(
            'user',
            service,
            false
        );


        step = 3;


        reply(
            serviceReply(service),
            renderRating
        );

    }}


    // ========================================================
    // RATING
    // ========================================================

    function renderRating(){{

        setProgress(
            50,
            '50%'
        );


        renderInput(
            'How would you rate your experience?',
            'Tap one rating from 1 to 5 stars.'
        );


        const card =
            input.querySelector(
                '.elite-fast-input'
            );


        card.insertAdjacentHTML(
            'beforeend',

            '<div class="rating-grid">'

            + '<button '
            + 'class="quick-btn" '
            + 'data-rating="1" '
            + 'type="button">'
            + '1 ⭐'
            + '</button>'

            + '<button '
            + 'class="quick-btn" '
            + 'data-rating="2" '
            + 'type="button">'
            + '2 ⭐'
            + '</button>'

            + '<button '
            + 'class="quick-btn" '
            + 'data-rating="3" '
            + 'type="button">'
            + '3 ⭐'
            + '</button>'

            + '<button '
            + 'class="quick-btn" '
            + 'data-rating="4" '
            + 'type="button">'
            + '4 ⭐'
            + '</button>'

            + '<button '
            + 'class="quick-btn" '
            + 'data-rating="5" '
            + 'type="button">'
            + '5 ⭐'
            + '</button>'

            + '</div>'
        );


        card
            .querySelectorAll(
                '[data-rating]'
            )
            .forEach(
                btn => btn.addEventListener(
                    'click',
                    function(){{

                        submitRating(
                            Number(
                                this.getAttribute(
                                    'data-rating'
                                )
                            )
                        );

                    }}
                )
            );

    }}


    function ratingReply(
        rating
    ){{

        if (rating === 5) {{

            return (
                'Wow, thank you for the wonderful '
                + '5-star rating! ⭐⭐⭐⭐⭐ '
                + 'How would you describe the experience of our staff?'
            );

        }}


        if (rating === 4) {{

            return (
                'Thank you for the great rating! 💕 '
                + 'How would you describe the experience of our staff?'
            );

        }}


        if (rating === 3) {{

            return (
                'Thank you for your honest feedback. 🌸 '
                + 'How would you describe the experience of our staff?'
            );

        }}


        if (rating === 2) {{

            return (
                'Thank you for being honest with us. 💗 '
                + 'Your feedback helps us improve. '
                + 'How would you describe the experience of our staff?'
            );

        }}


        return (
            'Thank you for sharing honestly. 💗 '
            + 'Your feedback is very important to us. '
            + 'How would you describe the experience of our staff?'
        );

    }}


    function submitRating(
        rating
    ){{

        if (busy) return;


        answers.rating =
            rating;


        addMessage(
            'user',
            rating + ' out of 5 ⭐',
            false
        );


        step = 4;


        reply(
            ratingReply(rating),
            renderStaff
        );

    }}


    // ========================================================
    // STAFF
    // ========================================================

    function renderStaff(){{

        setProgress(
            75,
            '75%'
        );


        renderInput(
            'How would you describe our staff?',
            'Choose the response that best matches your experience.'
        );


        const card =
            input.querySelector(
                '.elite-fast-input'
            );


        card.insertAdjacentHTML(
            'beforeend',

            '<div class="quick-grid">'
            + `{staff_buttons}`
            + '</div>'

            + '<div class="fast-other">'

            + '<input '
            + 'id="fast-other-staff" '
            + 'class="fast-text-input" '
            + 'type="text" '
            + 'maxlength="160" '
            + 'placeholder="Or type your own feedback...">'

            + '<button '
            + 'id="fast-other-staff-btn" '
            + 'class="fast-primary" '
            + 'type="button">'
            + 'Finish Feedback →'
            + '</button>'

            + '</div>'
        );


        card
            .querySelectorAll(
                '[data-staff]'
            )
            .forEach(
                btn => btn.addEventListener(
                    'click',
                    function(){{

                        submitStaff(
                            this.getAttribute(
                                'data-staff'
                            )
                        );

                    }}
                )
            );


        document
            .getElementById(
                'fast-other-staff-btn'
            )
            .addEventListener(
                'click',
                function(){{

                    const v =
                        document
                            .getElementById(
                                'fast-other-staff'
                            )
                            .value
                            .trim();


                    if (v) {{
                        submitStaff(v);
                    }}

                }}
            );

    }}


    // ========================================================
    // FINAL STAFF SUBMISSION
    // ========================================================

    function submitStaff(
        staff
    ){{

        if (
            busy
            || !staff
        ) return;


        answers.staff_experience =
            staff;


        addMessage(
            'user',
            staff,
            false
        );


        clearInput();


        setProgress(
            100,
            '✓ Complete'
        );


        // ====================================================
        // CRITICAL NEW BEHAVIOUR
        //
        // We DO NOT wait for Firestore.
        //
        // First show the thank-you screen.
        //
        // Then start the save/navigation.
        // ====================================================

        showInstantThankYou();


        // Give browser a tiny amount of time to paint
        // the thank-you screen first.
        //
        // This is NOT a 20-second delay.
        //
        // It is only 50 milliseconds.

        setTimeout(
            submitToStreamlit,
            50
        );

    }}


    // ========================================================
    // INSTANT THANK YOU
    // ========================================================

    function showInstantThankYou(){{

        const rating =
            Number(
                answers.rating
            );


        const stars =
            '⭐'.repeat(
                Math.max(
                    0,
                    Math.min(
                        5,
                        rating
                    )
                )
            );


        chat.innerHTML = '';


        const complete =
            document.createElement(
                'div'
            );


        complete.className =
            'elite-fast-complete';


        complete.innerHTML =

            '<div class="fast-check">'
            + '✓'
            + '</div>'

            + '<div class="fast-thank">'
            + 'Thank you for sharing 💕'
            + '</div>'

            + '<div class="fast-desc">'
            + 'Your feedback helps '
            + '<strong>'
            + 'Elite Beauty Studio'
            + '</strong> '
            + 'create an even better experience for you.'
            + '</div>'

            + '<div class="fast-summary">'

            + '<div class="fast-summary-row">'
            + '<span>👤 Guest:</span>'
            + '<span class="value">'
            + escapeHtml(
                answers.customer_name
            )
            + '</span>'
            + '</div>'

            + '<div class="fast-summary-row">'
            + '<span>✂ Service:</span>'
            + '<span class="value">'
            + escapeHtml(
                answers.beauty_service
            )
            + '</span>'
            + '</div>'

            + '<div class="fast-summary-row">'
            + '<span>⭐ Rating:</span>'
            + '<span class="value">'
            + rating
            + ' / 5 Stars '
            + stars
            + '</span>'
            + '</div>'

            + '<div class="fast-summary-row">'
            + '<span>♡ Staff:</span>'
            + '<span class="value">'
            + escapeHtml(
                answers.staff_experience
            )
            + '</span>'
            + '</div>'

            + '</div>'

            + '<div class="fast-saved">'
            + '✦ &nbsp; Thank you! Your feedback has been submitted.'
            + '</div>';


        chat.appendChild(
            complete
        );


        scrollChat();


        // Hide input immediately.
        clearInput();

    }}


    // ========================================================
    // HTML ESCAPE FOR FINAL SUMMARY
    // ========================================================

    function escapeHtml(
        value
    ){{

        return String(value)
            .replace(
                /&/g,
                '&amp;'
            )
            .replace(
                /</g,
                '&lt;'
            )
            .replace(
                />/g,
                '&gt;'
            )
            .replace(
                /"/g,
                '&quot;'
            )
            .replace(
                /'/g,
                '&#039;'
            );

    }}


    // ========================================================
    // SEND TO STREAMLIT
    // ========================================================

    function submitToStreamlit(){{

        try {{

            const submissionId =
                (
                    window.crypto
                    && window.crypto.randomUUID
                )

                ? window.crypto.randomUUID()

                : (
                    'ebs-'
                    + Date.now()
                    + '-'
                    + Math.random()
                        .toString(16)
                        .slice(2)
                );


            const url =
                new URL(
                    window.parent.location.href
                );


            url.searchParams.set(
                'submit',
                '1'
            );


            url.searchParams.set(
                'submission_id',
                submissionId
            );


            url.searchParams.set(
                'customer_name',
                answers.customer_name
            );


            url.searchParams.set(
                'beauty_service',
                answers.beauty_service
            );


            url.searchParams.set(
                'rating',
                String(
                    answers.rating
                )
            );


            url.searchParams.set(
                'staff_experience',
                answers.staff_experience
            );


            /*
             * The Streamlit side starts Firestore
             * in a background thread.
             *
             * Therefore the server response does
             * NOT wait for Firestore.
             */

            window.parent.location.href =
                url.toString();

        }} catch(e) {{

            console.log(
                'Submission navigation error:',
                e
            );

        }}

    }}


    // ========================================================
    // BOOT
    // ========================================================

    function keepCustomerPageAtTop(){{

        /*
         * The frontend is rendered inside Streamlit's iframe.
         * Explicitly return the OUTER customer page to the top once
         * during the initial boot. This prevents a remembered browser
         * focus/scroll position from opening the feedback form halfway
         * down the page.
         *
         * We intentionally do NOT call this after customer actions,
         * because later replies must not move the customer around.
         */

        try {{

            if (window.parent && window.parent !== window) {{

                window.parent.requestAnimationFrame(function(){{

                    try {{
                        window.parent.scrollTo({{
                            top: 0,
                            left: 0,
                            behavior: 'auto'
                        }});
                    }} catch(e) {{}}

                }});

            }} else {{

                window.requestAnimationFrame(function(){{
                    window.scrollTo({{
                        top: 0,
                        left: 0,
                        behavior: 'auto'
                    }});
                }});

            }}

        }} catch(e) {{}}

    }}


    function boot(){{

        /* Open at the very top on the initial load only. */
        keepCustomerPageAtTop();


        addMessage(
            'ai',
            welcome,
            false
        );


        renderName();

    }}


    boot();

}})();

</script>
"""


# ============================================================
# COMPLETION SCREEN AFTER STREAMLIT RERUN
# ============================================================

if st.session_state.completed:

    answers = (
        st.session_state.get(
            "final_answers",
            {}
        )
    )


    customer_name = (
        answers.get(
            "customer_name",
            q_name,
        )
    )


    beauty_service = (
        answers.get(
            "beauty_service",
            q_service,
        )
    )


    try:

        rating = int(
            answers.get(
                "rating",
                q_rating or 0,
            )
            or 0
        )

    except (
        TypeError,
        ValueError,
    ):

        rating = 0


    staff = (
        answers.get(
            "staff_experience",
            q_staff,
        )
    )


    stars = (
        "⭐"
        * max(
            0,
            min(
                5,
                rating
            )
        )
    )


    completion_html = f"""

    <style>

    {CUSTOM_CSS}

    {FRONTEND_CSS}

    </style>


    <div class="elite-fast-root">


        <div class="elite-fast-complete">

            <div class="fast-check">
                ✓
            </div>


            <div class="fast-thank">
                Thank you for sharing 💕
            </div>


            <div class="fast-desc">

                Your feedback helps
                <strong>
                    Elite Beauty Studio
                </strong>
                create an even better
                experience for you.

            </div>


            <div class="fast-summary">


                <div class="fast-summary-row">

                    <span>
                        👤 Guest:
                    </span>

                    <span class="value">
                        {esc(customer_name)}
                    </span>

                </div>


                <div class="fast-summary-row">

                    <span>
                        ✂ Service:
                    </span>

                    <span class="value">
                        {esc(beauty_service)}
                    </span>

                </div>


                <div class="fast-summary-row">

                    <span>
                        ⭐ Rating:
                    </span>

                    <span class="value">
                        {rating}
                        / 5 Stars
                        {stars}
                    </span>

                </div>


                <div class="fast-summary-row">

                    <span>
                        ♡ Staff:
                    </span>

                    <span class="value">
                        {esc(staff)}
                    </span>

                </div>


            </div>

        </div>


        <div class="fast-saved">

            ✦ &nbsp;
            Thank you! Your feedback has been submitted.

        </div>


        <button
            id="again-btn"
            class="fast-primary"
            type="button"
        >
            ↻ &nbsp; Give Feedback Again
        </button>


        <div class="fast-footer">

            ✨<br>

            <strong>
                Powered by Elite Beauty Studio AI
            </strong>

            <br>

            🛡️ Your feedback is securely recorded.

        </div>


    </div>


    <script>

    document
        .getElementById(
            'again-btn'
        )
        .addEventListener(
            'click',
            function(){{

                const url =
                    new URL(
                        window.parent.location.href
                    );


                [
                    'submit',
                    'submission_id',
                    'customer_name',
                    'beauty_service',
                    'rating',
                    'staff_experience'
                ]
                .forEach(
                    k =>
                        url.searchParams.delete(k)
                );


                window.parent.location.href =
                    url.toString();

            }}
        );

    </script>

    """


    components.html(
        completion_html,
        height=760,
        scrolling=False,
    )


else:

    components.html(
        HTML,
        height=1250,
        scrolling=False,
    )

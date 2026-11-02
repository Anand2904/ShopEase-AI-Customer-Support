
import asyncio
import csv
import io
import os
import tempfile
import uuid
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from portal_dashboard_page import show_customer_dashboard

import pandas as pd
import streamlit as st
from PIL import Image, UnidentifiedImageError

from agents.log_agent import LOG_FILE
from customer_portal import (
    authenticate_customer,
    get_customer_orders,
    initialize_database,
)
from main import process_ticket
from notifications import unread_events, mark_read
from portal_notifications_page import show_notification_preferences


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
ATTACHMENTS_DIR = BASE_DIR / "complaint_attachments"
ATTACHMENT_INDEX = ATTACHMENTS_DIR / "attachments.csv"
SUPPORT_UPDATES_FILE = BASE_DIR / "support_updates.csv"
CUSTOMER_REPLIES_FILE = BASE_DIR / "customer_replies.csv"

MAX_IMAGES = 3
MAX_IMAGE_BYTES = 5 * 1024 * 1024

REPLY_FIELDS = [
    "ticket_id",
    "customer_id",
    "order_id",
    "created_at",
    "message",
    "photo_count",
]

st.set_page_config(
    page_title="ShopEase | Customer Support",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# STYLING
# ============================================================

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(125deg, #07172c, #102e50);
        color: #edf5ff;
    }

    .block-container {
        max-width: 1500px;
        padding-top: 0.45rem;
        padding-bottom: 1.5rem;
    }

    h1, h2, h3, h4 {
        color: #f7fbff !important;
    }

    h2 {
        font-size: 1.45rem !important;
    }

    h3 {
        font-size: 1.2rem !important;
    }

    p, li {
        font-size: 0.9rem;
        line-height: 1.45;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(14, 43, 73, 0.8);
        border: 1px solid #2b4c6d;
        border-radius: 12px;
    }

    [data-testid="stForm"] {
        background: #102c4b;
        border: 1px solid #355777;
        border-radius: 12px;
        padding: 0.85rem;
    }

    [data-testid="stTabs"] button {
        font-size: 0.9rem;
        font-weight: 600;
        padding: 0.45rem 0.7rem;
    }

    [data-baseweb="tab-list"] {
        gap: 0.25rem;
    }

    [data-testid="stMetricValue"] {
        color: white;
        font-size: 1.45rem !important;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.78rem !important;
    }

    [data-testid="stExpander"] {
        border-color: #31577a;
        border-radius: 9px;
    }

    .stButton > button[kind="primary"],
    [data-testid="stFormSubmitButton"] button[kind="primary"] {
        background: #287ce0;
        color: white;
        border: 0;
    }

    /* Compact Ask page */

    .ask-hero {
        background: linear-gradient(110deg, #10284a, #1b4a7c);
        border: 1px solid #31577a;
        border-radius: 14px;
        padding: 16px 20px;
        margin: 4px 0 12px;
    }

    .ask-hero h2 {
        margin: 0 0 5px;
        font-size: 1.4rem !important;
    }

    .ask-hero p {
        margin: 0 0 12px;
        color: #d6e6f8;
        font-size: 0.86rem;
    }

    .ask-steps {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px;
    }

    .ask-step {
        background: rgba(255,255,255,0.09);
        padding: 9px 11px;
        border-radius: 9px;
        font-size: 0.79rem;
        color: #eaf3ff;
    }

    .ask-step b {
        display: inline-block;
        background: #64b9ec;
        color: #092b47;
        border-radius: 50%;
        width: 22px;
        height: 22px;
        line-height: 22px;
        text-align: center;
        margin-right: 5px;
    }

    .compact-heading {
        font-size: 1.03rem;
        font-weight: 700;
        margin-bottom: 0.4rem;
    }

    .ticket-heading {
        font-size: 1.3rem;
        font-weight: 750;
    }

    .ticket-summary {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        background: #112f50;
        border: 1px solid #31577a;
        border-radius: 10px;
        margin: 0.45rem 0;
    }

    .ticket-summary > div {
        padding: 10px;
        border-right: 1px solid #31577a;
        overflow-wrap: anywhere;
    }

    .ticket-summary > div:last-child {
        border-right: 0;
    }

    .ticket-summary small {
        display: block;
        color: #b9cee4;
        font-size: 0.72rem;
        margin-bottom: 4px;
    }

    .ticket-summary strong {
        color: white;
        font-size: 0.9rem;
    }

    .compact-stats {
        display: flex;
        gap: 10px;
        margin: 0.35rem 0 0.6rem;
    }

    .compact-stats span {
        flex: 1;
        padding: 9px 13px;
        background: #133354;
        border: 1px solid #31577a;
        border-radius: 9px;
        font-size: 0.85rem;
    }

    .compact-stats b {
        color: white;
        font-size: 1.05rem;
    }

    @media (max-width: 760px) {
        .ask-steps {
            grid-template-columns: 1fr;
        }

        .ticket-summary {
            grid-template-columns: repeat(2, 1fr);
        }

        .compact-stats {
            flex-direction: column;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# INITIALIZATION
# ============================================================

initialize_database()

if "customer" not in st.session_state:
    st.session_state.customer = None


def safe_html(value):
    return escape(str(value), quote=True)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_csv_safe(path):
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()

    try:
        return pd.read_csv(
            path,
            dtype=str,
            keep_default_na=False,
        )
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return pd.DataFrame()


# ============================================================
# LOGIN
# ============================================================

def show_login():
    st.title("🛍️ ShopEase Customer Portal")
    st.caption("Sign in to view orders and contact customer support.")

    left, center, right = st.columns([1, 1.4, 1])

    with center:
        with st.container(border=True):
            st.subheader("🔐 Customer Login")

            with st.form("customer_login"):
                email = st.text_input(
                    "Email address",
                    placeholder="aarav@example.com",
                )

                password = st.text_input(
                    "Password",
                    type="password",
                )

                submitted = st.form_submit_button(
                    "Log in",
                    type="primary",
                    use_container_width=True,
                )

            if submitted:
                customer = authenticate_customer(email, password)

                if customer:
                    st.session_state.customer = customer
                    st.rerun()
                else:
                    st.error("Incorrect email or password.")

            with st.expander("Demo login details"):
                st.write("aarav@example.com")
                st.write("priya@example.com")
                st.write("rahul@example.com")
                st.caption("Password: DemoPass123!")

    st.caption(
        "This is a local demonstration. "
        "Do not use real passwords or private customer images."
    )


# ============================================================
# CUSTOMER TICKETS
# ============================================================

def customer_tickets(customer, orders):
    logs = read_csv_safe(LOG_FILE)

    if logs.empty:
        return logs

    required = {"customer_name", "order_id"}

    if not required.issubset(logs.columns):
        return pd.DataFrame()

    owned_orders = {
        str(order["order_id"])
        for order in orders
    }

    return logs.loc[
        (logs["customer_name"] == customer["name"])
        & (logs["order_id"].isin(owned_orders))
    ].copy()


def add_support_updates(logs):
    logs = logs.copy()

    logs["display_status"] = logs["status"].map(
        {
            "Escalated": "Under Review",
            "Resolved": "AI Response Provided",
        }
    ).fillna(logs["status"])

    logs["staff_note"] = ""
    logs["staff_updated_at"] = ""

    updates = read_csv_safe(SUPPORT_UPDATES_FILE)

    required = {
        "ticket_id",
        "status",
        "staff_note",
        "updated_at",
    }

    if updates.empty or not required.issubset(updates.columns):
        return logs

    latest = updates.drop_duplicates(
        "ticket_id",
        keep="last",
    ).set_index("ticket_id")

    logs["display_status"] = (
        logs["ticket_id"]
        .map(latest["status"])
        .fillna(logs["display_status"])
    )

    logs["staff_note"] = (
        logs["ticket_id"]
        .map(latest["staff_note"])
        .fillna("")
    )

    logs["staff_updated_at"] = (
        logs["ticket_id"]
        .map(latest["updated_at"])
        .fillna("")
    )

    return logs


# ============================================================
# PHOTO VALIDATION AND STORAGE
# ============================================================

def validate_photos(uploads):
    uploads = uploads or []

    if len(uploads) > MAX_IMAGES:
        raise ValueError(
            f"You can upload a maximum of {MAX_IMAGES} photos."
        )

    checked = []

    for upload in uploads:
        data = upload.getvalue()

        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError(
                f"{upload.name} exceeds the 5 MB limit."
            )

        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()

            with Image.open(io.BytesIO(data)) as image:
                image_format = image.format

        except (OSError, ValueError, UnidentifiedImageError):
            raise ValueError(
                f"{upload.name} is not a valid image."
            )

        extensions = {
            "JPEG": ".jpg",
            "PNG": ".png",
            "WEBP": ".webp",
        }

        if image_format not in extensions:
            raise ValueError(
                "Only JPG, PNG and WEBP photos are supported."
            )

        checked.append(
            (data, extensions[image_format])
        )

    return checked


def save_ticket_photos(
    ticket_id,
    customer_id,
    order_id,
    checked_photos,
):
    if not checked_photos:
        return 0

    ATTACHMENTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    ticket_folder = ATTACHMENTS_DIR / str(ticket_id)
    ticket_folder.mkdir(exist_ok=True)

    rows = []

    for number, (data, extension) in enumerate(
        checked_photos,
        start=1,
    ):
        filename = (
            f"photo_{number}_{uuid.uuid4().hex[:8]}"
            f"{extension}"
        )

        (ticket_folder / filename).write_bytes(data)

        rows.append(
            {
                "ticket_id": str(ticket_id),
                "customer_id": str(customer_id),
                "order_id": str(order_id),
                "file_path": str(
                    Path(str(ticket_id)) / filename
                ),
                "uploaded_at": utc_now(),
            }
        )

    with ATTACHMENT_INDEX.open(
        "a",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0].keys()),
        )

        if handle.tell() == 0:
            writer.writeheader()

        writer.writerows(rows)

    return len(rows)


def get_ticket_photos(ticket_id, customer_id, order_id):
    index = read_csv_safe(ATTACHMENT_INDEX)

    required = {
        "ticket_id",
        "customer_id",
        "order_id",
        "file_path",
    }

    if index.empty or not required.issubset(index.columns):
        return []

    matching = index.loc[
        (index["ticket_id"] == str(ticket_id))
        & (index["customer_id"] == str(customer_id))
        & (index["order_id"] == str(order_id))
    ]

    root = ATTACHMENTS_DIR.resolve()
    ticket_folder = (root / str(ticket_id)).resolve()

    photos = []

    for _, row in matching.iterrows():
        relative_path = str(row["file_path"])
        path = (root / relative_path).resolve()

        if not path.is_relative_to(ticket_folder):
            continue

        if not path.is_file():
            continue

        if path.suffix.lower() not in {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
        }:
            continue

        try:
            if path.stat().st_size > MAX_IMAGE_BYTES:
                continue

            data = path.read_bytes()

            with Image.open(io.BytesIO(data)) as image:
                image.verify()

        except (OSError, ValueError, UnidentifiedImageError):
            continue

        photos.append(
            {
                "relative_path": relative_path,
                "filename": path.name,
                "data": data,
            }
        )

    return photos


def update_ticket_evidence(
    ticket_id,
    customer_id,
    order_id,
    relative_path,
    replacement=None,
):
    if not ATTACHMENT_INDEX.exists():
        raise ValueError("No evidence index found.")

    root = ATTACHMENTS_DIR.resolve()
    ticket_folder = (root / str(ticket_id)).resolve()
    original_path = (root / relative_path).resolve()

    if not original_path.is_relative_to(ticket_folder):
        raise ValueError("Invalid evidence path.")

    if not original_path.is_file():
        raise ValueError("Original photo is missing.")

    with ATTACHMENT_INDEX.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    matched_index = None

    for index, row in enumerate(rows):
        if (
            row.get("ticket_id") == str(ticket_id)
            and row.get("customer_id") == str(customer_id)
            and row.get("order_id") == str(order_id)
            and row.get("file_path") == relative_path
        ):
            matched_index = index
            break

    if matched_index is None:
        raise ValueError("Photo does not belong to this ticket.")

    new_file = None

    if replacement is None:
        rows.pop(matched_index)
    else:
        data, extension = replacement

        new_file = ticket_folder / (
            f"replacement_{uuid.uuid4().hex[:10]}"
            f"{extension}"
        )

        new_file.write_bytes(data)

        rows[matched_index]["file_path"] = str(
            Path(str(ticket_id)) / new_file.name
        )

        if "uploaded_at" in fields:
            rows[matched_index]["uploaded_at"] = utc_now()

    temporary = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            newline="",
            encoding="utf-8",
            dir=ATTACHMENTS_DIR,
            prefix=".evidence_",
            suffix=".csv",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)

            writer = csv.DictWriter(
                handle,
                fieldnames=fields,
            )

            writer.writeheader()
            writer.writerows(rows)

        os.replace(temporary, ATTACHMENT_INDEX)

    except Exception:
        if temporary:
            temporary.unlink(missing_ok=True)

        if new_file:
            new_file.unlink(missing_ok=True)

        raise

    try:
        original_path.unlink()
    except OSError:
        st.warning(
            "Evidence record updated, but the old "
            "photo could not be deleted from disk."
        )


def show_ticket_evidence(
    ticket_id,
    customer_id,
    order_id,
):
    photos = get_ticket_photos(
        ticket_id,
        customer_id,
        order_id,
    )

    st.caption(
        "Review each photo. You can keep, replace, "
        "or remove an incorrect image."
    )

    if not photos:
        st.info("No photos attached to this ticket.")
        return

    for index, photo in enumerate(photos, start=1):
        with st.container(border=True):
            preview, controls = st.columns(
                [1, 1.5],
                gap="medium",
            )

            with preview:
                st.image(
                    photo["data"],
                    caption=f"Photo {index}",
                    use_container_width=True,
                )

            with controls:
                st.markdown(f"**Photo {index}**")

                action = st.radio(
                    "Is this photo correct?",
                    [
                        "Keep photo",
                        "Replace photo",
                        "Remove photo",
                    ],
                    key=(
                        f"photo_action_{ticket_id}_"
                        f"{photo['relative_path']}"
                    ),
                )

                if action == "Keep photo":
                    st.success("This photo will be kept.")

                elif action == "Replace photo":
                    replacement = st.file_uploader(
                        "Upload replacement",
                        type=["jpg", "jpeg", "png", "webp"],
                        key=(
                            f"replacement_{ticket_id}_"
                            f"{photo['relative_path']}"
                        ),
                    )

                    if replacement is not None:
                        try:
                            checked = validate_photos(
                                [replacement]
                            )

                            st.image(
                                replacement,
                                width=180,
                                caption="Replacement preview",
                            )

                            if st.button(
                                "Confirm replacement",
                                type="primary",
                                key=f"replace_{ticket_id}_{index}",
                            ):
                                update_ticket_evidence(
                                    ticket_id,
                                    customer_id,
                                    order_id,
                                    photo["relative_path"],
                                    checked[0],
                                )

                                st.rerun()

                        except (ValueError, OSError) as error:
                            st.error(str(error))

                else:
                    confirmed = st.checkbox(
                        "Confirm permanent removal",
                        key=f"confirm_remove_{ticket_id}_{index}",
                    )

                    if st.button(
                        "Remove photo",
                        disabled=not confirmed,
                        key=f"remove_{ticket_id}_{index}",
                    ):
                        try:
                            update_ticket_evidence(
                                ticket_id,
                                customer_id,
                                order_id,
                                photo["relative_path"],
                            )

                            st.rerun()

                        except (ValueError, OSError) as error:
                            st.error(str(error))


# ============================================================
# CUSTOMER REPLIES
# ============================================================

def save_customer_reply(
    ticket_id,
    customer_id,
    order_id,
    message,
    checked_photos,
):
    if not message.strip() and not checked_photos:
        raise ValueError(
            "Enter a message or attach at least one photo."
        )

    photo_count = save_ticket_photos(
        ticket_id,
        customer_id,
        order_id,
        checked_photos,
    )

    row = {
        "ticket_id": str(ticket_id),
        "customer_id": str(customer_id),
        "order_id": str(order_id),
        "created_at": utc_now(),
        "message": message.strip(),
        "photo_count": photo_count,
    }

    with CUSTOMER_REPLIES_FILE.open(
        "a",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=REPLY_FIELDS,
        )

        if handle.tell() == 0:
            writer.writeheader()

        writer.writerow(row)

    return photo_count


def show_conversation_history(
    ticket,
    ticket_id,
    customer_id,
):
    events = []

    created = str(ticket.get("timestamp", ""))

    complaint = str(ticket.get("complaint", "")).strip()

    if complaint:
        events.append(
            (
                created,
                0,
                "Customer · Original complaint",
                complaint,
            )
        )

    response = str(ticket.get("response", "")).strip()

    if response:
        events.append(
            (
                created,
                1,
                "AI Support · Initial response",
                response,
            )
        )

    replies = read_csv_safe(CUSTOMER_REPLIES_FILE)

    if not replies.empty and {
        "ticket_id",
        "customer_id",
        "created_at",
        "message",
    }.issubset(replies.columns):
        matching = replies.loc[
            (replies["ticket_id"] == str(ticket_id))
            & (replies["customer_id"] == str(customer_id))
        ]

        for _, reply in matching.iterrows():
            events.append(
                (
                    str(reply["created_at"]),
                    2,
                    "Customer · Follow-up",
                    str(reply["message"]),
                )
            )

    updates = read_csv_safe(SUPPORT_UPDATES_FILE)

    if not updates.empty and {
        "ticket_id",
        "updated_at",
        "status",
        "staff_note",
    }.issubset(updates.columns):
        matching = updates.loc[
            updates["ticket_id"] == str(ticket_id)
        ]

        for _, update in matching.iterrows():
            events.append(
                (
                    str(update["updated_at"]),
                    3,
                    "Support Staff · " + str(update["status"]),
                    str(update["staff_note"]),
                )
            )

    events.sort(key=lambda item: (item[0], item[1]))

    if not events:
        st.info("No conversation history available.")
        return

    for timestamp, _, author, message in events:
        st.markdown(f"**{author}**")

        if timestamp:
            st.caption(
                timestamp.replace("T", " ")[:19] + " UTC"
            )

        if message.strip():
            st.write(message)

        st.divider()


# ============================================================
# ASK PAGE — COMPACT LAYOUT
# ============================================================

def show_ask_page(customer, orders):
    first_name = safe_html(
        customer["name"].split()[0]
    )


    first_name = safe_html(customer["name"].split()[0])

    hero_html = (
        '<div class="ask-hero">'
        f'<h2>Hi {first_name} 👋 How can we help today?</h2>'
        '<p>Ask about orders, returns, refunds, deliveries or your account. '
        'Our AI support agents search company policies to help you find the next step.</p>'
        '<div class="ask-steps">'
        '<div class="ask-step"><b>1</b> Describe your issue</div>'
        '<div class="ask-step"><b>2</b> Four AI agents review it</div>'
        '<div class="ask-step"><b>3</b> Get an answer or support ticket</div>'
        '</div>'
        '</div>'
    )

    st.markdown(hero_html, unsafe_allow_html=True)
    st.markdown(
        '<div class="compact-heading">💡 Try an example</div>',
        unsafe_allow_html=True,
    )

    examples = [
        "Where is my order?",
        "I want to return my shoes",
        "I forgot my password",
        "The product arrived broken",
        "I was charged twice",
        "Do you sell bulk gift cards?",
    ]

    for start in (0, 3):
        columns = st.columns(3, gap="small")

        for column, example in zip(
            columns,
            examples[start:start + 3],
        ):
            with column:
                if st.button(
                    example,
                    key=f"example_{start}_{example}",
                    use_container_width=True,
                ):
                    st.session_state["ask_text"] = example
                    st.rerun()

    with st.container(border=True):
        with st.form("quick_ask_form"):
            question = st.text_area(
                "Your question or complaint",
                key="ask_text",
                placeholder=(
                    "Describe your issue here..."
                ),
                height=75,
            )

            order_options = {
                f"{order['order_id']} — {order['product_name']}": order
                for order in orders
            }

            order_column, button_column = st.columns(
                [2.5, 1],
                vertical_alignment="bottom",
            )

            with order_column:
                selected_order = st.selectbox(
                    "Related order",
                    ["General question (no order)"]
                    + list(order_options.keys()),
                )

            with button_column:
                submitted = st.form_submit_button(
                    "💬 Send to AI",
                    type="primary",
                    use_container_width=True,
                )

        st.caption(
            "For damaged items, use Raise Complaint "
            "to attach photos. AI processes text, not images."
        )

    if submitted:
        if not question.strip():
            st.warning("Please enter your question.")
            return

        order = order_options.get(selected_order)

        if order is None:
            st.info(
                "Please select a related order to create "
                "a trackable support ticket."
            )
            return

        try:
            with st.spinner(
                "Four AI agents are reviewing your request..."
            ):
                result = asyncio.run(
                    process_ticket(
                        complaint=(
                            f"Customer complaint about order "
                            f"{order['order_id']}: "
                            f"{question.strip()}"
                        ),
                        customer_name=customer["name"],
                        order_id=order["order_id"],
                    )
                )

            st.success(
                f"Ticket created: "
                f"{result['ticket']['ticket_id']}"
            )

            with st.container(border=True):
                st.markdown("#### 🤖 AI Support Response")
                st.write(
                    result["resolution"].customer_response
                )

                if result["ticket"]["status"] == "Escalated":
                    st.warning(
                        "Under Review — sent for support attention"
                    )
                else:
                    st.info(
                        "AI Response Provided — "
                        "view the ticket in My Complaints"
                    )

        except Exception as error:
            st.error(
                f"Could not process your request: {error}"
            )


# ============================================================
# SUPPORT OVERVIEW
# ============================================================

def show_overview_page(customer, orders):
    st.markdown("### 📊 Your Support Overview")

    logs = customer_tickets(customer, orders)

    if not logs.empty:
        logs = add_support_updates(logs)

    total = len(logs)

    under_review = (
        int((logs["display_status"] == "Under Review").sum())
        if not logs.empty
        else 0
    )

    ai_answered = (
        int((logs["status"] == "Resolved").sum())
        if not logs.empty
        else 0
    )

    first, second, third = st.columns(3)

    first.metric("📝 Total complaints", total)
    second.metric("🤖 AI responses", ai_answered)
    third.metric("⏳ Under review", under_review)

    st.markdown("#### 🕘 Recent activity")

    if logs.empty:
        st.info(
            "No complaints yet. "
            "Use Raise Complaint to get started."
        )
        return

    if "timestamp" in logs.columns:
        logs = logs.sort_values(
            "timestamp",
            ascending=False,
        )

    filter_column, search_column = st.columns([1, 2])

    with filter_column:
        status_filter = st.selectbox(
            "Filter by status",
            ["All"] + sorted(
                logs["display_status"].unique().tolist()
            ),
            key="overview_status",
        )

    with search_column:
        search = st.text_input(
            "Search tickets",
            placeholder="Ticket ID, order or complaint",
            key="overview_search",
        )

    visible = logs.copy()

    if status_filter != "All":
        visible = visible.loc[
            visible["display_status"] == status_filter
        ]

    if search.strip():
        columns = [
            name
            for name in [
                "ticket_id",
                "order_id",
                "category",
                "complaint",
            ]
            if name in visible.columns
        ]

        if columns:
            matching = visible[columns].astype(str).apply(
                lambda column: column.str.contains(
                    search.strip(),
                    case=False,
                    regex=False,
                )
            ).any(axis=1)

            visible = visible.loc[matching]

    columns = [
        "ticket_id",
        "timestamp",
        "order_id",
        "category",
        "urgency",
        "display_status",
        "complaint",
    ]

    st.dataframe(
        visible[
            [column for column in columns if column in visible]
        ].head(20),
        hide_index=True,
        use_container_width=True,
        height=min(500, 40 + max(1, min(len(visible), 20)) * 37),
    )

    st.caption(
        "An AI response does not automatically confirm "
        "a refund, replacement or completed human review."
    )


# ============================================================
# ORDERS PAGE
# ============================================================

def show_orders_page(orders):
    st.markdown("### 📦 My Order History")

    if not orders:
        st.info("No orders found.")
        return

    order_df = pd.DataFrame(orders)

    search_column, status_column = st.columns([2, 1])

    with search_column:
        search = st.text_input(
            "Search orders",
            placeholder="Order ID or product",
        )

    with status_column:
        status = st.selectbox(
            "Delivery status",
            ["All"] + sorted(
                order_df["status"].astype(str).unique().tolist()
            ),
        )

    visible = order_df.copy()

    if search.strip():
        matching = (
            visible["order_id"].astype(str).str.contains(
                search.strip(),
                case=False,
                regex=False,
            )
            | visible["product_name"].astype(str).str.contains(
                search.strip(),
                case=False,
                regex=False,
            )
        )

        visible = visible.loc[matching]

    if status != "All":
        visible = visible.loc[
            visible["status"].astype(str) == status
        ]

    columns = [
        "order_id",
        "order_date",
        "product_name",
        "amount",
        "status",
    ]

    st.dataframe(
        visible[columns],
        hide_index=True,
        use_container_width=True,
        height=min(520, 40 + max(1, len(visible)) * 36),
    )

    st.download_button(
        "⬇️ Download order history",
        data=visible[columns].to_csv(
            index=False
        ).encode("utf-8-sig"),
        file_name="my_order_history.csv",
        mime="text/csv",
    )


# ============================================================
# RAISE COMPLAINT
# ============================================================

def show_complaint_page(customer, orders):
    st.markdown("### 📝 Raise a Complaint")

    options = {
        f"{order['order_id']} — {order['product_name']}": order
        for order in orders
    }

    with st.form("complaint_form"):
        if options:
            selected_label = st.selectbox(
                "Choose your order",
                list(options.keys()),
            )
        else:
            selected_label = None
            st.info(
                "You need an order to submit an order complaint."
            )

        complaint = st.text_area(
            "Describe your issue",
            height=95,
            placeholder=(
                "Example: My package arrived damaged."
            ),
        )

        photos = st.file_uploader(
            "📷 Upload product or delivery photos (optional)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            help="Maximum 3 photos, 5 MB each.",
        )

        submitted = st.form_submit_button(
            "Submit complaint with evidence",
            type="primary",
            use_container_width=True,
        )

    if photos:
        st.markdown("**Check your selected photos**")

        columns = st.columns(
            min(len(photos), 3)
        )

        for index, photo in enumerate(photos[:3]):
            with columns[index]:
                st.image(
                    photo,
                    use_container_width=True,
                )
                st.caption(photo.name)

        st.caption(
            "If a photo is incorrect, remove it from "
            "the upload selection and choose the correct file."
        )

    if not submitted:
        return

    if not selected_label:
        st.warning("Please select an order.")
        return

    if not complaint.strip():
        st.warning("Please describe your issue.")
        return

    try:
        checked_photos = validate_photos(photos or [])
    except ValueError as error:
        st.error(str(error))
        return

    order = options[selected_label]

    try:
        with st.spinner(
            "AI support agents are reviewing your complaint..."
        ):
            result = asyncio.run(
                process_ticket(
                    complaint=(
                        f"Customer complaint about order "
                        f"{order['order_id']}: "
                        f"{complaint.strip()}"
                    ),
                    customer_name=customer["name"],
                    order_id=order["order_id"],
                )
            )

        ticket = result["ticket"]

        st.success(
            f"Ticket created: {ticket['ticket_id']}"
        )

        try:
            photo_count = save_ticket_photos(
                ticket["ticket_id"],
                customer["customer_id"],
                order["order_id"],
                checked_photos,
            )

            if photo_count:
                st.info(
                    f"📎 {photo_count} photo(s) attached."
                )

        except OSError as error:
            st.error(
                f"Ticket created, but photos could "
                f"not be saved: {error}"
            )

        with st.container(border=True):
            st.markdown("#### 🤖 AI Support Response")
            st.write(
                result["resolution"].customer_response
            )

            st.caption(
                f"Confidence: "
                f"{result['resolution'].confidence}"
            )

            if ticket["status"] == "Escalated":
                st.warning(
                    "Under Review — escalated to support"
                )
            else:
                st.success("AI Response Provided")

    except Exception as error:
        st.error(
            f"Complaint processing failed: {error}"
        )


# ============================================================
# MY COMPLAINTS — COMPACT TICKET CENTER
# ============================================================

def show_tickets_page(customer, orders):
    st.markdown("### 📋 My Complaints")

    logs = customer_tickets(customer, orders)

    if logs.empty:
        st.info("No complaints recorded yet.")
        return

    logs = add_support_updates(
        logs.reset_index(drop=True)
    )

    attachment_data = read_csv_safe(ATTACHMENT_INDEX)

    logs["photos"] = 0

    if not attachment_data.empty and {
        "customer_id",
        "ticket_id",
    }.issubset(attachment_data.columns):
        counts = (
            attachment_data.loc[
                attachment_data["customer_id"]
                == str(customer["customer_id"])
            ]
            .groupby("ticket_id")
            .size()
        )

        logs["photos"] = (
            logs["ticket_id"]
            .map(counts)
            .fillna(0)
            .astype(int)
        )

    review_count = int(
        (logs["display_status"] == "Under Review").sum()
    )

    ai_count = int(
        (logs["status"] == "Resolved").sum()
    )

    st.markdown(
        f"""
        <div class="compact-stats">
            <span>🎟️ <b>{len(logs)}</b> Total tickets</span>
            <span>⏳ <b>{review_count}</b> Under review</span>
            <span>🤖 <b>{ai_count}</b> AI responses</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    filter_column, ticket_column, refresh_column = st.columns(
        [1.1, 2, 0.8],
        vertical_alignment="bottom",
    )

    with filter_column:
        status_filter = st.selectbox(
            "Filter by status",
            ["All"] + sorted(
                logs["display_status"].unique().tolist()
            ),
        )

    visible = logs.copy()

    if status_filter != "All":
        visible = visible.loc[
            visible["display_status"] == status_filter
        ]

    if "timestamp" in visible.columns:
        visible = visible.sort_values(
            "timestamp",
            ascending=False,
        )

    with ticket_column:
        if visible.empty:
            st.selectbox(
                "Select a ticket",
                ["No matching tickets"],
                disabled=True,
            )
            selected_id = None
        else:
            selected_id = st.selectbox(
                "Select a ticket",
                visible["ticket_id"].astype(str).tolist(),
            )

    with refresh_column:
        if st.button(
            "↻ Refresh",
            use_container_width=True,
        ):
            st.rerun()

    if selected_id is None:
        st.info("No tickets match this filter.")
        return

    ticket = visible.loc[
        visible["ticket_id"].astype(str) == selected_id
    ].iloc[0]

    status = str(
        ticket.get("display_status", "Unknown")
    )

    order_id = str(ticket.get("order_id", ""))
    customer_id = customer["customer_id"]
    photo_count = int(ticket.get("photos", 0))

    with st.container(border=True):
        title_column, status_column = st.columns(
            [3, 1],
            vertical_alignment="center",
        )

        with title_column:
            st.markdown(
                f'<div class="ticket-heading">'
                f'🎟️ Ticket {safe_html(selected_id)}'
                f'</div>',
                unsafe_allow_html=True,
            )

        with status_column:
            st.markdown(
                f"**{safe_html(status)}**",
                unsafe_allow_html=True,
            )

        summary = [
            ("📦 Order", order_id),
            ("🏷️ Category", ticket.get("category", "—")),
            ("📊 Urgency", ticket.get("urgency", "—")),
            ("🖼️ Photos", photo_count),
        ]

        summary_html = "".join(
            f"<div>"
            f"<small>{safe_html(label)}</small>"
            f"<strong>{safe_html(value)}</strong>"
            f"</div>"
            for label, value in summary
        )

        st.markdown(
            f'<div class="ticket-summary">'
            f'{summary_html}'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.caption(
            "Click the arrow beside any section to view details."
        )

        with st.expander(
            "🤖 AI Support Response",
            expanded=False,
        ):
            st.write(
                ticket.get("response", "")
                or "No response recorded."
            )

        with st.expander(
            f"📷 Uploaded Evidence ({photo_count} photos)",
            expanded=False,
        ):
            show_ticket_evidence(
                selected_id,
                customer_id,
                order_id,
            )

        reason = str(
            ticket.get("escalation_reason", "")
        ).strip()

        if reason:
            with st.expander(
                "ℹ️ Reason for Escalation",
                expanded=False,
            ):
                st.write(reason)

        staff_note = str(
            ticket.get("staff_note", "")
        ).strip()

        if staff_note:
            with st.expander(
                "🎧 Latest Support Staff Update",
                expanded=False,
            ):
                st.write(staff_note)
                st.caption(
                    "Updated: "
                    + str(
                        ticket.get("staff_updated_at", "")
                    ).replace("T", " ")[:19]
                    + " UTC"
                )

        with st.expander(
            "💬 Conversation History",
            expanded=False,
        ):
            show_conversation_history(
                ticket,
                selected_id,
                customer_id,
            )

        with st.expander(
            "✉️ Reply to Support",
            expanded=False,
        ):
            st.caption(
                "Add information to this ticket without "
                "creating a new complaint."
            )

            with st.form(
                f"reply_form_{selected_id}",
                clear_on_submit=True,
            ):
                message = st.text_area(
                    "Your message",
                    height=85,
                    max_chars=2000,
                )

                reply_photos = st.file_uploader(
                    "Additional photos",
                    type=["jpg", "jpeg", "png", "webp"],
                    accept_multiple_files=True,
                    key=f"reply_photos_{selected_id}",
                )

                reply_submitted = st.form_submit_button(
                    "Send reply",
                    type="primary",
                )

            if reply_submitted:
                try:
                    checked = validate_photos(
                        reply_photos or []
                    )

                    count = save_customer_reply(
                        selected_id,
                        customer_id,
                        order_id,
                        message,
                        checked,
                    )

                    st.success(
                        f"Reply saved. "
                        f"{count} additional photo(s) attached."
                    )

                    st.rerun()

                except (ValueError, OSError) as error:
                    st.error(str(error))

        with st.expander(
            "🗓️ Ticket Information",
            expanded=False,
        ):
            st.write(
                f"**Ticket ID:** {selected_id}"
            )
            st.write(
                f"**Created:** "
                f"{ticket.get('timestamp', '—')}"
            )
            st.write(
                f"**Status:** {status}"
            )
            st.write(
                f"**Order:** {order_id}"
            )
            st.write(
                f"**Category:** "
                f"{ticket.get('category', '—')}"
            )
            st.write(
                f"**Urgency:** "
                f"{ticket.get('urgency', '—')}"
            )
            st.write(
                f"**Photos:** {photo_count}"
            )

        with st.expander(
            "💡 What Happens Next?",
            expanded=False,
        ):
            if status == "Awaiting Customer":
                st.write(
                    "Support staff requested more information."
                )
                st.write(
                    "Read the latest update and reply "
                    "using the section above."
                )

            elif status == "Resolved by Support":
                st.write(
                    "A support representative marked "
                    "this ticket resolved."
                )

            elif status == "Under Review":
                st.write(
                    "Your ticket is waiting for "
                    "support staff review."
                )
                st.write(
                    "Refresh the page to check for updates."
                )

            else:
                st.write(
                    "The AI provided an answer based "
                    "on available company policies."
                )
                st.write(
                    "This does not automatically confirm "
                    "a refund or replacement."
                )

        with st.expander(
            "⬇️ Download Ticket History",
            expanded=False,
        ):
            st.download_button(
                "Download my ticket history",
                data=logs.to_csv(
                    index=False
                ).encode("utf-8"),
                file_name="my_tickets.csv",
                mime="text/csv",
                use_container_width=True,
            )

    with st.expander(
        "View all complaint tickets",
        expanded=False,
    ):
        columns = [
            "ticket_id",
            "timestamp",
            "order_id",
            "category",
            "urgency",
            "display_status",
            "photos",
        ]

        st.dataframe(
            logs[
                [
                    column
                    for column in columns
                    if column in logs.columns
                ]
            ],
            hide_index=True,
            use_container_width=True,
        )


# ============================================================
# NOTIFICATION BANNER
# ============================================================

def show_notification_banner(customer, orders):
    logs = customer_tickets(customer, orders)

    owned_ids = (
        logs["ticket_id"].astype(str).tolist()
        if not logs.empty
        else []
    )

    recipient = (
        f"customer:{customer['customer_id']}"
    )

    try:
        pending = unread_events(
            recipient,
            owned_ids,
            "staff",
        )

        with st.expander(
            f"🔔 Support notifications "
            f"({len(pending)} unread)",
            expanded=bool(pending),
        ):
            if not pending:
                st.caption(
                    "No unread support updates."
                )

            for event in pending[:10]:
                st.markdown(
                    f"**Ticket "
                    f"{safe_html(event['ticket_id'])}**"
                )
                st.write(event["message"])
                st.caption(event["time"])

            if pending:
                if st.button(
                    "Mark notifications as read",
                    key="mark_notifications_read",
                ):
                    mark_read(
                        recipient,
                        pending,
                    )
                    st.rerun()

            if st.button(
                "↻ Check for updates",
                key="check_notifications",
            ):
                st.rerun()

    except (OSError, ValueError) as error:
        st.warning(
            f"Notifications unavailable: {error}"
        )

    return owned_ids


# ============================================================
# MAIN DASHBOARD
# ============================================================

def show_dashboard():
    customer = st.session_state.customer

    if customer is None:
        st.rerun()
        return

    orders = get_customer_orders(
        customer["customer_id"]
    )

    brand_column, account_column = st.columns(
        [4, 2],
        vertical_alignment="center",
    )

    with brand_column:
        st.markdown("### 🛍️ ShopEase")

    with account_column:
        st.caption(
            f"👤 Signed in as {customer['name']}"
        )

    owned_ticket_ids = show_notification_banner(
        customer,
        orders,
    )

    tabs = st.tabs(
        [
            "💬 Ask",
            "📊 Support Overview",
            "📦 My Orders",
            "📝 Raise Complaint",
            "📋 My Complaints",
            "🔔 Notifications",
            "🏠 Dashboard",
        ]
    )

    with tabs[0]:
        show_ask_page(
            customer,
            orders,
        )

    with tabs[1]:
        show_overview_page(
            customer,
            orders,
        )

    with tabs[2]:
        show_orders_page(
            orders,
        )

    with tabs[3]:
        show_complaint_page(
            customer,
            orders,
        )

    with tabs[4]:
        show_tickets_page(
            customer,
            orders,
        )

    with tabs[5]:
        show_notification_preferences(
            customer,
            owned_ticket_ids,
        )
    with tabs[6]:
        show_customer_dashboard(customer, orders)


# ============================================================
# START APPLICATION
# ============================================================

if st.session_state.customer is None:
    show_login()
else:
    show_dashboard()

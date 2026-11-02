import asyncio
import csv
import io
from html import escape
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image, UnidentifiedImageError

from agents.log_agent import LOG_FILE
from customer_portal import authenticate_customer, get_customer_orders, initialize_database
from main import process_ticket
from notifications import unread_events, mark_read

BASE_DIR = Path(__file__).resolve().parent
ROBOT_IMAGE = BASE_DIR / 'assets' / 'robot.png'
ATTACHMENTS_DIR = BASE_DIR / 'complaint_attachments'
ATTACHMENT_INDEX = ATTACHMENTS_DIR / 'attachments.csv'
SUPPORT_UPDATES_FILE = BASE_DIR / 'support_updates.csv'
CUSTOMER_REPLIES_FILE = BASE_DIR / 'customer_replies.csv'
REPLY_FIELDS = ['ticket_id', 'customer_id', 'order_id', 'created_at', 'message', 'photo_count']
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES = 3

st.set_page_config(page_title='ShopEase Customer Portal', page_icon='🛍️', layout='wide', initial_sidebar_state='collapsed')
st.markdown('''
<style>
.stApp {background:linear-gradient(125deg,#07172c 0%,#102e50 100%);color:#edf5ff;}
.block-container {max-width:1450px;padding-top:.65rem;padding-bottom:1.4rem;}
h1,h2,h3,h4 {color:#f7fbff!important;letter-spacing:-.02em;}
h2 {font-size:1.55rem!important;} h3 {font-size:1.28rem!important;} h4 {font-size:1.06rem!important;}
p,li {font-size:.91rem;line-height:1.52;}
[data-testid="stVerticalBlockBorderWrapper"] {background:rgba(14,43,73,.82);border-radius:12px;border:1px solid #2b4c6d;}
[data-testid="stMetricValue"] {color:#fff;font-size:1.45rem!important;}
[data-testid="stMetricLabel"] {font-size:.8rem!important;}
[data-testid="stMetric"] {padding:.15rem 0;}
[data-testid="stTabs"] button {font-size:.91rem;font-weight:600;padding:.55rem .9rem;}
[data-baseweb="tab-list"] {gap:.5rem;}
[data-testid="stForm"] {border:1px solid #355777;border-radius:12px;padding:.9rem;background:#102c4b;}
.stButton>button[kind="primary"],[data-testid="stFormSubmitButton"] button {background:#287ce0;color:#fff;border:0;}
[data-testid="stAlert"] {padding:.6rem .85rem;}
[data-testid="stCaptionContainer"] p {font-size:.76rem;}
.ticket-heading {font-size:1.48rem;font-weight:750;line-height:1.2;margin:0;}
.ticket-status {display:inline-block;padding:7px 12px;border-radius:9px;background:#194b78;color:#8acaff;font-size:.86rem;font-weight:700;}
.ticket-status.review {background:#514821;color:#ffe6a0;}
.ticket-summary {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;border:1px solid #31577a;border-radius:11px;background:#112f50;margin:.7rem 0 .9rem;}
.ticket-summary>div {padding:13px 16px;border-right:1px solid #31577a;min-width:0;}
.ticket-summary>div:last-child {border-right:0;}
.ticket-summary small {display:block;font-size:.74rem;color:#b9cee4;margin-bottom:5px;}
.ticket-summary strong {font-size:.99rem;font-weight:700;overflow-wrap:anywhere;}
.ticket-section-title {font-size:1.03rem;font-weight:700;margin:0 0 9px;}
.ticket-response {font-size:.9rem;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere;}
.ticket-detail-row {display:grid;grid-template-columns:95px minmax(0,1fr);gap:10px;padding:8px 0;border-bottom:1px solid #284967;font-size:.84rem;}
.ticket-detail-row:last-child {border-bottom:0;}
.ticket-detail-row span:first-child {color:#b6cce2;}
.ticket-detail-row span:last-child {text-align:right;overflow-wrap:anywhere;font-weight:600;}
.next-step {font-size:.85rem;line-height:1.55;margin:0 0 9px;}
.compact-note {font-size:.76rem;color:#a9c1d9;}
@media(max-width:760px){.ticket-summary{grid-template-columns:repeat(2,minmax(0,1fr));}.ticket-summary>div:nth-child(2){border-right:0;}.ticket-summary>div:nth-child(-n+2){border-bottom:1px solid #31577a;}}
</style>
''', unsafe_allow_html=True)


initialize_database()
if 'customer' not in st.session_state:
    st.session_state.customer = None


def show_login():
    st.markdown('## 🛍️ ShopEase Customer Portal')
    st.caption('Sign in to check orders and contact support.')
    _, middle, _ = st.columns([1, 1.4, 1])
    with middle:
        with st.container(border=True):
            st.subheader('🔐 Customer login')
            with st.form('login_form'):
                email = st.text_input('Email', placeholder='aarav@example.com')
                password = st.text_input('Password', type='password')
                submitted = st.form_submit_button('Log in', use_container_width=True)
            if submitted:
                customer = authenticate_customer(email, password)
                if customer:
                    st.session_state.customer = customer
                    st.rerun()
                else:
                    st.error('Incorrect email or password.')
            with st.expander('Demo accounts'):
                st.write('aarav@example.com')
                st.write('priya@example.com')
                st.write('rahul@example.com')
                st.caption('Demo password: DemoPass123!')
    st.caption('Local demonstration only. Do not enter real customer credentials or personal photos.')


def customer_tickets(customer, orders):
    if not LOG_FILE.exists():
        return pd.DataFrame()
    logs = pd.read_csv(LOG_FILE, dtype=str).fillna('')
    if logs.empty:
        return logs
    if not {'customer_name', 'order_id'}.issubset(logs.columns):
        st.warning('Ticket log is missing required columns.')
        return pd.DataFrame()
    owned_ids = {str(order['order_id']) for order in orders}
    return logs.loc[
        (logs['customer_name'] == customer['name'])
        & (logs['order_id'].isin(owned_ids))
    ].copy()


def validate_photos(uploads):
    if len(uploads) > MAX_IMAGES:
        raise ValueError(f'Please upload at most {MAX_IMAGES} photos.')
    checked = []
    for upload in uploads:
        data = upload.getvalue()
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError(f'{upload.name} exceeds the 5 MB limit.')
        try:
            with Image.open(io.BytesIO(data)) as img:
                img.verify()
            with Image.open(io.BytesIO(data)) as img:
                fmt = img.format
        except (UnidentifiedImageError, OSError, ValueError):
            raise ValueError(f'{upload.name} is not a valid image.')
        if fmt not in ('JPEG', 'PNG', 'WEBP'):
            raise ValueError(f'{upload.name} must be JPG, PNG or WEBP.')
        checked.append((data, {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}[fmt]))
    return checked


def save_ticket_photos(ticket_id, customer_id, order_id, checked_photos):
    if not checked_photos:
        return 0
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    ticket_folder = ATTACHMENTS_DIR / str(ticket_id)
    ticket_folder.mkdir(exist_ok=True)
    rows = []
    for index, (data, extension) in enumerate(checked_photos, start=1):
        filename = f'photo_{index}_{uuid.uuid4().hex[:8]}{extension}'
        (ticket_folder / filename).write_bytes(data)
        rows.append({
            'ticket_id': str(ticket_id),
            'customer_id': str(customer_id),
            'order_id': str(order_id),
            'file_path': str(Path(str(ticket_id)) / filename),
            'uploaded_at': datetime.now(timezone.utc).isoformat(),
        })
    with ATTACHMENT_INDEX.open('a', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        if handle.tell() == 0:
            writer.writeheader()
        writer.writerows(rows)
    return len(rows)




def save_customer_reply(ticket_id, customer_id, order_id, message, checked_photos):
    """Store a reply against an existing ticket; don't call the AI or create a new ticket."""
    if not message.strip() and not checked_photos:
        raise ValueError('Write a reply or attach at least one photo.')
    # Save attachments before the reply entry; keep the original ticket unchanged.
    count = save_ticket_photos(ticket_id, customer_id, order_id, checked_photos)
    row = {
        'ticket_id': str(ticket_id), 'customer_id': str(customer_id),
        'order_id': str(order_id),
        'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'message': message.strip(), 'photo_count': count,
    }
    with CUSTOMER_REPLIES_FILE.open('a', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=REPLY_FIELDS)
        if handle.tell() == 0:
            writer.writeheader()
        writer.writerow(row)
    return count


def load_customer_replies(ticket_id, customer_id):
    if not CUSTOMER_REPLIES_FILE.exists() or CUSTOMER_REPLIES_FILE.stat().st_size == 0:
        return pd.DataFrame()
    data = pd.read_csv(CUSTOMER_REPLIES_FILE, dtype=str, keep_default_na=False)
    if not set(REPLY_FIELDS).issubset(data.columns):
        return pd.DataFrame()
    return data.loc[(data['ticket_id'] == str(ticket_id)) &
                    (data['customer_id'] == str(customer_id))].copy()


def add_support_updates(logs):
    """Merge latest local staff action by ticket ID without changing the AI audit log."""
    logs = logs.copy()
    logs['display_status'] = logs['status'].map({
        'Escalated': 'Under Review', 'Resolved': 'AI Response Provided',
    }).fillna(logs['status'])
    logs['staff_note'] = ''
    logs['staff_updated_at'] = ''
    if not SUPPORT_UPDATES_FILE.exists() or SUPPORT_UPDATES_FILE.stat().st_size == 0:
        return logs
    try:
        updates = pd.read_csv(SUPPORT_UPDATES_FILE, dtype=str, keep_default_na=False)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        st.warning(f'Staff updates could not be loaded: {exc}')
        return logs
    needed = {'ticket_id', 'status', 'staff_note', 'updated_at'}
    if not needed.issubset(updates.columns):
        st.warning('Staff update file has unexpected columns.')
        return logs
    latest = updates.drop_duplicates('ticket_id', keep='last').set_index('ticket_id')
    logs['display_status'] = logs['ticket_id'].map(latest['status']).fillna(logs['display_status'])
    logs['staff_note'] = logs['ticket_id'].map(latest['staff_note']).fillna('')
    logs['staff_updated_at'] = logs['ticket_id'].map(latest['updated_at']).fillna('')
    return logs


REPLIES_FILE_FOR_TIMELINE = CUSTOMER_REPLIES_FILE
UPDATES_FILE_FOR_TIMELINE = SUPPORT_UPDATES_FILE


def show_conversation_timeline(ticket, ticket_id, customer_id=None):
    """Show a chronological, read-only record of AI, customer, and staff messages."""
    events = []
    created = str(ticket.get('timestamp', ''))
    complaint = str(ticket.get('complaint', '')).strip()
    if complaint:
        events.append((created, 0, 'Customer · Original complaint', complaint, ''))
    response = str(ticket.get('response', '')).strip()
    if response:
        events.append((created, 1, 'AI support · Initial response', response, ''))

    if REPLIES_FILE_FOR_TIMELINE.exists() and REPLIES_FILE_FOR_TIMELINE.stat().st_size:
        try:
            replies = pd.read_csv(REPLIES_FILE_FOR_TIMELINE, dtype=str, keep_default_na=False)
            if {'ticket_id', 'created_at', 'message'}.issubset(replies.columns):
                matches = replies['ticket_id'].eq(str(ticket_id))
                if customer_id is not None:
                    if 'customer_id' not in replies.columns:
                        matches &= False
                    else:
                        matches &= replies['customer_id'].eq(str(customer_id))
                for _, entry in replies.loc[matches].iterrows():
                    count = str(entry.get('photo_count', '0'))
                    attachment = f'{count} photo(s) attached' if count.isdigit() and int(count) else ''
                    events.append((str(entry['created_at']), 2, 'Customer · Follow-up',
                                   str(entry['message']).strip(), attachment))
        except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
            st.warning('Some customer replies could not be loaded.')

    if UPDATES_FILE_FOR_TIMELINE.exists() and UPDATES_FILE_FOR_TIMELINE.stat().st_size:
        try:
            updates = pd.read_csv(UPDATES_FILE_FOR_TIMELINE, dtype=str, keep_default_na=False)
            if {'ticket_id', 'updated_at', 'staff_note', 'status'}.issubset(updates.columns):
                for _, entry in updates.loc[updates['ticket_id'].eq(str(ticket_id))].iterrows():
                    events.append((str(entry['updated_at']), 3,
                                   'Support staff · ' + str(entry['status']),
                                   str(entry['staff_note']).strip(), ''))
        except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
            st.warning('Some staff updates could not be loaded.')

    events.sort(key=lambda item: (item[0], item[1]))
    with st.container(border=True):
        st.markdown('#### 💬 Conversation history')
        st.caption('Chronological activity from locally saved records. Times are UTC.')
        if not events:
            st.info('No conversation history available for this ticket.')
        for stamp, _, author, message, attachment in events:
            st.markdown(f'**{author}**')
            st.caption((stamp.replace('T', ' ')[:19] + ' UTC') if stamp else 'Time unavailable')
            if message:
                st.write(message)
            if attachment:
                st.caption('📎 ' + attachment)
            st.divider()


def show_dashboard():
    customer = st.session_state.customer
    if not customer:
        st.rerun()
    customer_id = customer['customer_id']
    orders = get_customer_orders(customer_id)

    brand, account, logout = st.columns([4, 2, 1], vertical_alignment='center')
    with brand:
        st.markdown('### 🛍️ ShopEase')
    with account:
        st.caption(f"👤 {customer['name']}")
    with logout:
        if st.button('Logout', use_container_width=True):
            st.session_state.customer = None
            st.rerun()

    # Compact welcome strip: avoids a tall hero panel on every tab.
    with st.container(border=True):
        greeting, robot = st.columns([10, 1], vertical_alignment='center')
        with greeting:
            first_name = customer['name'].split()[0]
            st.markdown(f'**Welcome back, {first_name}!**  ·  Track orders and manage support requests')
        with robot:
            if ROBOT_IMAGE.exists():
                st.image(str(ROBOT_IMAGE), width=62)

    # New staff updates are shown as local, persistent unread notifications.
    try:
        owned_ticket_ids = customer_tickets(customer, orders).get('ticket_id', pd.Series(dtype=str)).astype(str).tolist()
        recipient = f"customer:{customer_id}"
        pending = unread_events(recipient, owned_ticket_ids, 'staff')
        with st.expander(f"🔔 Support notifications ({len(pending)} unread)", expanded=bool(pending)):
            if not pending:
                st.caption('No unread support updates. Use Refresh to check for new messages.')
            else:
                for event in pending[:10]:
                    st.markdown(f"**Ticket {event['ticket_id']}** · {event['status'] or 'Staff update'}")
                    st.write(event['message'])
                    st.caption(event['time'])
                if st.button('Mark support notifications as read', key='mark_customer_read'):
                    mark_read(recipient, pending)
                    st.rerun()
            if st.button('↻ Check for updates', key='refresh_customer_notifications'):
                st.rerun()
    except (OSError, ValueError) as exc:
        st.warning(f'Notifications unavailable: {exc}')

    overview_tab, orders_tab, help_tab, tickets_tab = st.tabs(
        ['📊 Support Overview', '📦 My Orders', '📝 Raise Complaint', '📋 My Complaints']
    )

    with overview_tab:
        st.markdown('#### Your support overview')
        st.caption('A snapshot of your tickets, including saved support-staff updates.')
        try:
            overview_logs = customer_tickets(customer, orders)
            if not overview_logs.empty:
                overview_logs = add_support_updates(overview_logs)
            if overview_logs.empty:
                total_tickets = 0
                under_review = 0
                ai_answered = 0
            else:
                total_tickets = len(overview_logs)
                under_review = int((overview_logs['display_status'] == 'Under Review').sum()) if 'status' in overview_logs else 0
                ai_answered = int((overview_logs['status'] == 'Resolved').sum()) if 'status' in overview_logs else 0

            metric_a, metric_b, metric_c = st.columns(3)
            metric_a.metric('📝 Total complaints', total_tickets)
            metric_b.metric('🤖 AI responses provided', ai_answered)
            metric_c.metric('⏳ Under review', under_review)

            with st.container(border=True):
                st.markdown('##### 🕘 Recent activity')
                if overview_logs.empty:
                    st.info('You have not submitted a complaint yet. Use the Raise Complaint tab to get started.')
                else:
                    if 'timestamp' in overview_logs.columns:
                        overview_logs = overview_logs.sort_values('timestamp', ascending=False)
                    for _, item in overview_logs.head(3).iterrows():
                        status = str(item.get('display_status', 'Unknown'))
                        st.markdown(f"**Ticket {item.get('ticket_id', '—')}** · Order {item.get('order_id', '—')}")
                        st.caption(f"{status} · {item.get('timestamp', 'Date unavailable')}")
                st.caption('For complete details, open the My Complaints tab.')

            with st.container(border=True):
                st.markdown('##### Quick guide')
                st.write('📦 **My Orders:** Check your purchases and delivery status.')
                st.write('📝 **Raise Complaint:** Describe an issue and attach up to three photos.')
                st.write('📋 **My Complaints:** Filter tickets, read AI responses and download your history.')
            st.caption('An AI response does not confirm a refund, replacement or completed human review.')
        except Exception as exc:
            st.error(f'Could not load support overview: {exc}')

    with orders_tab:
        if not orders:
            st.info('No orders found for your account.')
        else:
            for order in orders:
                with st.container(border=True):
                    detail, status_col = st.columns([4, 1], vertical_alignment='center')
                    with detail:
                        st.markdown(f"**{order['product_name']}**")
                        st.caption(
                            f"Order {order['order_id']} · {order['order_date']} · ₹{order['amount']:,.2f}"
                        )
                    with status_col:
                        if order['status'] == 'Delivered':
                            st.success('Delivered')
                        elif order['status'] == 'Shipped':
                            st.info('Shipped')
                        else:
                            st.warning(order['status'])

    with help_tab:
        options = {f"{o['order_id']} — {o['product_name']}": o for o in orders}
        with st.form('complaint_form'):
            if options:
                selected_label = st.selectbox('Choose your order', list(options))
            else:
                selected_label = None
                st.info('You need an order before submitting an order complaint.')
            complaint = st.text_area(
                'Describe your issue', height=110,
                placeholder='Example: My package arrived damaged.'
            )
            photos = st.file_uploader(
                '📷 Upload photos of the product or delivery package (optional)',
                type=['jpg', 'jpeg', 'png', 'webp'],
                accept_multiple_files=True,
                help='Up to 3 images, 5 MB each. Use sample images for this demo.',
            )
            st.caption('Photos are saved locally as evidence for the support ticket. The AI does not analyze images yet.')
            submitted = st.form_submit_button('Submit complaint with evidence', use_container_width=True)

        if photos:
            st.markdown('**Photo preview**')
            preview_cols = st.columns(min(len(photos), 3))
            for idx, photo in enumerate(photos[:3]):
                with preview_cols[idx]:
                    st.image(photo, use_container_width=True)
                    st.caption(photo.name)

        if submitted:
            if not selected_label:
                st.warning('Please select an order.')
            elif not complaint.strip():
                st.warning('Please describe your issue.')
            else:
                try:
                    checked_photos = validate_photos(photos or [])
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    selected = options[selected_label]
                    try:
                        with st.spinner('AI support agents are reviewing your complaint...'):
                            result = asyncio.run(process_ticket(
                                complaint=(
                                    f"Customer complaint about order {selected['order_id']}: "
                                    f"{complaint.strip()}"
                                ),
                                customer_name=customer['name'],
                                order_id=selected['order_id'],
                            ))
                        ticket = result['ticket']
                        resolution = result['resolution']
                        st.success(f"Ticket created: {ticket['ticket_id']}")
                        try:
                            saved_count = save_ticket_photos(
                                ticket['ticket_id'], customer_id,
                                selected['order_id'], checked_photos
                            )
                            if saved_count:
                                st.info(f'📎 {saved_count} photo(s) attached to this ticket.')
                        except OSError as exc:
                            st.error(f'Ticket created, but photos could not be saved: {exc}')
                        with st.container(border=True):
                            st.markdown('#### 🤖 AI support response')
                            st.write(resolution.customer_response)
                            st.caption(f'Confidence: {resolution.confidence}')
                            if ticket['status'] == 'Escalated':
                                st.error('Escalated for support review')
                                st.caption(ticket['escalation_reason'])
                            else:
                                st.success('Resolved')
                    except Exception as exc:
                        st.error(f'Complaint processing failed: {exc}')

    with tickets_tab:
        st.markdown('### 📋 My Complaints')
        st.caption('Track AI responses and support-staff updates saved locally. Refresh to see new changes.')
        try:
            logs = customer_tickets(customer, orders)
            if logs.empty:
                st.info('No complaints recorded for your orders yet.')
            else:
                logs = add_support_updates(logs.reset_index(drop=True))
                logs['photos'] = 0
                if ATTACHMENT_INDEX.exists():
                    attachment_data = pd.read_csv(ATTACHMENT_INDEX, dtype=str).fillna('')
                    if {'customer_id', 'ticket_id'}.issubset(attachment_data.columns):
                        counts = attachment_data.loc[
                            attachment_data['customer_id'] == str(customer_id)
                        ].groupby('ticket_id').size()
                        logs['photos'] = logs['ticket_id'].map(counts).fillna(0).astype(int)

                review_count = int((logs['display_status'] == 'Under Review').sum())
                answered_count = int((logs['status'] == 'Resolved').sum())
                m1, m2, m3 = st.columns(3)
                m1.metric('Total tickets', len(logs))
                m2.metric('Under review', review_count)
                m3.metric('AI responses provided', answered_count)
                if st.button('↻ Refresh staff updates', key='refresh_customer_tickets'):
                    st.rerun()

                filter_col, picker_col = st.columns([1, 2], gap='medium')
                with filter_col:
                    selected_status = st.selectbox('Filter by status', ['All'] + sorted(logs['display_status'].dropna().unique().tolist()))
                visible = logs if selected_status == 'All' else logs.loc[logs['display_status'] == selected_status]
                if visible.empty:
                    st.info('No tickets match this filter.')
                else:
                    if 'timestamp' in visible.columns:
                        visible = visible.sort_values('timestamp', ascending=False)
                    with picker_col:
                        chosen_id = st.selectbox('Select a ticket', visible['ticket_id'].astype(str).tolist())
                    ticket = visible.loc[visible['ticket_id'].astype(str) == chosen_id].iloc[0]
                    status = str(ticket.get('display_status', 'Unknown'))
                    escalated = status == 'Under Review'
                    safe = lambda value: escape(str(value), quote=True)
                    left, right = st.columns([2.45, 1], gap='medium')
                    with left:
                        with st.container(border=True):
                            hcol, scol = st.columns([2, 1], vertical_alignment='center')
                            with hcol:
                                st.markdown(f'<div class="ticket-heading">🎟️ Ticket {safe(chosen_id)}</div>', unsafe_allow_html=True)
                            with scol:
                                css_class = 'ticket-status review' if escalated else 'ticket-status'
                                st.markdown(f'<div class="{css_class}">{safe(status)}</div>', unsafe_allow_html=True)
                            summary = [
                                ('📦 Order', ticket.get('order_id', '—')),
                                ('🏷️ Category', ticket.get('category', '—')),
                                ('📊 Urgency', ticket.get('urgency', '—')),
                                ('🖼️ Photos', int(ticket.get('photos', 0))),
                            ]
                            summary_html = ''.join(f'<div><small>{safe(label)}</small><strong>{safe(value)}</strong></div>' for label,value in summary)
                            st.markdown(f'<div class="ticket-summary">{summary_html}</div>', unsafe_allow_html=True)
                            with st.container(border=True):
                                st.markdown('<div class="ticket-section-title">🤖 AI Support Response</div>', unsafe_allow_html=True)
                                response = str(ticket.get('response', '')).strip() or 'No response recorded.'
                                st.markdown(f'<div class="ticket-response">{safe(response)}</div>', unsafe_allow_html=True)
                            reason = str(ticket.get('escalation_reason', '')).strip()
                            if reason:
                                with st.container(border=True):
                                    st.markdown('<div class="ticket-section-title">ℹ️ Reason for Escalation</div>', unsafe_allow_html=True)
                                    st.write(reason)
                            note = str(ticket.get('staff_note', '')).strip()
                            if note:
                                with st.container(border=True):
                                    st.markdown('<div class="ticket-section-title">🎧 Latest Support Staff Update</div>', unsafe_allow_html=True)
                                    st.write(note)
                                    st.caption('Updated: ' + str(ticket.get('staff_updated_at', '')).replace('T', ' ')[:19] + ' UTC')
                            show_conversation_timeline(ticket, chosen_id, customer_id)
                            with st.container(border=True):
                                st.markdown('<div class="ticket-section-title">💬 Reply to support</div>', unsafe_allow_html=True)
                                st.caption('Add information or evidence to this ticket. A reply does not create another complaint or automatically change its status.')
                                with st.form(f'customer_reply_{chosen_id}', clear_on_submit=True):
                                    reply_text = st.text_area('Your message', height=85, max_chars=2000,
                                        placeholder='Example: Here is the serial number and an additional photo.')
                                    reply_photos = st.file_uploader('Additional evidence (up to 3 photos, 5 MB each)',
                                        type=['jpg', 'jpeg', 'png', 'webp'], accept_multiple_files=True,
                                        key=f'reply_upload_{chosen_id}')
                                    send_reply = st.form_submit_button('Send reply to support', use_container_width=True)
                                if send_reply:
                                    try:
                                        checked_reply_photos = validate_photos(reply_photos or [])
                                        photo_count = save_customer_reply(chosen_id, customer_id,
                                            str(ticket.get('order_id', '')), reply_text, checked_reply_photos)
                                        st.success(f'Reply saved to ticket {chosen_id}. Added {photo_count} photo(s).')
                                        st.rerun()
                                    except (ValueError, OSError) as exc:
                                        st.error(f'Could not save reply: {exc}')
                            st.markdown('<div class="compact-note">Replies are saved locally for the support desk to view; there is no automatic notification or live messaging.</div>', unsafe_allow_html=True)
                    with right:
                        with st.container(border=True):
                            st.markdown('<div class="ticket-section-title">🗓️ Ticket Information</div>', unsafe_allow_html=True)
                            details = [
                                ('Ticket ID', chosen_id),
                                ('Created', str(ticket.get('timestamp', '—')).replace('T', ' ')[:19]),
                                ('Status', status),
                                ('Order ID', ticket.get('order_id', '—')),
                                ('Category', ticket.get('category', '—')),
                                ('Urgency', ticket.get('urgency', '—')),
                                ('Photos', int(ticket.get('photos', 0))),
                            ]
                            detail_html = ''.join(f'<div class="ticket-detail-row"><span>{safe(k)}</span><span>{safe(v)}</span></div>' for k,v in details)
                            st.markdown(detail_html, unsafe_allow_html=True)
                        with st.container(border=True):
                            st.markdown('<div class="ticket-section-title">💡 What happens next?</div>', unsafe_allow_html=True)
                            if status == 'Awaiting Customer':
                                steps = ['Support staff requested more information.', 'Read the latest staff note on this ticket.', 'Use Reply to support below to send details or additional photos.']
                            elif status == 'Resolved by Support':
                                steps = ['A support representative marked this ticket resolved.', 'Read their latest note for details.', 'This does not automatically update your order or refund.']
                            elif escalated:
                                steps = ['The ticket is marked Under Review.', 'Support staff can record updates in the local dashboard.', 'Refresh this page to check for changes.']
                            else:
                                steps = ['The AI provided an answer based on available policies.', 'This does not confirm a refund or replacement.', 'Review the response and contact support if needed.']
                            for i, step in enumerate(steps, 1):
                                st.markdown(f'<div class="next-step"><b>{i}.</b> {safe(step)}</div>', unsafe_allow_html=True)
                        st.download_button('⬇️ Download my ticket history', data=logs.to_csv(index=False).encode('utf-8'), file_name='my_tickets.csv', mime='text/csv', use_container_width=True)

                with st.expander('View all complaint tickets'):
                    cols = ['ticket_id', 'timestamp', 'order_id', 'category', 'urgency', 'display_status', 'photos']
                    st.dataframe(logs[[c for c in cols if c in logs.columns]], use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f'Could not load ticket history: {exc}')


if st.session_state.customer is None:
    show_login()
else:
    show_dashboard()

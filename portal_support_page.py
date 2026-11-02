"""ShopEase local-only support dashboard.

Run: streamlit run admin_dashboard.py --server.address 127.0.0.1 --server.port 8502
No login is provided: do not deploy or expose this dashboard on a network.
Staff actions are recorded in support_updates.csv, leaving the AI audit log intact.
"""

import csv
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from notifications import unread_events, mark_read
from PIL import Image, UnidentifiedImageError

BASE_DIR = Path(__file__).resolve().parent
TICKETS_FILE = BASE_DIR / 'ticket_logs.csv'
UPDATES_FILE = BASE_DIR / 'support_updates.csv'
REPLIES_FILE = BASE_DIR / 'customer_replies.csv'
ATTACHMENTS_DIR = BASE_DIR / 'complaint_attachments'
ATTACHMENTS_INDEX = ATTACHMENTS_DIR / 'attachments.csv'
STATUSES = ['Under Review', 'Awaiting Customer', 'Resolved by Support']
UPDATE_FIELDS = ['ticket_id', 'updated_at', 'status', 'staff_note']

st.markdown('''
<style>
.stApp {background:linear-gradient(120deg,#07182d,#102e50);color:#eef6ff;}
.block-container {max-width:1480px;padding-top:1rem;padding-bottom:2rem;}
h1,h2,h3 {color:#f6fbff!important;} h1{font-size:1.65rem!important;} h2{font-size:1.35rem!important;} h3{font-size:1.05rem!important;}
p,li {font-size:.9rem;line-height:1.5;}
[data-testid="stVerticalBlockBorderWrapper"] {background:rgba(16,44,75,.88);border:1px solid #315577;border-radius:12px;}
[data-testid="stMetricValue"] {font-size:1.55rem!important;color:#fff;}
[data-testid="stMetricLabel"] {font-size:.8rem!important;}
[data-testid="stForm"] {background:#102c4b;border:1px solid #315577;border-radius:12px;}
[data-testid="stCaptionContainer"] p {font-size:.77rem;}
[data-testid="stAlert"] {padding:.55rem .8rem;}
.info-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px 18px;}
.info-cell {padding:8px 0;border-bottom:1px solid #294966;font-size:.84rem;overflow-wrap:anywhere;}
.info-cell b {display:block;color:#a9c7e3;font-size:.75rem;margin-bottom:3px;}
.response-box {white-space:pre-wrap;overflow-wrap:anywhere;font-size:.88rem;line-height:1.65;}
</style>
''', unsafe_allow_html=True)


def read_csv(path):
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        st.error(f'Could not read {path.name}: {exc}')
        return pd.DataFrame()


def load_tickets():
    data = read_csv(TICKETS_FILE)
    if data.empty:
        return data
    required = {'ticket_id', 'status'}
    if not required.issubset(data.columns):
        st.error('ticket_logs.csv must contain ticket_id and status columns.')
        return pd.DataFrame()
    data = data.drop_duplicates(subset=['ticket_id'], keep='last').copy()
    updates = read_csv(UPDATES_FILE)
    data['support_status'] = data['status'].map({
        'Escalated': 'Under Review', 'Resolved': 'AI Response Provided'
    }).fillna(data['status'])
    data['last_staff_note'] = ''
    data['last_updated'] = ''
    if not updates.empty and set(UPDATE_FIELDS).issubset(updates.columns):
        latest = updates.drop_duplicates(subset=['ticket_id'], keep='last').set_index('ticket_id')
        data['support_status'] = data['ticket_id'].map(latest['status']).fillna(data['support_status'])
        data['last_staff_note'] = data['ticket_id'].map(latest['staff_note']).fillna('')
        data['last_updated'] = data['ticket_id'].map(latest['updated_at']).fillna('')
    return data.sort_values('timestamp', ascending=False) if 'timestamp' in data else data


def save_update(ticket_id, status, note):
    # Append-only history: never overwrite the AI's original ticket record.
    row = {
        'ticket_id': str(ticket_id),
        'updated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'status': status,
        'staff_note': note.strip(),
    }
    with UPDATES_FILE.open('a', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=UPDATE_FIELDS)
        if handle.tell() == 0:
            writer.writeheader()
        writer.writerow(row)


def safe_photo_path(ticket_id, stored_path):
    """Only open files inside this ticket's own attachment folder."""
    if not stored_path:
        return None
    base = (ATTACHMENTS_DIR / str(ticket_id)).resolve()
    candidate = (ATTACHMENTS_DIR / stored_path).resolve()
    if candidate.parent != base or candidate.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp'}:
        return None
    return candidate if candidate.is_file() else None


def show_photos(ticket_id):
    index = read_csv(ATTACHMENTS_INDEX)
    if index.empty or not {'ticket_id', 'file_path'}.issubset(index.columns):
        st.caption('No photos attached to this ticket.')
        return
    entries = index.loc[index['ticket_id'] == str(ticket_id), 'file_path'].tolist()
    if not entries:
        st.caption('No photos attached to this ticket.')
        return
    cols = st.columns(min(len(entries), 3))
    shown = 0
    for item in entries[:12]:
        path = safe_photo_path(ticket_id, item)
        if path is None:
            continue
        try:
            with Image.open(path) as img:
                img.verify()
            with cols[shown % len(cols)]:
                st.image(str(path), use_container_width=True)
                st.caption(path.name)
            shown += 1
        except (UnidentifiedImageError, OSError, ValueError):
            st.warning('An attached image could not be opened.')
    if not shown:
        st.caption('No accessible photos found.')


def info(label, value):
    import html
    return f'<div class="info-cell"><b>{html.escape(str(label))}</b>{html.escape(str(value or "—"))}</div>'


st.title('🎧 ShopEase Support Desk')
st.caption('Local testing dashboard · No authentication · Staff changes are saved separately from AI ticket logs')
st.warning('Demo only: this dashboard has no login. Run it on localhost, and do not expose it publicly or use real customer information.', icon='⚠️')

left, right = st.columns([5, 1], vertical_alignment='center')
with left:
    st.markdown('### Complaint management')
with right:
    if st.button('↻ Refresh', use_container_width=True):
        st.rerun()

tickets = load_tickets()
if tickets.empty:
    st.info('No tickets yet. Submit a complaint through the customer portal first.')
    st.code('streamlit run app.py --server.port 8501')
    st.stop()

# Support staff see unread customer replies across all tickets.
try:
    pending = unread_events('staff:local', tickets['ticket_id'].astype(str).tolist(), 'customer')
    with st.expander(f"🔔 New customer replies ({len(pending)} unread)", expanded=bool(pending)):
        if not pending:
            st.caption('No unread customer replies. Click Refresh to check again.')
        else:
            for event in pending[:15]:
                st.markdown(f"**Ticket {event['ticket_id']}**")
                st.write(event['message'])
                st.caption(event['time'])
            if st.button('Mark customer replies as read', key='mark_staff_read'):
                mark_read('staff:local', pending)
                st.rerun()
except (OSError, ValueError) as exc:
    st.warning(f'Notifications unavailable: {exc}')

under_review = int((tickets['support_status'] == 'Under Review').sum())
awaiting = int((tickets['support_status'] == 'Awaiting Customer').sum())
resolved = int((tickets['support_status'] == 'Resolved by Support').sum())
cols = st.columns(4)
for col, label, value in zip(cols, ['Total tickets', 'Under review', 'Awaiting customer', 'Resolved by support'],
                             [len(tickets), under_review, awaiting, resolved]):
    with col:
        with st.container(border=True):
            st.metric(label, value)

filter_col, search_col = st.columns([1, 2])
with filter_col:
    choices = ['All'] + sorted(tickets['support_status'].dropna().unique().tolist())
    status_filter = st.selectbox('Filter by status', choices)
with search_col:
    search = st.text_input('Search tickets', placeholder='Ticket ID, order, customer, category...')

visible = tickets.copy()
if status_filter != 'All':
    visible = visible[visible['support_status'] == status_filter]
if search.strip():
    searchable = [c for c in ['ticket_id', 'order_id', 'customer_name', 'category', 'complaint'] if c in visible.columns]
    if searchable:
        matches = visible[searchable].astype(str).apply(lambda s: s.str.contains(search.strip(), case=False, regex=False)).any(axis=1)
        visible = visible.loc[matches]

st.caption(f'Showing {len(visible)} of {len(tickets)} tickets')
columns = ['ticket_id', 'timestamp', 'customer_name', 'order_id', 'category', 'urgency', 'support_status']
labels = {'ticket_id':'Ticket ID', 'timestamp':'Created', 'customer_name':'Customer', 'order_id':'Order',
          'category':'Category', 'urgency':'Urgency', 'support_status':'Staff status'}
st.dataframe(visible[[c for c in columns if c in visible.columns]].rename(columns=labels),
             hide_index=True, use_container_width=True, height=min(340, 85 + 36 * max(1, len(visible))))

if visible.empty:
    st.info('No tickets match these filters.')
    st.stop()

ids = visible['ticket_id'].tolist()
selected_id = st.selectbox('Open ticket', ids, format_func=lambda tid: f'{tid} · ' +
                           str(visible.loc[visible['ticket_id'] == tid, 'customer_name'].iloc[0] if 'customer_name' in visible else 'Ticket'))
ticket = visible.loc[visible['ticket_id'] == selected_id].iloc[0]

REPLIES_FILE_FOR_TIMELINE = REPLIES_FILE
UPDATES_FILE_FOR_TIMELINE = UPDATES_FILE


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


main_col, side_col = st.columns([1.75, 1], gap='medium')
with main_col:
    with st.container(border=True):
        st.subheader(f'🎟️ Ticket {selected_id}')
        st.info(f"Current staff status: {ticket['support_status']}")
        cells = [
            info('Customer', ticket.get('customer_name', '')),
            info('Order', ticket.get('order_id', '')),
            info('Category', ticket.get('category', '')),
            info('Urgency', ticket.get('urgency', '')),
            info('AI status', ticket.get('status', '')),
            info('Sentiment', ticket.get('sentiment', '')),
        ]
        st.markdown('<div class="info-grid">' + ''.join(cells) + '</div>', unsafe_allow_html=True)
        st.markdown('#### Customer complaint')
        st.write(ticket.get('complaint', 'Not recorded'))
        st.markdown('#### 🤖 AI support response')
        import html
        st.markdown('<div class="response-box">' + html.escape(ticket.get('response', 'No response recorded')) + '</div>', unsafe_allow_html=True)
        if ticket.get('escalation_reason', '').strip():
            st.markdown('#### Escalation reason')
            st.warning(ticket['escalation_reason'])
        if ticket.get('kb_sources', '').strip():
            st.caption('Knowledge sources: ' + ticket['kb_sources'])
    show_conversation_timeline(ticket, selected_id)
    with st.container(border=True):
        st.markdown('#### 📷 Customer evidence photos')
        show_photos(selected_id)

with side_col:
    with st.container(border=True):
        st.markdown('#### Update this ticket')
        st.caption('Updates are recorded as staff actions; they do not alter the original AI decision.')
        with st.form(f'update_{selected_id}'):
            new_status = st.selectbox('New status', STATUSES, index=STATUSES.index(ticket['support_status'])
                                      if ticket['support_status'] in STATUSES else 0)
            staff_note = st.text_area('Staff note', height=115,
                                      placeholder='Example: Reviewed sample photos; requested order packaging details.')
            submitted = st.form_submit_button('Save staff update', type='primary', use_container_width=True)
        if submitted:
            if not staff_note.strip():
                st.error('Please enter a staff note before saving.')
            else:
                try:
                    save_update(selected_id, new_status, staff_note)
                    st.success('Staff update saved.')
                    st.rerun()
                except OSError as exc:
                    st.error(f'Could not save update: {exc}')
        if ticket.get('last_staff_note', '').strip():
            st.markdown('**Latest staff note**')
            st.write(ticket['last_staff_note'])
            st.caption('Updated: ' + str(ticket.get('last_updated', '')))

    with st.container(border=True):
        st.markdown('#### Ticket activity')
        history = read_csv(UPDATES_FILE)
        if not history.empty and set(UPDATE_FIELDS).issubset(history.columns):
            history = history.loc[history['ticket_id'] == selected_id].iloc[::-1]
            for _, entry in history.head(10).iterrows():
                st.markdown(f"**{entry['status']}**")
                st.caption(entry['updated_at'])
                st.write(entry['staff_note'])
                st.divider()
            if history.empty:
                st.caption('No staff updates yet.')
        else:
            st.caption('No staff updates yet.')

    st.download_button('⬇️ Download filtered tickets',
                       data=visible.to_csv(index=False).encode('utf-8'),
                       file_name='support_tickets.csv', mime='text/csv', use_container_width=True)

st.caption('Staff updates are stored in support_updates.csv; customer replies in customer_replies.csv. Refresh to view new customer messages and photos.')

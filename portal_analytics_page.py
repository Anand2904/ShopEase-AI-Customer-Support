"""ShopEase support analytics — local demo, read-only.
Run: streamlit run analytics_dashboard.py --server.address 127.0.0.1 --server.port 8503
"""
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
TICKETS = ROOT / 'ticket_logs.csv'
UPDATES = ROOT / 'support_updates.csv'

st.markdown('''<style>
.stApp{background:linear-gradient(120deg,#07182d,#102e50);color:#edf5ff}
.block-container{max-width:1460px;padding-top:1rem;padding-bottom:2rem}
h1{font-size:1.65rem!important}h2{font-size:1.2rem!important}h3{font-size:1rem!important}
p,li{font-size:.87rem!important}
[data-testid="stVerticalBlockBorderWrapper"]{background:#102c4b;border:1px solid #315577;border-radius:12px}
[data-testid="stMetricValue"]{font-size:1.55rem!important;color:#fff}
[data-testid="stMetricLabel"]{font-size:.78rem!important}
[data-testid="stCaptionContainer"] p{font-size:.75rem!important}
</style>''', unsafe_allow_html=True)


def read_csv(path):
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        st.error(f'Cannot read {path.name}: {error}')
        return pd.DataFrame()


def load_data():
    tickets = read_csv(TICKETS)
    if tickets.empty:
        return tickets
    required = {'ticket_id', 'status'}
    if not required.issubset(tickets.columns):
        st.error('ticket_logs.csv requires ticket_id and status columns.')
        return pd.DataFrame()
    tickets = tickets.drop_duplicates('ticket_id', keep='last').copy()
    tickets['support_status'] = tickets['status'].map({
        'Escalated': 'Under Review', 'Resolved': 'AI Response Provided'
    }).fillna(tickets['status'])
    updates = read_csv(UPDATES)
    if not updates.empty and {'ticket_id', 'status'}.issubset(updates.columns):
        # Prefer most recently recorded staff update, where timestamps exist.
        if 'updated_at' in updates.columns:
            updates = updates.sort_values('updated_at', kind='stable')
        latest = updates.drop_duplicates('ticket_id', keep='last').set_index('ticket_id')
        tickets['support_status'] = tickets['ticket_id'].map(latest['status']).fillna(tickets['support_status'])
    if 'timestamp' in tickets.columns:
        tickets['created_at'] = pd.to_datetime(tickets['timestamp'], errors='coerce', utc=True)
    else:
        tickets['created_at'] = pd.NaT
    for column in ('category', 'urgency', 'sentiment', 'customer_name', 'order_id'):
        if column not in tickets.columns:
            tickets[column] = ''
        tickets[column] = tickets[column].replace('', 'Unknown')
    return tickets


header, refresh = st.columns([7, 1], vertical_alignment='center')
with header:
    st.markdown('## 📊 ShopEase · Support Analytics')
    st.caption('Read-only local dashboard · AI tickets + latest staff status · Times displayed in UTC')
with refresh:
    if st.button('↻ Refresh', use_container_width=True):
        st.rerun()

data = load_data()
if data.empty:
    st.info('No ticket data yet. Submit a complaint in the customer portal to populate ticket_logs.csv.')
    st.stop()

with st.container(border=True):
    st.markdown('**Filters**')
    a, b, c, d = st.columns([1.3, 1, 1, 1])
    with a:
        category = st.selectbox('Category', ['All'] + sorted(data['category'].unique().tolist()))
    with b:
        urgency = st.selectbox('Urgency', ['All'] + sorted(data['urgency'].unique().tolist()))
    with c:
        status = st.selectbox('Current status', ['All'] + sorted(data['support_status'].unique().tolist()))
    with d:
        days = st.selectbox('Created', ['All time', 'Last 7 days', 'Last 30 days', 'Last 90 days'])

filtered = data.copy()
if category != 'All':
    filtered = filtered[filtered['category'] == category]
if urgency != 'All':
    filtered = filtered[filtered['urgency'] == urgency]
if status != 'All':
    filtered = filtered[filtered['support_status'] == status]
if days != 'All time':
    limit = {'Last 7 days': 7, 'Last 30 days': 30, 'Last 90 days': 90}[days]
    cutoff = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=limit)
    filtered = filtered[filtered['created_at'] >= cutoff]

count = len(filtered)
escalated = int(filtered['status'].eq('Escalated').sum())
under_review = int(filtered['support_status'].eq('Under Review').sum())
staff_resolved = int(filtered['support_status'].eq('Resolved by Support').sum())
rate = (escalated / count * 100) if count else 0
m1, m2, m3, m4, m5 = st.columns(5)
for col, label, value in [
    (m1, 'Total tickets', count),
    (m2, 'AI escalations', escalated),
    (m3, 'Escalation rate', f'{rate:.1f}%'),
    (m4, 'Under review', under_review),
    (m5, 'Resolved by staff', staff_resolved),
]:
    with col:
        with st.container(border=True):
            st.metric(label, value)

left, right = st.columns(2, gap='medium')
with left:
    with st.container(border=True):
        st.markdown('### Complaints by category')
        categories = filtered['category'].value_counts()
        if categories.empty:
            st.info('No matching tickets.')
        else:
            st.bar_chart(categories.rename_axis('Category').rename('Tickets'), horizontal=True)
with right:
    with st.container(border=True):
        st.markdown('### Current ticket status')
        statuses = filtered['support_status'].value_counts()
        if statuses.empty:
            st.info('No matching tickets.')
        else:
            st.bar_chart(statuses.rename_axis('Status').rename('Tickets'), horizontal=True)

left, right = st.columns(2, gap='medium')
with left:
    with st.container(border=True):
        st.markdown('### Ticket volume over time')
        dated = filtered.dropna(subset=['created_at'])
        if dated.empty:
            st.info('No valid ticket timestamps available.')
        else:
            daily = dated.groupby(dated['created_at'].dt.strftime('%Y-%m-%d')).size()
            daily.index.name = 'Date (UTC)'
            st.line_chart(daily.rename('Tickets'))
with right:
    with st.container(border=True):
        st.markdown('### Urgency and sentiment')
        u, s = st.columns(2)
        with u:
            st.markdown('**Urgency**')
            st.dataframe(filtered['urgency'].value_counts().rename_axis('Urgency').reset_index(name='Tickets'), hide_index=True, use_container_width=True)
        with s:
            st.markdown('**Sentiment**')
            st.dataframe(filtered['sentiment'].value_counts().rename_axis('Sentiment').reset_index(name='Tickets'), hide_index=True, use_container_width=True)

with st.container(border=True):
    st.markdown('### Ticket explorer')
    columns = ['ticket_id', 'timestamp', 'customer_name', 'order_id', 'category', 'urgency', 'sentiment', 'status', 'support_status']
    available = [name for name in columns if name in filtered.columns]
    view = filtered.sort_values('created_at', ascending=False, na_position='last')
    st.dataframe(view[available].rename(columns={
        'ticket_id': 'Ticket', 'timestamp': 'Created (UTC)', 'customer_name': 'Customer',
        'order_id': 'Order', 'category': 'Category', 'urgency': 'Urgency',
        'sentiment': 'Sentiment', 'status': 'AI status', 'support_status': 'Current status'
    }), use_container_width=True, hide_index=True)
    st.download_button('⬇ Export filtered ticket report', data=view[available].to_csv(index=False).encode('utf-8'),
                       file_name='shopease_analytics.csv', mime='text/csv')

st.caption('Escalation rate = tickets originally escalated by AI ÷ tickets in the selected filter. Staff resolution counts reflect the latest recorded support status; this dashboard does not measure actual refund or delivery completion. Demo only: do not expose publicly.')

"""ShopEase customer notification preferences. Local demo; no external messages sent."""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from notifications import unread_events, mark_read

ROOT = Path(__file__).resolve().parent
PREF_DIR = ROOT / 'notification_preferences'

DEFAULTS = {
    'email': True, 'sms': False, 'whatsapp': False, 'in_app': True,
    'frequency': 'Whenever the ticket status changes',
    'quiet_hours': '10 PM to 7 AM', 'mobile': '',
}


def _preferences_file(customer_id):
    return PREF_DIR / f'customer_{int(customer_id)}.json'


def load_preferences(customer_id):
    path = _preferences_file(customer_id)
    try:
        data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        return {**DEFAULTS, **{k: v for k, v in data.items() if k in DEFAULTS}}
    except (OSError, ValueError, TypeError):
        return DEFAULTS.copy()


def save_preferences(customer_id, values):
    PREF_DIR.mkdir(parents=True, exist_ok=True)
    target = _preferences_file(customer_id)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=PREF_DIR,
                                         prefix='.prefs_', suffix='.json', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump({**values, 'saved_at': datetime.now(timezone.utc).isoformat()}, handle, indent=2)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def show_notification_preferences(customer, ticket_ids):
    """Dense dark-blue notifications settings in the existing customer tab."""
    customer_id = customer['customer_id']
    saved = load_preferences(customer_id)

    st.markdown('<div id="shopease-compact-notify"></div>', unsafe_allow_html=True)
    st.markdown("""
    <style>
    /* Restore the original navy theme; compact only this tab. */
    [role="tabpanel"]:has(#shopease-compact-notify),
    [data-testid="stTabContent"]:has(#shopease-compact-notify) {
        background: transparent !important; color: #eaf4ff !important;
        padding: .25rem 0 !important;
    }
    [role="tabpanel"]:has(#shopease-compact-notify) [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stTabContent"]:has(#shopease-compact-notify) [data-testid="stVerticalBlockBorderWrapper"] {
        background: #102d4e !important; border: 1px solid #315574 !important;
        border-radius: 12px !important; box-shadow: none !important;
    }
    [role="tabpanel"]:has(#shopease-compact-notify) [data-testid="stVerticalBlock"],
    [data-testid="stTabContent"]:has(#shopease-compact-notify) [data-testid="stVerticalBlock"] {
        gap: .32rem !important;
    }
    [role="tabpanel"]:has(#shopease-compact-notify) [data-testid="stHorizontalBlock"],
    [data-testid="stTabContent"]:has(#shopease-compact-notify) [data-testid="stHorizontalBlock"] {
        gap: .85rem !important;
    }
    [role="tabpanel"]:has(#shopease-compact-notify) h3,
    [role="tabpanel"]:has(#shopease-compact-notify) h4,
    [role="tabpanel"]:has(#shopease-compact-notify) label,
    [role="tabpanel"]:has(#shopease-compact-notify) p,
    [data-testid="stTabContent"]:has(#shopease-compact-notify) h3,
    [data-testid="stTabContent"]:has(#shopease-compact-notify) h4,
    [data-testid="stTabContent"]:has(#shopease-compact-notify) label,
    [data-testid="stTabContent"]:has(#shopease-compact-notify) p {
        color: #edf6ff !important;
    }
    [role="tabpanel"]:has(#shopease-compact-notify) [data-testid="stCaptionContainer"] p,
    [data-testid="stTabContent"]:has(#shopease-compact-notify) [data-testid="stCaptionContainer"] p {
        color: #a9c0d7 !important; font-size: .77rem !important;
        line-height: 1.25 !important;
    }
    [role="tabpanel"]:has(#shopease-compact-notify) [data-testid="stForm"],
    [data-testid="stTabContent"]:has(#shopease-compact-notify) [data-testid="stForm"] {
        border: none !important; padding: 0 !important; background: transparent !important;
    }
    [role="tabpanel"]:has(#shopease-compact-notify) [data-testid="stWidgetLabel"] p,
    [data-testid="stTabContent"]:has(#shopease-compact-notify) [data-testid="stWidgetLabel"] p {
        font-size: .86rem !important; line-height: 1.2 !important;
    }
    [role="tabpanel"]:has(#shopease-compact-notify) [data-testid="stRadio"] label,
    [data-testid="stTabContent"]:has(#shopease-compact-notify) [data-testid="stRadio"] label {
        padding: .1rem 0 !important;
    }
    [role="tabpanel"]:has(#shopease-compact-notify) input,
    [role="tabpanel"]:has(#shopease-compact-notify) [data-baseweb="select"] > div,
    [data-testid="stTabContent"]:has(#shopease-compact-notify) input,
    [data-testid="stTabContent"]:has(#shopease-compact-notify) [data-baseweb="select"] > div {
        background: #1b304c !important; color: #f3f8ff !important;
        border-color: #4b6684 !important;
    }
    [role="tabpanel"]:has(#shopease-compact-notify) [data-testid="stFormSubmitButton"] button,
    [data-testid="stTabContent"]:has(#shopease-compact-notify) [data-testid="stFormSubmitButton"] button {
        background: #287ce0 !important; color: #ffffff !important;
        border: none !important; min-height: 2.25rem !important;
    }
    [role="tabpanel"]:has(#shopease-compact-notify) [data-testid="stMarkdownContainer"] h3,
    [data-testid="stTabContent"]:has(#shopease-compact-notify) [data-testid="stMarkdownContainer"] h3 {
        padding: 0 !important; font-size: 1.22rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('### 🔔 Customer communication preferences')
    st.caption('Manage how you hear about your tickets. Saved settings apply to future updates in this demo.')

    with st.form(f'notification_preferences_{customer_id}'):
        left, right = st.columns([1, 1], gap='medium')
        with left:
            with st.container(border=True):
                st.markdown('**Communication channels**')
                st.caption('Choose the channels you prefer for support updates.')
                email = st.toggle('📧 Email notifications', value=bool(saved['email']),
                                  key=f'notify_email_{customer_id}',
                                  help='Email delivery is not connected in this demo.')
                sms = st.toggle('📱 SMS notifications', value=bool(saved['sms']),
                                key=f'notify_sms_{customer_id}',
                                help='SMS delivery is not connected in this demo.')
                whatsapp = st.toggle('💬 WhatsApp notifications', value=bool(saved['whatsapp']),
                                     key=f'notify_whatsapp_{customer_id}',
                                     help='WhatsApp delivery is not connected in this demo.')
                in_app = st.toggle('🔔 In-app notifications', value=bool(saved['in_app']),
                                   key=f'notify_inapp_{customer_id}',
                                   help='See updates within the support portal.')
                st.caption('Email, SMS and WhatsApp are preferences only; no messages are sent.')
                st.text_input('Email address', value=str(customer.get('email', '')),
                              disabled=True)
                mobile = st.text_input('Mobile number (SMS / WhatsApp)',
                                       value=str(saved['mobile']),
                                       placeholder='+91 98765 43210')
                st.caption('Mobile verification is not connected in this demo.')

        with right:
            with st.container(border=True):
                st.markdown('**Notification preferences**')
                frequencies = [
                    'Whenever the ticket status changes',
                    'Only when resolved or escalated',
                    'One daily summary',
                ]
                frequency = st.radio(
                    'When should we notify you?', frequencies,
                    index=frequencies.index(saved['frequency'])
                    if saved['frequency'] in frequencies else 0,
                )
                quiet_options = [
                    'No quiet hours', '10 PM to 7 AM',
                    '9 PM to 8 AM', '11 PM to 6 AM',
                ]
                quiet_hours = st.selectbox(
                    'Quiet hours (future SMS / WhatsApp)', quiet_options,
                    index=quiet_options.index(saved['quiet_hours'])
                    if saved['quiet_hours'] in quiet_options else 1,
                )
                st.caption('Daily summaries and quiet hours are not yet automated.')
                submit = st.form_submit_button('💾 Save preferences', type='primary')
                st.markdown('**Example notification**')
                st.info('🔔 Ticket update: Your complaint is under review.')

    if submit:
        try:
            save_preferences(customer_id, {
                'email': email, 'sms': sms, 'whatsapp': whatsapp,
                'in_app': in_app, 'frequency': frequency,
                'quiet_hours': quiet_hours, 'mobile': mobile.strip(),
            })
            st.success('Communication preferences saved.')
        except (OSError, ValueError) as exc:
            st.error(f'Could not save preferences: {exc}')

    with st.expander('📨 Actual support updates (expand to view)', expanded=False):
        recipient = f'customer:{customer_id}'
        try:
            events = unread_events(recipient, [str(t) for t in ticket_ids], 'staff')
            if not events:
                st.info('No unread support updates for your tickets.')
            else:
                st.caption(f'{len(events)} unread update(s)')
                for event in events[:15]:
                    with st.expander(
                        f"Ticket {event['ticket_id']} · "
                        f"{event['status'] or 'Support update'}"
                    ):
                        st.write(event['message'] or 'A ticket update was recorded.')
                        st.caption(event['time'])
                if st.button('Mark updates as read', key='notify_mark_read'):
                    mark_read(recipient, events)
                    st.rerun()
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            st.warning(f'Could not load support updates: {exc}')

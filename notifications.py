"""Local-only unread notification helpers for ShopEase demo."""
import csv
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
READS = ROOT / 'notification_reads.csv'
FIELDS = ['recipient', 'event_key', 'read_at']


def _rows(path):
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna('')
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def unread_events(recipient, ticket_ids, source):
    """Customer receives staff updates; staff receives customer replies."""
    filename = 'support_updates.csv' if source == 'staff' else 'customer_replies.csv'
    df = _rows(ROOT / filename)
    required = {'ticket_id', 'updated_at'} if source == 'staff' else {'ticket_id', 'created_at'}
    if df.empty or not required.issubset(df.columns):
        return []
    df = df[df['ticket_id'].isin({str(t) for t in ticket_ids})]
    reads = _rows(READS)
    seen = set()
    if {'recipient', 'event_key'}.issubset(reads.columns):
        seen = set(reads.loc[reads['recipient'] == str(recipient), 'event_key'])
    events = []
    # Include row index to distinguish multiple messages with identical timestamps.
    for idx, row in df.iterrows():
        ticket_id = str(row['ticket_id'])
        when = str(row['updated_at'] if source == 'staff' else row['created_at'])
        key = f'{source}:{ticket_id}:{idx}:{when}'
        if key not in seen:
            message = str(row.get('staff_note', '') if source == 'staff' else row.get('message', ''))
            events.append({'key': key, 'ticket_id': ticket_id, 'time': when, 'message': message,
                           'status': str(row.get('status', ''))})
    return sorted(events, key=lambda item: item['time'], reverse=True)


def mark_read(recipient, events):
    if not events:
        return
    existing = _rows(READS)
    seen = set(zip(existing.get('recipient', pd.Series(dtype=str)), existing.get('event_key', pd.Series(dtype=str))))
    READS.parent.mkdir(parents=True, exist_ok=True)
    with READS.open('a', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if handle.tell() == 0:
            writer.writeheader()
        for event in events:
            pair = (str(recipient), event['key'])
            if pair not in seen:
                writer.writerow({'recipient': pair[0], 'event_key': pair[1],
                                 'read_at': datetime.now(timezone.utc).isoformat()})
                seen.add(pair)

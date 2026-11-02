
"""
ShopEase Customer Support Dashboard

Displays dashboard statistics for the signed-in customer.

Data sources:
    ticket_logs.csv
    support_updates.csv

Used by:
    portal_customer_page.py

Main function:
    show_customer_dashboard(customer, orders)
"""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent

BACKGROUND = "#0b1e35"
CARD_BACKGROUND = "#112d4d"
CHART_BACKGROUND = "#0c192b"
TEXT_COLOR = "#eaf4ff"
MUTED_COLOR = "#a8bfd9"
GRID_COLOR = "#31445d"

BAR_WIDTH = 18


# ============================================================
# DATA HELPERS
# ============================================================

def read_csv(filename):
    """Safely read a CSV file from the project folder."""

    path = ROOT / filename

    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()

    try:
        return pd.read_csv(
            path,
            dtype=str,
            keep_default_na=False
        )
    except (
        OSError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError
    ):
        return pd.DataFrame()


def load_customer_tickets(customer, orders):
    """Load only tickets belonging to the signed-in customer."""

    tickets = read_csv("ticket_logs.csv")

    if tickets.empty:
        return pd.DataFrame()

    required_columns = {
        "ticket_id",
        "customer_name",
        "order_id"
    }

    if not required_columns.issubset(tickets.columns):
        return pd.DataFrame()

    customer_name = str(
        customer.get("name", "")
    ).strip().casefold()

    owned_order_ids = {
        str(order.get("order_id", "")).strip()
        for order in orders
    }

    name_matches = (
        tickets["customer_name"]
        .astype(str)
        .str.strip()
        .str.casefold()
        .eq(customer_name)
    )

    order_matches = (
        tickets["order_id"].isin(owned_order_ids)
        | tickets["order_id"].eq("")
    )

    tickets = tickets.loc[
        name_matches & order_matches
    ].copy()

    if tickets.empty:
        return tickets

    tickets = tickets.drop_duplicates(
        subset="ticket_id",
        keep="last"
    )

    defaults = {
        "timestamp": "",
        "category": "Other",
        "urgency": "Low",
        "status": "",
        "complaint": "",
        "response": "",
        "sentiment": ""
    }

    for column, default in defaults.items():
        if column not in tickets.columns:
            tickets[column] = default

    tickets["created_at"] = pd.to_datetime(
        tickets["timestamp"],
        errors="coerce",
        utc=True
    )

    tickets["current_status"] = (
        tickets["status"]
        .replace({
            "Resolved": "AI Response Provided",
            "Escalated": "Under Review"
        })
    )

    # Apply the most recent support-staff update.
    updates = read_csv("support_updates.csv")

    if (
        not updates.empty
        and {"ticket_id", "status"}.issubset(updates.columns)
    ):
        if "updated_at" in updates.columns:
            updates = updates.sort_values(
                "updated_at",
                kind="stable"
            )

        latest_updates = (
            updates.drop_duplicates(
                subset="ticket_id",
                keep="last"
            )
            .set_index("ticket_id")["status"]
        )

        tickets["current_status"] = (
            tickets["ticket_id"]
            .map(latest_updates)
            .fillna(tickets["current_status"])
        )

    return tickets


# ============================================================
# CHART STYLING
# ============================================================

def style_chart(chart):
    """Apply consistent dark styling to Altair charts."""

    return (
        chart
        .configure_view(
            stroke=None
        )
        .configure_axis(
            labelColor=TEXT_COLOR,
            titleColor=MUTED_COLOR,
            gridColor=GRID_COLOR,
            domain=False,
            tickColor=GRID_COLOR,
            labelFontSize=11,
            titleFontSize=11
        )
        .configure_legend(
            labelColor=TEXT_COLOR,
            titleColor=TEXT_COLOR,
            labelFontSize=11,
            orient="bottom"
        )
        .configure(
            background=CHART_BACKGROUND
        )
    )


def vertical_bar_chart(
    counts,
    color="#7cc5f7",
    height=205
):
    """
    Create a vertical bar chart with slim bars.

    Change BAR_WIDTH at the top of this file to adjust
    both the Category and Urgency chart bar widths.
    """

    chart_data = pd.DataFrame({
        "Group": counts.index.astype(str),
        "Tickets": counts.values.astype(int)
    })

    chart = (
        alt.Chart(chart_data)
        .mark_bar(
            color=color,
            size=BAR_WIDTH,
            cornerRadiusTopLeft=4,
            cornerRadiusTopRight=4
        )
        .encode(
            x=alt.X(
                "Group:N",
                sort=None,
                axis=alt.Axis(
                    title=None,
                    labelAngle=0,
                    labelLimit=110
                )
            ),
            y=alt.Y(
                "Tickets:Q",
                axis=alt.Axis(
                    title=None,
                    tickMinStep=1,
                    format="d"
                ),
                scale=alt.Scale(
                    domainMin=0
                )
            ),
            tooltip=[
                alt.Tooltip(
                    "Group:N",
                    title="Type"
                ),
                alt.Tooltip(
                    "Tickets:Q",
                    title="Tickets"
                )
            ]
        )
        .properties(
            height=height
        )
    )

    return style_chart(chart)


def status_bar_chart(counts, height=205):
    """Horizontal bars for current ticket statuses."""

    chart_data = pd.DataFrame({
        "Status": counts.index.astype(str),
        "Tickets": counts.values.astype(int)
    })

    chart = (
        alt.Chart(chart_data)
        .mark_bar(
            color="#7cc5f7",
            size=24,
            cornerRadiusEnd=4
        )
        .encode(
            y=alt.Y(
                "Status:N",
                sort=None,
                axis=alt.Axis(
                    title=None,
                    labelLimit=180
                )
            ),
            x=alt.X(
                "Tickets:Q",
                axis=alt.Axis(
                    title=None,
                    tickMinStep=1,
                    format="d"
                ),
                scale=alt.Scale(
                    domainMin=0
                )
            ),
            tooltip=[
                "Status:N",
                "Tickets:Q"
            ]
        )
        .properties(
            height=height
        )
    )

    return style_chart(chart)


def activity_line_chart(tickets, height=205):
    """
    Smooth ticket activity lines with horizontal date labels.

    Dates are plotted as discrete days, preventing repeated
    date labels from appearing between the actual data points.
    """

    dated = tickets.dropna(
        subset=["created_at"]
    ).copy()

    if dated.empty:
        return None

    dated["day"] = (
        dated["created_at"]
        .dt.strftime("%d %b")
    )

    dated["date_sort"] = (
        dated["created_at"]
        .dt.strftime("%Y-%m-%d")
    )

    daily = (
        dated.groupby(
            ["date_sort", "day"],
            as_index=False
        )
        .agg(
            Tickets=("ticket_id", "count"),
            AI_answered=(
                "status",
                lambda values: int(
                    values.str.casefold()
                    .eq("resolved")
                    .sum()
                )
            ),
            Escalated=(
                "status",
                lambda values: int(
                    values.str.casefold()
                    .eq("escalated")
                    .sum()
                )
            )
        )
        .sort_values("date_sort")
    )

    date_order = daily["day"].tolist()

    long_data = daily.melt(
        id_vars=["date_sort", "day"],
        value_vars=[
            "Tickets",
            "AI_answered",
            "Escalated"
        ],
        var_name="Series",
        value_name="Count"
    )

    long_data["Series"] = long_data["Series"].replace({
        "AI_answered": "AI answered"
    })

    colors = alt.Scale(
        domain=[
            "Tickets",
            "AI answered",
            "Escalated"
        ],
        range=[
            "#ff9fa8",
            "#74c8ff",
            "#307be8"
        ]
    )

    x_encoding = alt.X(
        "day:N",
        sort=date_order,
        axis=alt.Axis(
            title=None,
            labelAngle=0,
            labelOverlap=False,
            labelLimit=90
        )
    )

    y_encoding = alt.Y(
        "Count:Q",
        scale=alt.Scale(
            domainMin=0
        ),
        axis=alt.Axis(
            title=None,
            tickMinStep=1,
            format="d"
        )
    )

    base = (
        alt.Chart(long_data)
        .encode(
            x=x_encoding,
            y=y_encoding,
            color=alt.Color(
                "Series:N",
                scale=colors,
                legend=alt.Legend(
                    title=None,
                    direction="horizontal"
                )
            ),
            tooltip=[
                alt.Tooltip(
                    "date_sort:N",
                    title="Date"
                ),
                alt.Tooltip(
                    "Series:N",
                    title="Type"
                ),
                alt.Tooltip(
                    "Count:Q",
                    title="Tickets"
                )
            ]
        )
    )

    # Smooth, seamless lines.
    lines = base.mark_line(
        interpolate="monotone",
        strokeWidth=3
    )

    points = base.mark_circle(
        size=65
    )

    chart = (
        (lines + points)
        .properties(
            height=height
        )
    )

    return style_chart(chart)


# ============================================================
# DASHBOARD UI
# ============================================================

def show_customer_dashboard(customer, orders):
    """Render the customer support dashboard."""

    st.markdown(
        """
        <style>
        .dashboard-title {
            color: #f5f9ff;
            font-size: 1.65rem;
            font-weight: 750;
            margin-bottom: 0;
        }

        .dashboard-subtitle {
            color: #a8bfd9;
            font-size: 0.85rem;
            margin-bottom: 8px;
        }

        .dashboard-panel-title {
            color: #f5f9ff;
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 5px;
        }

        .dashboard-metric {
            background: #112d4d;
            border: 1px solid #315577;
            border-radius: 12px;
            padding: 12px 14px;
            min-height: 102px;
        }

        .dashboard-metric-label {
            color: #eaf4ff;
            font-size: 0.85rem;
            font-weight: 600;
        }

        .dashboard-metric-value {
            color: #ffffff;
            font-size: 1.8rem;
            font-weight: 750;
            line-height: 1.25;
            margin-top: 5px;
        }

        .dashboard-metric-note {
            color: #a8bfd9;
            font-size: 0.75rem;
            margin-top: 4px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    tickets = load_customer_tickets(
        customer,
        orders
    )

    heading_col, export_col = st.columns(
        [5, 1.2],
        vertical_alignment="center"
    )

    with heading_col:
        st.markdown(
            '<div class="dashboard-title">'
            '📊 My Support Dashboard'
            '</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="dashboard-subtitle">'
            'Your complaints, AI responses and '
            'support-team updates at a glance.'
            '</div>',
            unsafe_allow_html=True
        )

    with export_col:
        if not tickets.empty:
            export_data = tickets.drop(
                columns=["created_at"],
                errors="ignore"
            )

            st.download_button(
                "⬇ Export CSV",
                data=export_data.to_csv(index=False),
                file_name="shopease_dashboard.csv",
                mime="text/csv",
                use_container_width=True
            )

    if tickets.empty:
        st.info(
            "No support tickets yet. "
            "Raise a complaint to see your dashboard."
        )
        return

    # --------------------------------------------------------
    # FILTERS
    # --------------------------------------------------------

    with st.expander(
        "🔎 Filter dashboard",
        expanded=False
    ):
        filter_left, filter_right = st.columns(2)

        categories = sorted(
            value
            for value in tickets["category"].unique()
            if str(value).strip()
        )

        urgencies = sorted(
            value
            for value in tickets["urgency"].unique()
            if str(value).strip()
        )

        with filter_left:
            selected_category = st.selectbox(
                "Category",
                ["All categories"] + categories,
                key="dashboard_category_filter"
            )

        with filter_right:
            selected_urgency = st.selectbox(
                "Urgency",
                ["All urgencies"] + urgencies,
                key="dashboard_urgency_filter"
            )

    filtered = tickets.copy()

    if selected_category != "All categories":
        filtered = filtered.loc[
            filtered["category"].eq(selected_category)
        ]

    if selected_urgency != "All urgencies":
        filtered = filtered.loc[
            filtered["urgency"].eq(selected_urgency)
        ]

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    total = len(filtered)

    ai_answered = int(
        filtered["status"]
        .str.casefold()
        .eq("resolved")
        .sum()
    )

    review_mask = (
        filtered["current_status"]
        .str.contains(
            "review|escalat|pending|waiting",
            case=False,
            na=False
        )
    )

    under_review = int(
        review_mask.sum()
    )

    high_urgency = int(
        filtered["urgency"]
        .str.casefold()
        .eq("high")
        .sum()
    )

    escalated = int(
        filtered["status"]
        .str.casefold()
        .eq("escalated")
        .sum()
    )

    ai_percentage = (
        round(ai_answered / total * 100)
        if total else 0
    )

    metric_values = [
        (
            "Total tickets",
            total,
            "Your complaints"
        ),
        (
            "AI answered",
            ai_answered,
            f"{ai_percentage}% of tickets"
        ),
        (
            "Under review",
            under_review,
            "Needs attention"
        ),
        (
            "High urgency",
            high_urgency,
            "Priority cases"
        ),
        (
            "Escalated",
            escalated,
            "Initially escalated"
        )
    ]

    metric_columns = st.columns(
        5,
        gap="small"
    )

    for column, (label, value, note) in zip(
        metric_columns,
        metric_values
    ):
        with column:
            st.markdown(
                f"""
                <div class="dashboard-metric">
                    <div class="dashboard-metric-label">
                        {label}
                    </div>
                    <div class="dashboard-metric-value">
                        {value}
                    </div>
                    <div class="dashboard-metric-note">
                        {note}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    # --------------------------------------------------------
    # TOP ROW: ACTIVITY + STATUS
    # --------------------------------------------------------

    chart_left, chart_right = st.columns(
        [1.8, 1],
        gap="small"
    )

    with chart_left:
        with st.container(border=True):
            st.markdown(
                '<div class="dashboard-panel-title">'
                '📈 Ticket Activity'
                '</div>',
                unsafe_allow_html=True
            )

            activity_chart = activity_line_chart(
                filtered,
                height=205
            )

            if activity_chart is None:
                st.info(
                    "No dated tickets available."
                )
            else:
                st.altair_chart(
                    activity_chart,
                    use_container_width=True
                )

    with chart_right:
        with st.container(border=True):
            st.markdown(
                '<div class="dashboard-panel-title">'
                '📋 Current Ticket Status'
                '</div>',
                unsafe_allow_html=True
            )

            status_counts = (
                filtered["current_status"]
                .replace("", "Unknown")
                .value_counts()
            )

            if status_counts.empty:
                st.info("No statuses available.")
            else:
                st.altair_chart(
                    status_bar_chart(
                        status_counts,
                        height=205
                    ),
                    use_container_width=True
                )

    # --------------------------------------------------------
    # BOTTOM ROW: CATEGORY + URGENCY + ATTENTION
    # --------------------------------------------------------

    bottom_left, bottom_middle, bottom_right = (
        st.columns(
            3,
            gap="small"
        )
    )

    with bottom_left:
        with st.container(border=True):
            st.markdown(
                '<div class="dashboard-panel-title">'
                '📦 By Category'
                '</div>',
                unsafe_allow_html=True
            )

            category_counts = (
                filtered["category"]
                .replace("", "Other")
                .value_counts()
            )

            if category_counts.empty:
                st.info("No categories available.")
            else:
                st.altair_chart(
                    vertical_bar_chart(
                        category_counts,
                        color="#7cc5f7",
                        height=205
                    ),
                    use_container_width=True
                )

    with bottom_middle:
        with st.container(border=True):
            st.markdown(
                '<div class="dashboard-panel-title">'
                '🚦 By Urgency'
                '</div>',
                unsafe_allow_html=True
            )

            urgency_counts = (
                filtered["urgency"]
                .replace("", "Unknown")
                .value_counts()
            )

            if urgency_counts.empty:
                st.info("No urgency data available.")
            else:
                st.altair_chart(
                    vertical_bar_chart(
                        urgency_counts,
                        color="#ffab83",
                        height=205
                    ),
                    use_container_width=True
                )

    with bottom_right:
        with st.container(border=True):
            st.markdown(
                '<div class="dashboard-panel-title">'
                '📝 Needs Attention'
                '</div>',
                unsafe_allow_html=True
            )

            pending = (
                filtered.loc[review_mask]
                .sort_values(
                    "created_at",
                    ascending=False,
                    na_position="last"
                )
            )

            if pending.empty:
                st.success(
                    "No tickets waiting for review."
                )
            else:
                for _, ticket in pending.head(4).iterrows():
                    ticket_id = str(
                        ticket["ticket_id"]
                    )

                    category = str(
                        ticket["category"]
                    )

                    urgency = str(
                        ticket["urgency"]
                    )

                    status = str(
                        ticket["current_status"]
                    )

                    st.markdown(
                        f"**🎫 {ticket_id}**"
                    )

                    st.caption(
                        f"{category} · "
                        f"{urgency} · "
                        f"{status}"
                    )

                if len(pending) > 4:
                    st.caption(
                        f"+ {len(pending) - 4} more tickets"
                    )

    # --------------------------------------------------------
    # TICKET DETAILS
    # --------------------------------------------------------

    with st.expander(
        "📋 View all dashboard tickets",
        expanded=False
    ):
        display_columns = [
            "ticket_id",
            "timestamp",
            "category",
            "urgency",
            "current_status",
            "complaint"
        ]

        display = filtered.sort_values(
            "created_at",
            ascending=False,
            na_position="last"
        )

        st.dataframe(
            display[display_columns],
            use_container_width=True,
            hide_index=True,
            column_config={
                "ticket_id": "Ticket",
                "timestamp": "Created",
                "category": "Category",
                "urgency": "Urgency",
                "current_status": "Status",
                "complaint": "Complaint"
            }
        )

    st.caption(
        "Statistics are calculated from your local ticket records. "
        "An AI response does not necessarily mean that the "
        "underlying order issue has been completed."
    )

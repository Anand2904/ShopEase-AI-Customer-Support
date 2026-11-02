
"""ShopEase unified local demo with role-based navigation.

Run:
    streamlit run unified_portal.py

Set SHOP_SUPPORT_PASSWORD in .env for staff access.
"""

import hmac
import os
import runpy
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from customer_portal import (
    authenticate_customer,
    initialize_database,
)


ROOT = Path(__file__).resolve().parent

load_dotenv(ROOT / ".env")

st.set_page_config(
    page_title="ShopEase | Unified Portal",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

initialize_database()


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
        max-width: 1450px;
        padding-top: .8rem;
        padding-bottom: 1.4rem;
    }

    h1 {
        font-size: 1.6rem !important;
    }

    h2 {
        font-size: 1.3rem !important;
    }

    h3 {
        font-size: 1.1rem !important;
    }

    p, li {
        font-size: .9rem;
        line-height: 1.5;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.45rem !important;
    }

    [data-testid="stSidebar"] {
        background: #081b31;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================

if "unified_role" not in st.session_state:
    st.session_state.unified_role = None

if "customer" not in st.session_state:
    st.session_state.customer = None


def logout():
    st.session_state.unified_role = None
    st.session_state.customer = None
    st.rerun()


# ============================================================
# PAGE HELPERS
# ============================================================

def run_page(filename):
    path = ROOT / filename

    if not path.is_file():
        st.error(
            f"Missing {filename}. "
            "Copy all unified portal files into the project folder."
        )
        return

    runpy.run_path(
        str(path),
        run_name="__main__",
    )


def customer_page():
    run_page("portal_customer_page.py")


def support_page():
    run_page("portal_support_page.py")


def analytics_page():
    run_page("portal_analytics_page.py")


def customer_preview():
    """
    Staff-only preview of the sample customer account.
    Not intended for real customer impersonation.
    """

    preview = authenticate_customer(
        "aarav@example.com",
        "DemoPass123!",
    )

    if preview is None:
        st.error(
            "Demo preview customer is missing "
            "from the local sample database."
        )
        return

    st.info(
        "Staff demo preview: showing the sample customer Aarav. "
        "This is not a real customer session."
    )

    st.session_state.customer = preview

    run_page("portal_customer_page.py")


# ============================================================
# LOGIN SCREEN
# ============================================================

if st.session_state.unified_role is None:

    st.title("🛍️ ShopEase | One Portal")

    st.caption(
        "One address for customer support, staff tickets, "
        "and analytics. Local demonstration only."
    )

    left, middle, right = st.columns(
        [1, 1.6, 1]
    )

    with middle:
        with st.container(border=True):

            st.subheader("Sign in")

            mode = st.radio(
                "Account type",
                ["Customer", "Support staff"],
                horizontal=True,
            )

            with st.form("unified_login"):

                if mode == "Customer":
                    email = st.text_input(
                        "Email",
                        placeholder="aarav@example.com",
                    )

                    password = st.text_input(
                        "Password",
                        type="password",
                    )

                else:
                    email = ""

                    password = st.text_input(
                        "Support password",
                        type="password",
                    )

                submitted = st.form_submit_button(
                    "Sign in",
                    use_container_width=True,
                )

            if submitted:

                if mode == "Customer":

                    user = authenticate_customer(
                        email.strip(),
                        password,
                    )

                    if user:
                        st.session_state.customer = user
                        st.session_state.unified_role = "customer"
                        st.rerun()

                    st.error(
                        "Invalid customer credentials."
                    )

                else:

                    expected = os.getenv(
                        "SHOP_SUPPORT_PASSWORD",
                        "",
                    )

                    if not expected:
                        st.error(
                            "Set SHOP_SUPPORT_PASSWORD in your "
                            ".env file before staff login."
                        )

                    elif hmac.compare_digest(
                        password.encode(),
                        expected.encode(),
                    ):
                        st.session_state.unified_role = "staff"
                        st.session_state.customer = None
                        st.rerun()

                    else:
                        st.error(
                            "Incorrect support password."
                        )

            st.caption(
                "Demo customer: "
                "aarav@example.com / DemoPass123!"
            )

    st.info(
        "Local demo only. Do not deploy publicly: "
        "this uses simple session authentication "
        "and CSV-based storage."
    )

    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

role = st.session_state.unified_role

with st.sidebar:

    st.markdown("### 🛍️ ShopEase")

    st.caption(
        "Unified support workspace"
    )

    if role == "staff":
        display_name = "Support staff"
    else:
        display_name = (
            st.session_state.customer or {}
        ).get("name", "Customer")

    st.write(
        "**Signed in as:** " + display_name
    )

    if st.button(
        "Sign out",
        use_container_width=True,
    ):
        logout()

    st.divider()

    if role == "staff":
        st.caption(
            "Staff can manage tickets, see analytics, "
            "and preview the demo customer portal."
        )
    else:
        st.caption(
            "Customers can access only their own portal."
        )

    robot_path = (
        ROOT
        / "assets"
        / "shopease_sidebar_banner.png"
    )

    if robot_path.is_file():

        st.markdown(
            '<div style="height:12px"></div>',
            unsafe_allow_html=True,
        )

        st.image(
            str(robot_path),
            use_container_width=True,
        )

        st.caption(
            "🤖 ShopEase AI support assistant"
        )


# ============================================================
# ROLE-BASED NAVIGATION
# ============================================================

if role == "staff":

    pages = [

        st.Page(
            customer_preview,
            title="Customer Portal (demo)",
            icon="🛍️",
            url_path="customer-preview",
            default=True,
        ),

        st.Page(
            support_page,
            title="Support Dashboard",
            icon="🎧",
            url_path="support-dashboard",
        ),

        st.Page(
            analytics_page,
            title="Analytics Dashboard",
            icon="📊",
            url_path="analytics-dashboard",
        ),

    ]

else:

    pages = [

        st.Page(
            customer_page,
            title="My Customer Portal",
            icon="🛍️",
            url_path="my-customer-portal",
            default=True,
        ),

    ]


navigation = st.navigation(
    pages,
    position="sidebar",
)

navigation.run()

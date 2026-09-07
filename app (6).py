
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
from google.cloud import firestore
from datetime import datetime, timezone

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Beauty Parlour AI Assistant",
    page_icon="💇",
    layout="wide"
)

# =========================================================
# AUTO REFRESH
# =========================================================

st_autorefresh(
    interval=30 * 1000,
    key="beauty_parlour_refresh"
)

# =========================================================
# FIRESTORE
# =========================================================

db = firestore.Client()

FEEDBACK_COLLECTION = "feedback"

# =========================================================
# SESSION STATE
# =========================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "step" not in st.session_state:
    st.session_state.step = 0

if "feedback" not in st.session_state:
    st.session_state.feedback = {
        "customer_name": "",
        "service": "",
        "rating": "",
        "staff_experience": "",
        "liked": "",
        "improvement": "",
        "visit_again": ""
    }

if "completed" not in st.session_state:
    st.session_state.completed = False

# =========================================================
# QUESTIONS
# =========================================================

questions = [
    "May I have your name, please?",
    "Which beauty service did you receive today?",
    "How would you rate your experience from 1 to 5?",
    "How would you describe the experience of our staff?",
    "What did you like most about your visit?",
    "What could we improve for your next visit?",
    "Would you visit us again?"
]

fields = [
    "customer_name",
    "service",
    "rating",
    "staff_experience",
    "liked",
    "improvement",
    "visit_again"
]

# =========================================================
# SAVE FEEDBACK TO FIRESTORE
# =========================================================

def save_feedback(feedback):

    firestore_feedback = {
        "customer_name": feedback["customer_name"],
        "service": feedback["service"],
        "rating": int(feedback["rating"]),
        "staff_experience": feedback["staff_experience"],
        "liked": feedback["liked"],
        "improvement": feedback["improvement"],
        "visit_again": feedback["visit_again"],
        "timestamp": datetime.now(timezone.utc)
    }

    doc_ref = db.collection(
        FEEDBACK_COLLECTION
    ).document()

    doc_ref.set(
        firestore_feedback
    )

    return doc_ref.id

# =========================================================
# LOAD FEEDBACK FROM FIRESTORE
# =========================================================

def load_feedback():

    documents = (
        db.collection(
            FEEDBACK_COLLECTION
        )
        .stream()
    )

    rows = []

    for document in documents:

        data = document.to_dict()

        timestamp = data.get("timestamp")

        if timestamp is not None:

            try:
                timestamp = timestamp.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except Exception:
                timestamp = str(timestamp)

        rows.append({
            "timestamp": timestamp,
            "customer_name": data.get(
                "customer_name", ""
            ),
            "service": data.get(
                "service", ""
            ),
            "rating": data.get(
                "rating", ""
            ),
            "staff_experience": data.get(
                "staff_experience", ""
            ),
            "liked": data.get(
                "liked", ""
            ),
            "improvement": data.get(
                "improvement", ""
            ),
            "visit_again": data.get(
                "visit_again", ""
            )
        })

    columns = [
        "timestamp",
        "customer_name",
        "service",
        "rating",
        "staff_experience",
        "liked",
        "improvement",
        "visit_again"
    ]

    return pd.DataFrame(
        rows,
        columns=columns
    )

# =========================================================
# RESET CHAT
# =========================================================

def reset_chat():

    st.session_state.messages = []

    st.session_state.step = 0

    st.session_state.feedback = {
        "customer_name": "",
        "service": "",
        "rating": "",
        "staff_experience": "",
        "liked": "",
        "improvement": "",
        "visit_again": ""
    }

    st.session_state.completed = False

# =========================================================
# APPLICATION
# =========================================================

st.title("💇 Beauty Parlour AI Assistant")

st.caption(
    "Customer Feedback Chatbot + Owner Business Dashboard"
)

chat_tab, dashboard_tab = st.tabs(
    [
        "💬 Customer Feedback",
        "📊 Owner Dashboard"
    ]
)

# =========================================================
# CUSTOMER FEEDBACK
# =========================================================

with chat_tab:

    st.header(
        "💬 Beauty Parlour Customer Feedback"
    )

    st.write(
        "We value your experience. "
        "Please share your feedback with us. 😊"
    )

    # -----------------------------------------------------
    # START CONVERSATION
    # -----------------------------------------------------

    if not st.session_state.messages:

        st.session_state.messages.append({
            "role": "assistant",
            "content": questions[0]
        })

    # -----------------------------------------------------
    # DISPLAY MESSAGES
    # -----------------------------------------------------

    for message in st.session_state.messages:

        with st.chat_message(
            message["role"]
        ):

            st.write(
                message["content"]
            )

    # -----------------------------------------------------
    # CHAT INPUT
    # -----------------------------------------------------

    if not st.session_state.completed:

        user_input = st.chat_input(
            "Type your answer..."
        )

        if user_input:

            user_input = user_input.strip()

            if user_input:

                st.session_state.messages.append({
                    "role": "user",
                    "content": user_input
                })

                current_step = (
                    st.session_state.step
                )

                current_field = (
                    fields[current_step]
                )

                # -----------------------------------------
                # RATING VALIDATION
                # -----------------------------------------

                if current_field == "rating":

                    try:

                        rating = int(user_input)

                        if rating < 1 or rating > 5:

                            st.session_state.messages.append({
                                "role": "assistant",
                                "content":
                                "Please enter a rating from 1 to 5."
                            })

                            st.rerun()

                        user_input = str(rating)

                    except ValueError:

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content":
                            "Please enter a number from 1 to 5."
                        })

                        st.rerun()

                # -----------------------------------------
                # SAVE ANSWER IN SESSION
                # -----------------------------------------

                st.session_state.feedback[
                    current_field
                ] = user_input

                st.session_state.step += 1

                # -----------------------------------------
                # NEXT QUESTION
                # -----------------------------------------

                if (
                    st.session_state.step
                    < len(questions)
                ):

                    next_question = questions[
                        st.session_state.step
                    ]

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": next_question
                    })

                # -----------------------------------------
                # COMPLETED
                # -----------------------------------------

                else:

                    try:

                        doc_id = save_feedback(
                            st.session_state.feedback
                        )

                        st.session_state.completed = True

                        customer = (
                            st.session_state.feedback[
                                "customer_name"
                            ]
                        )

                        service = (
                            st.session_state.feedback[
                                "service"
                            ]
                        )

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content":
                            f"Thank you, {customer}! 😊\n\n"
                            f"We appreciate your feedback "
                            f"about your **{service}** service.\n\n"
                            "Your feedback has been recorded "
                            "successfully. Thank you for "
                            "visiting us! 💇✨"
                        })

                    except Exception as e:

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content":
                            "Your feedback could not be saved. "
                            "Please try again."
                        })

                        st.error(
                            f"Firestore error: {e}"
                        )

                st.rerun()

    else:

        st.success(
            "✅ Thank you! Your feedback has been recorded."
        )

        if st.button(
            "🔄 Give Feedback Again"
        ):

            reset_chat()

            st.rerun()

# =========================================================
# OWNER DASHBOARD
# =========================================================

with dashboard_tab:

    st.header(
        "📊 Beauty Parlour Owner Insights Dashboard"
    )

    st.caption(
        "Live customer feedback and business insights"
    )

    # -----------------------------------------------------
    # LOAD FIRESTORE DATA
    # -----------------------------------------------------

    try:

        df = load_feedback()

    except Exception as e:

        st.error(
            f"Unable to load Firestore data: {e}"
        )

        df = pd.DataFrame()

    # -----------------------------------------------------
    # EMPTY DATA
    # -----------------------------------------------------

    if len(df) == 0:

        st.info(
            "👋 No customer feedback has been received yet."
        )

        st.write(
            "Complete the customer feedback chatbot "
            "to see live results here."
        )

    else:

        # -------------------------------------------------
        # RATING
        # -------------------------------------------------

        df["rating"] = pd.to_numeric(
            df["rating"],
            errors="coerce"
        )

        total_customers = len(df)

        average_rating = df["rating"].mean()

        five_star = (
            df["rating"] == 5
        ).sum()

        return_customers = (
            df["visit_again"]
            .astype(str)
            .str.strip()
            .str.lower()
            == "yes"
        ).sum()

        # =================================================
        # KPI
        # =================================================

        col1, col2, col3, col4 = st.columns(4)

        with col1:

            st.metric(
                "👥 Total Responses",
                total_customers
            )

        with col2:

            st.metric(
                "⭐ Average Rating",
                f"{average_rating:.1f}/5"
            )

        with col3:

            st.metric(
                "🌟 5-Star Ratings",
                f"{five_star}/{total_customers}"
            )

        with col4:

            st.metric(
                "🔁 Would Return",
                f"{return_customers}/{total_customers}"
            )

        st.divider()

        # =================================================
        # SERVICE USAGE
        # =================================================

        st.subheader(
            "💇 Service Usage"
        )

        service_counts = (
            df["service"]
            .astype(str)
            .str.strip()
            .replace("", "Unknown")
            .value_counts()
        )

        col1, col2 = st.columns(2)

        with col1:

            st.bar_chart(
                service_counts
            )

        with col2:

            st.dataframe(
                service_counts.rename(
                    "Customers"
                ),
                use_container_width=True
            )

        st.divider()

        # =================================================
        # STAFF EXPERIENCE
        # =================================================

        st.subheader(
            "👩‍💼 Staff Experience"
        )

        staff_counts = (
            df["staff_experience"]
            .astype(str)
            .str.strip()
            .replace("", "Not provided")
            .value_counts()
        )

        st.bar_chart(
            staff_counts
        )

        st.divider()

        # =================================================
        # WHAT CUSTOMERS LIKE
        # =================================================

        st.subheader(
            "👍 What Customers Like"
        )

        liked_counts = (
            df["liked"]
            .astype(str)
            .str.strip()
            .replace("", "Not provided")
            .value_counts()
        )

        st.bar_chart(
            liked_counts
        )

        st.divider()

        # =================================================
        # IMPROVEMENT FEEDBACK
        # =================================================

        st.subheader(
            "⚠️ Improvement Feedback"
        )

        improvement_counts = (
            df["improvement"]
            .astype(str)
            .str.strip()
            .replace("", "Not provided")
            .value_counts()
        )

        col1, col2 = st.columns(2)

        with col1:

            st.bar_chart(
                improvement_counts
            )

        with col2:

            no_improvement = (
                df["improvement"]
                .astype(str)
                .str.strip()
                .str.lower()
                .isin([
                    "nothing",
                    "no",
                    "none",
                    "no improvement"
                ])
            ).sum()

            improvement_requested = (
                total_customers
                - no_improvement
            )

            st.write(
                f"✅ No improvement needed: "
                f"**{no_improvement}**"
            )

            st.write(
                f"⚠️ Improvement requested: "
                f"**{improvement_requested}**"
            )

        st.divider()

        # =================================================
        # CUSTOMER FEEDBACK
        # =================================================

        st.subheader(
            "📋 Customer Feedback"
        )

        display_df = df.rename(
            columns={
                "timestamp": "Timestamp",
                "customer_name": "Customer",
                "service": "Service",
                "rating": "Rating",
                "staff_experience":
                    "Staff Experience",
                "liked":
                    "Liked Most",
                "improvement":
                    "Improvement",
                "visit_again":
                    "Visit Again"
            }
        )

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        # =================================================
        # BUSINESS INSIGHTS
        # =================================================

        st.subheader(
            "🤖 AI Business Insights"
        )

        satisfaction_percentage = (
            five_star
            / total_customers
        ) * 100

        return_percentage = (
            return_customers
            / total_customers
        ) * 100

        st.success(
            f"🌟 **Customer Satisfaction:** "
            f"{satisfaction_percentage:.0f}% "
            f"of customers gave a 5-star rating."
        )

        st.info(
            f"🔁 **Customer Loyalty:** "
            f"{return_percentage:.0f}% "
            f"of customers said they would visit again."
        )

        most_popular_service = (
            service_counts.idxmax()
        )

        st.write(
            f"💇 **Most Popular Service:** "
            f"{most_popular_service}"
        )

        most_liked = (
            liked_counts.idxmax()
        )

        st.write(
            f"👍 **Customers Like Most:** "
            f"{most_liked}"
        )

        most_common_staff = (
            staff_counts.idxmax()
        )

        st.write(
            f"👩‍💼 **Most Common Staff Experience:** "
            f"{most_common_staff}"
        )

        if improvement_requested > 0:

            st.warning(
                f"⚠️ **Action Required:** "
                f"{improvement_requested} customer(s) "
                f"requested an improvement."
            )

        else:

            st.success(
                "✅ No improvement requests were received."
            )

        st.divider()

        st.caption(
            "🔄 Dashboard automatically refreshes every 30 seconds."
        )

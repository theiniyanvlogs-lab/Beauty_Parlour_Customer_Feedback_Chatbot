
import streamlit as st
from google.cloud import firestore
from datetime import datetime, timezone

st.set_page_config(
    page_title="Beauty Parlour Customer Feedback",
    page_icon="💇"
)

db = firestore.Client()

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


def save_feedback(feedback):

    data = {
        "customer_name": feedback["customer_name"],
        "service": feedback["service"],
        "rating": int(feedback["rating"]),
        "staff_experience": feedback["staff_experience"],
        "liked": feedback["liked"],
        "improvement": feedback["improvement"],
        "visit_again": feedback["visit_again"],
        "timestamp": datetime.now(timezone.utc)
    }

    db.collection("feedback").add(data)


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


st.title("💇 Beauty Parlour Customer Feedback")

st.write(
    "We value your experience. "
    "Please share your feedback with us. 😊"
)


if not st.session_state.messages:

    st.session_state.messages.append({
        "role": "assistant",
        "content": questions[0]
    })


for message in st.session_state.messages:

    with st.chat_message(message["role"]):
        st.write(message["content"])


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

            current_step = st.session_state.step
            current_field = fields[current_step]

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

            st.session_state.feedback[
                current_field
            ] = user_input

            st.session_state.step += 1

            if st.session_state.step < len(questions):

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": questions[
                        st.session_state.step
                    ]
                })

            else:

                try:

                    save_feedback(
                        st.session_state.feedback
                    )

                    st.session_state.completed = True

                    customer = (
                        st.session_state.feedback[
                            "customer_name"
                        ]
                    )

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content":
                        f"Thank you, {customer}! 😊\n\n"
                        "Your feedback has been recorded "
                        "successfully. 💇✨"
                    })

                except Exception as e:

                    st.error(
                        f"Unable to save feedback: {e}"
                    )

            st.rerun()

else:

    st.success(
        "✅ Thank you! Your feedback has been recorded."
    )

    if st.button("🔄 Give Feedback Again"):

        reset_chat()
        st.rerun()

from aiogram.fsm.state import State, StatesGroup

class FeedbackStates(StatesGroup):
    awaiting_feedback_text = State() # User will be prompted to send their feedback text
    # We might add more states later if the feedback process becomes more complex
    # (e.g., awaiting_confirmation, awaiting_rating_for_feedback_itself, etc.) 
from aiogram.fsm.state import State, StatesGroup

class FeedbackStates(StatesGroup):
    awaiting_feedback_text = State()

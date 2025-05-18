from aiogram.fsm.state import State, StatesGroup

class SolveCaseStates(StatesGroup):
    awaiting_solution = State()

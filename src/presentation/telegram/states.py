from aiogram.fsm.state import State, StatesGroup


class ExcusedRequestState(StatesGroup):
    waiting_reason = State()

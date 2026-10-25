from aiogram.fsm.state import State, StatesGroup


class SearchStates(StatesGroup):
    waiting_for_query = State()


class ServiceOrderStates(StatesGroup):
    waiting_for_prompt = State()
    confirming_order = State()


class FocusSessionStates(StatesGroup):
    choosing_subject = State()


class FlashcardStates(StatesGroup):
    waiting_for_deck_title = State()
    waiting_for_front = State()
    waiting_for_back = State()


class ProfileStates(StatesGroup):
    waiting_for_major = State()
    waiting_for_goals = State()

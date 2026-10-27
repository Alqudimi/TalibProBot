from aiogram.fsm.state import State, StatesGroup


class OnboardingFSM(StatesGroup):
    wait_level = State()
    wait_subjects = State()
    wait_tz = State()


class SearchFSM(StatesGroup):
    wait_query = State()


class ServiceInputFSM(StatesGroup):
    wait_text = State()
    wait_file = State()
    wait_choice = State()
    wait_confirm = State()


class BookingFSM(StatesGroup):
    pick_slot = State()
    wait_note = State()
    wait_confirm = State()


class TicketFSM(StatesGroup):
    pick_topic = State()
    wait_text = State()
    wait_attach = State()


class ReviewFSM(StatesGroup):
    wait_stars = State()
    wait_text = State()


class ProfileFSM(StatesGroup):
    wait_level = State()
    wait_subjects = State()
    wait_tz = State()


class PlanFSM(StatesGroup):
    wait_exam_date = State()
    pick_hours = State()
    confirm_plan = State()


class TimerFSM(StatesGroup):
    idle = State()
    focus = State()
    break_ = State()
    paused = State()


class GroupFSM(StatesGroup):
    wait_code = State()
    wait_intro = State()


class AdminCatalogFSM(StatesGroup):
    pick_service = State()
    edit_field = State()
    wait_price = State()
    wait_terms = State()
    confirm_publish = State()


class AdminRefundFSM(StatesGroup):
    pick_payment = State()
    wait_reason = State()
    confirm = State()


class AdminBroadcastFSM(StatesGroup):
    compose_text = State()
    compose_media = State()
    pick_audience = State()
    preview = State()
    confirm = State()


class AdminUserFSM(StatesGroup):
    wait_search = State()
    pick_role = State()
    wait_reason = State()


class FlashcardFSM(StatesGroup):
    wait_deck_title = State()
    wait_card_front = State()
    wait_card_back = State()


# Backward-compatibility aliases
SearchStates = SearchFSM
ServiceOrderStates = ServiceInputFSM
FocusSessionStates = TimerFSM
FlashcardStates = FlashcardFSM
ProfileStates = ProfileFSM

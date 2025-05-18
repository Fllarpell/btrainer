from aiogram.fsm.state import State, StatesGroup

class AdminStates(StatesGroup):
    awaiting_tg_id_for_search = State()
    
    awaiting_user_db_id_for_view = State()
    awaiting_block_reason = State()
    awaiting_broadcast_message_text = State()
    awaiting_broadcast_confirmation = State()

    awaiting_case_title_manual_add = State()
    awaiting_case_text_manual_add = State()
    awaiting_case_id_for_edit_title = State()
    awaiting_new_case_title = State()
    awaiting_case_id_for_edit_text = State()
    awaiting_new_case_text = State()

    awaiting_new_welcome_message = State()
    awaiting_new_help_message = State() 

    # States for AI Reference Management
    awaiting_ai_ref_type = State()
    awaiting_ai_ref_description = State() # General description state
    awaiting_ai_ref_url = State() # Specifically for URL if type is URL
    awaiting_ai_ref_citation = State() # For citation details
    # For editing, we might reuse above or create specific edit states if flow differs
    awaiting_ai_ref_id_for_edit = State()
    awaiting_ai_ref_field_to_edit = State() # If we allow editing specific fields
    awaiting_ai_ref_new_value_for_edit = State() 
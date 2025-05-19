from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from app.db.models import User, UserRole, AISourceType
from aiogram.filters.callback_data import CallbackData
from typing import Optional
from datetime import datetime

class AdminUserCallback(CallbackData, prefix="admin_user"):
    action: str
    user_id: int
    page: Optional[int] = None

class AdminCaseCallback(CallbackData, prefix="admin_case"):
    action: str
    case_id: Optional[int] = None
    page: Optional[int] = None

class OnboardingCallback(CallbackData, prefix="onboarding"):
    action: str

class CaseAction(CallbackData, prefix="case_action"):
    pass

class UserProfileCallback(CallbackData, prefix="user_profile"):
    action: str

def get_main_menu_keyboard(user_role: UserRole = UserRole.USER) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📝 Новый кейс"), KeyboardButton(text="📊 Мой прогресс")],
        [KeyboardButton(text="💬 Оставить отзыв"), KeyboardButton(text="ℹ️ Помощь")],
        [KeyboardButton(text="💳 Тарифы и подписка")]
    ]
    if user_role == UserRole.ADMIN:
        buttons.append([KeyboardButton(text="👑 Админ панель")])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_onboarding_welcome_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Расскажи подробнее!", callback_data=OnboardingCallback(action="tell_me_more").pack())]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_onboarding_explanation_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Как мне начать?", callback_data=OnboardingCallback(action="how_to_start").pack())]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_onboarding_trial_offer_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🚀 Начать 7-дневный бесплатный пробный период", callback_data=OnboardingCallback(action="start_trial").pack())],
        # TODO: Add "View Subscription Plans" button later if needed, pointing to tariff_handlers
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_panel_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Пользователи", callback_data="admin_users_menu")
    )
    builder.row(
        InlineKeyboardButton(text="Кейсы", callback_data="admin_cases_menu")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика запросов БД", callback_data="admin_total_db_requests")
    )
    builder.row(
        InlineKeyboardButton(text="📚 Управление источниками ИИ", callback_data="admin_ai_references_menu")
    )
    builder.row(
        InlineKeyboardButton(text="📈 Конверсия из триала", callback_data="admin_trial_conversion_stats")
    )
    return builder.as_markup()

def get_admin_users_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Список пользователей (стр. 1)", callback_data="admin_list_users_page_0")],
        [InlineKeyboardButton(text="Найти пользователя (по TG ID)", callback_data="admin_find_user_by_tg_id_prompt")],
        [InlineKeyboardButton(text="⬅️ Назад (в админ меню)", callback_data="admin_main_menu_back")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def get_admin_user_list_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons_row = []
    if current_page > 0:
        buttons_row.append(InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"admin_list_users_page_{current_page - 1}"))
    
    buttons_row.append(InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}", callback_data="admin_noop")) # No operation button

    if current_page < total_pages - 1:
        buttons_row.append(InlineKeyboardButton(text="След. ➡️", callback_data=f"admin_list_users_page_{current_page + 1}"))
    
    keyboard_buttons = [buttons_row]
    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад (в меню Пользователи)", callback_data="admin_users_menu_back")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    return keyboard

def get_admin_user_actions_keyboard(db_user: User) -> InlineKeyboardMarkup:
    buttons = []

    if db_user.is_blocked:
        buttons.append([InlineKeyboardButton(text="🔓 Разблокировать пользователя", callback_data=f"admin_unblock_user_{db_user.id}")])
    else:
        buttons.append([InlineKeyboardButton(text="🚫 Заблокировать пользователя", callback_data=f"admin_block_user_{db_user.id}")])

    if db_user.role == UserRole.ADMIN:
        buttons.append([InlineKeyboardButton(text="Сделать Пользователем", callback_data=f"admin_set_role_user_{db_user.id}")])
    else:
        buttons.append([InlineKeyboardButton(text="Сделать Администратором", callback_data=f"admin_set_role_admin_{db_user.id}")])
    
    buttons.append([InlineKeyboardButton(text="🎁 Управление триалом", callback_data=f"admin_manage_trial_{db_user.id}")])
    buttons.append([InlineKeyboardButton(text="💳 Управление подпиской", callback_data=f"admin_manage_sub_{db_user.id}")])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад (в меню Пользователи)", callback_data="admin_users_menu_back")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def get_admin_cases_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Список всех кейсов (стр. 1)", callback_data="admin_list_cases_page_0")],
        #[InlineKeyboardButton(text="Добавить кейс вручную", callback_data="admin_add_case_manual_prompt")],
        #[InlineKeyboardButton(text="Найти кейс (по ID)", callback_data="admin_find_case_by_id_prompt")],
        [InlineKeyboardButton(text="⬅️ Назад (в гл. админ меню)", callback_data="admin_main_menu_back")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def get_admin_case_list_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons_row = []
    if current_page > 0:
        buttons_row.append(InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"admin_list_cases_page_{current_page - 1}"))
    
    buttons_row.append(InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}", callback_data="admin_noop")) # No operation button

    if current_page < total_pages - 1:
        buttons_row.append(InlineKeyboardButton(text="След. ➡️", callback_data=f"admin_list_cases_page_{current_page + 1}"))
    
    keyboard_buttons = []
    if buttons_row:
        keyboard_buttons.append(buttons_row)
    
    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад (в меню Кейсы)", callback_data="admin_cases_menu")]) 
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    return keyboard

def get_subscribe_inline_keyboard(plan_id: str, plan_title: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"✨ Оформить {plan_title}",
        callback_data=f"subscribe_action:{plan_id}"
    )
    return builder.as_markup()

def get_after_case_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔀 Запросить другой кейс", callback_data="request_another_case")
    builder.adjust(1)
    return builder.as_markup()

def get_after_solution_analysis_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💼 Получить новый кейс", callback_data="request_case_again")
    return builder.as_markup()

def get_admin_ai_references_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Список источников (Стр. 1)", callback_data="admin_list_ai_references_page_0"))
    builder.row(InlineKeyboardButton(text="➕ Добавить новый источник", callback_data="admin_add_ai_reference_prompt"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад (в гл. админ меню)", callback_data="admin_main_menu_back"))
    return builder.as_markup()

def get_admin_ai_source_type_select_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for source_type_enum_member in AISourceType:
        builder.button(
            text=source_type_enum_member.name.replace("_", " ").title(),
            callback_data=f"admin_select_ai_ref_type_{source_type_enum_member.value}"
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="⬅️ Отмена (в меню источников)", callback_data="admin_ai_references_menu_back"))
    return builder.as_markup()

def get_admin_ai_reference_list_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    pagination_buttons = []
    if current_page > 0:
        pagination_buttons.append(
            InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"admin_list_ai_references_page_{current_page - 1}")
        )
    if total_pages > 0:
        pagination_buttons.append(
            InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}", callback_data="admin_noop")
        )
    if current_page < total_pages - 1:
        pagination_buttons.append(
            InlineKeyboardButton(text="След. ➡️", callback_data=f"admin_list_ai_references_page_{current_page + 1}")
        )
    
    if pagination_buttons:
        builder.row(*pagination_buttons)

    builder.row(InlineKeyboardButton(text="⬅️ Назад (в меню источников)", callback_data="admin_ai_references_menu_back"))
    return builder.as_markup()

def get_admin_ai_reference_actions_keyboard(reference_id: int, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Редактировать", callback_data=f"admin_edit_ai_reference_prompt_{reference_id}")
    active_text = "Деактивировать" if is_active else "Активировать"
    builder.button(text=f"👁️ {active_text}", callback_data=f"admin_toggle_ai_reference_active_{reference_id}")
    builder.button(text="🗑️ Удалить", callback_data=f"admin_delete_ai_reference_confirm_{reference_id}")
    builder.row(InlineKeyboardButton(text="⬅️ К списку источников", callback_data="admin_list_ai_references_page_0"))
    return builder.as_markup()

def get_admin_manage_trial_keyboard(user_id: int, current_trial_end_date: Optional[datetime]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if current_trial_end_date and current_trial_end_date > datetime.now(current_trial_end_date.tzinfo):
        builder.button(text=f"⏳ Продлить триал на 7 дней", callback_data=f"admin_grant_trial_{user_id}_7")
        builder.button(text=f"⏳ Продлить триал на 30 дней", callback_data=f"admin_grant_trial_{user_id}_30")
        builder.button(text="❌ Отменить активный триал", callback_data=f"admin_cancel_trial_{user_id}")
    else:
        builder.button(text="🎁 Выдать триал на 7 дней", callback_data=f"admin_grant_trial_{user_id}_7")
        builder.button(text="🎁 Выдать триал на 30 дней", callback_data=f"admin_grant_trial_{user_id}_30")
    
    builder.button(text="⬅️ Назад (к действиям с пользователем)", callback_data=f"admin_view_user_{user_id}")
    builder.adjust(1)
    return builder.as_markup()

def get_admin_manage_subscription_keyboard(user_id: int, current_subscription_status: Optional[str], current_plan_name: Optional[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    available_plans = {
        "base_1m": {"name": "Базовый - 1 месяц", "duration_days": 30},
        "pro_1m": {"name": "Продвинутый - 1 месяц", "duration_days": 30},
        "pro_3m": {"name": "Продвинутый - 3 месяца", "duration_days": 90},
    }

    for plan_id, plan_details in available_plans.items():
        builder.button(text=f"💳 Активировать: {plan_details['name']}", callback_data=f"admin_activate_sub_{user_id}_{plan_id}")

    if current_subscription_status == "active":
        builder.button(text=f"🚫 Деактивировать текущую подписку ({current_plan_name or 'N/A'})", callback_data=f"admin_deactivate_sub_{user_id}")
    
    builder.button(text="⬅️ Назад (к действиям с пользователем)", callback_data=f"admin_view_user_{user_id}")
    builder.adjust(1)
    return builder.as_markup()

def get_main_inline_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Новый кейс", callback_data="main_menu:request_case")
    builder.button(text="📊 Мой прогресс", callback_data="main_menu:my_progress")
    builder.button(text="💬 Оставить отзыв", callback_data="main_menu:leave_feedback")
    builder.button(text="💳 Тарифы и подписка", callback_data="main_menu:tariffs")
    builder.button(text="ℹ️ Помощь", callback_data="main_menu:help")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def get_back_to_main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в главное меню", callback_data="main_menu:show")
    return builder.as_markup()

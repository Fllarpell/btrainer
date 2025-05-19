import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.db.models import UserRole, AdminAction, User, SubscriptionStatus
from app.ui.keyboards import (
    get_admin_panel_main_keyboard,
)
from app.states.admin_states import AdminStates

from .admin_user_management import admin_user_mgmt_router
from .admin_case_management import admin_case_mgmt_router
from .admin_ai_reference_management import admin_ai_ref_router
from .filters import AdminTelegramFilter
from app.db.crud.user_crud import get_total_db_request_count, count_converted_from_trial_users
from aiogram.utils.formatting import Text, Bold, Italic, Code

logger = logging.getLogger(__name__)
admin_router = Router(name="admin_handlers")

admin_router.include_router(admin_user_mgmt_router)
admin_router.include_router(admin_case_mgmt_router)
admin_router.include_router(admin_ai_ref_router)

@admin_router.message(Command("admin"), AdminTelegramFilter())
async def handle_admin_command(message: types.Message, state: FSMContext, session: AsyncSession):
    logger.info(f"Admin user {message.from_user.id} accessed /admin panel.")
    current_state = await state.get_state()
    if current_state is not None:
        logger.info(f"Admin {message.from_user.id} was in state {current_state}, clearing state before showing admin menu.")
        await state.clear()
    admin_menu_kb = get_admin_panel_main_keyboard()
    await message.answer(
        "Добро пожаловать в админ-панель!",
        reply_markup=admin_menu_kb
    )

@admin_router.message(Command("admin"))
async def handle_admin_command_access_denied(message: types.Message):
    logger.warning(f"User {message.from_user.id} (non-admin) attempted to access /admin.")

@admin_router.callback_query(F.data == "admin_main_menu_back", AdminTelegramFilter())
async def handle_admin_main_menu_back_callback(callback_query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()
    await callback_query.answer()
    logger.debug(f"Admin {callback_query.from_user.id} pressed 'admin_main_menu_back'.")
    admin_menu_kb = get_admin_panel_main_keyboard()
    await callback_query.message.edit_text(
        "Админ-панель. Выберите действие:",
        reply_markup=admin_menu_kb
    )

@admin_router.callback_query(F.data == "admin_total_db_requests", AdminTelegramFilter())
async def handle_admin_total_db_requests_callback(callback_query: types.CallbackQuery, session: AsyncSession):
    await callback_query.answer()
    logger.debug(f"Admin {callback_query.from_user.id} requested total DB requests.")
    
    total_requests = await get_total_db_request_count(db=session)
    
    plain_descriptive_text = "Эта цифра представляет собой общее количество раз, когда пользовательские действия приводили к инициации сессии с базой данных."
    
    content = Text(
        Bold("📊 Статистика запросов к БД"), "\n\n",
        "Всего зарегистрировано запросов от пользователей: ", Code(str(total_requests)), "\n\n",
        Italic(plain_descriptive_text), "\n\n",
        "Для возврата в главное меню нажмите соответствующую кнопку."
    )
    
    await callback_query.message.edit_text(
        text=content.as_markdown(),
        parse_mode="MarkdownV2",
        reply_markup=get_admin_panel_main_keyboard()
    )

@admin_router.callback_query(F.data == "admin_trial_conversion_stats", AdminTelegramFilter())
async def handle_admin_trial_conversion_stats_callback(callback_query: types.CallbackQuery, session: AsyncSession):
    await callback_query.answer()
    logger.debug(f"Admin {callback_query.from_user.id} requested trial conversion stats.")
    
    converted_users_count = await count_converted_from_trial_users(db=session)
    total_users_with_trial_ended_or_active = await session.scalar(
        select(func.count(User.id)).filter(
            (User.trial_end_date != None) | (User.subscription_status == SubscriptionStatus.ACTIVE)
        )
    )
    
    percentage = 0.0
    if total_users_with_trial_ended_or_active > 0:
        percentage = (converted_users_count / total_users_with_trial_ended_or_active) * 100
        percentage_str = f"{percentage:.2f}%"
    else:
        percentage_str = "N/A (нет пользователей с триалом/активной подпиской)"

    plain_descriptive_text_conversion = "Эта цифра показывает тех, кто был в статусе TRIAL и затем перешел в ACTIVE."

    content = Text(
        Bold("📊 Конверсия из триала в подписку"), "\n\n",
        "Количество пользователей, перешедших с триала на платную подписку: ", Code(str(converted_users_count)), "\n",
        "Приблизительный процент конверсии: ", Code(percentage_str), 
        " (от пользователей, у которых был триал или сейчас активна подписка)\n\n",
        Italic(plain_descriptive_text_conversion), "\n",
        "Для возврата в главное меню нажмите соответствующую кнопку."
    )

    await callback_query.message.edit_text(
        text=content.as_markdown(),
        parse_mode="MarkdownV2",
        reply_markup=get_admin_panel_main_keyboard()
    )

@admin_router.message(Command("cancel_admin_action"), AdminTelegramFilter())
async def handle_cancel_admin_action(message: types.Message, state: FSMContext, session: AsyncSession):
    current_admin_state = await state.get_state()
    if current_admin_state is None:
        await message.answer("Нет активных админских действий для отмены.", reply_markup=get_admin_panel_main_keyboard())
        logger.debug(f"Admin {message.from_user.id} tried /cancel_admin_action but no state was active.")
        return
    logger.info(f"Admin {message.from_user.id} cancelled state {current_admin_state} using /cancel_admin_action.")
    await state.clear()
    await message.answer("Действие отменено. Возврат в главное админ меню.", reply_markup=get_admin_panel_main_keyboard())

@admin_router.callback_query(F.data == "admin_noop", AdminTelegramFilter())
async def handle_admin_noop_callback(callback_query: types.CallbackQuery, session: AsyncSession):
    await callback_query.answer()

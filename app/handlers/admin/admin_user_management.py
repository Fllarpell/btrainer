import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import math

from app.db.crud import user_crud
from app.db.crud import admin_log_crud
from app.db.models import UserRole, SubscriptionStatus, AdminAction
from app.ui.keyboards import (
    get_admin_users_menu_keyboard, 
    get_admin_user_list_keyboard, 
    get_admin_user_actions_keyboard,
    get_admin_panel_main_keyboard,
    get_admin_manage_trial_keyboard,
    get_admin_manage_subscription_keyboard
)
from app.states.admin_states import AdminStates

from .filters import AdminTelegramFilter

from app.utils.formatters import format_datetime_md, escape_md

from app.db.crud.user_crud import (
    get_user, count_users, get_users, get_user_by_telegram_id, 
    block_user, unblock_user, set_user_role,
    grant_trial_period, cancel_trial_period, activate_user_subscription, deactivate_user_subscription
)
from app.db.crud.admin_log_crud import create_admin_log

logger = logging.getLogger(__name__)
admin_user_mgmt_router = Router(name="admin_user_management")

USERS_PER_PAGE = 10

async def display_user_details(message_or_cq: types.Message | types.CallbackQuery, db_user_id: int, session: AsyncSession):
    logger.debug(f"display_user_details called for user_db_id: {db_user_id}")
    target_message = message_or_cq.message if isinstance(message_or_cq, types.CallbackQuery) else message_or_cq
    
    db_user = await get_user(db=session, user_id=db_user_id)
    if not db_user:
        logger.warning(f"display_user_details: User with db_id {db_user_id} not found.")
        await target_message.answer(f"⚠️ Пользователь с внутренним ID `{db_user_id}` не найден в базе данных\.")
        return

    user_display_name = escape_md(f"{db_user.first_name or ''} {db_user.last_name or ''}".strip() or f"User {db_user.id}")

    details_text = f"👤 **Информация о пользователе: {user_display_name}** \(ID: `{db_user.id}`\)\n\n"
    details_text += f"✉️ Telegram ID: `{db_user.telegram_id}`\n"
    details_text += f"🗣️ Username: `@{escape_md(db_user.username)}`\n" if db_user.username else f"🗣️ Username: `Не указан`\n"
    details_text += f"🌍 Язык: `{escape_md(db_user.language_code or 'Не указан')}`\n"
    details_text += escape_md("------------------------------------") + "\n"
    details_text += f"🔑 Роль: `{escape_md(db_user.role.value)}`\n"
    details_text += f"💳 Статус подписки: `{escape_md(db_user.subscription_status.value)}`\n"
    if db_user.current_plan_name:
        details_text += f"📄 Текущий план: `{escape_md(db_user.current_plan_name)}`\n"
    
    if db_user.subscription_status == SubscriptionStatus.TRIAL and db_user.trial_end_date:
        details_text += f"⏳ Триал активен до: `{format_datetime_md(db_user.trial_end_date)}`\n"
    elif db_user.subscription_status == SubscriptionStatus.ACTIVE and db_user.subscription_expires_at:
        details_text += f"⌛ Подписка активна до: `{format_datetime_md(db_user.subscription_expires_at)}`\n"
    
    details_text += escape_md("------------------------------------") + "\n"
    details_text += f"📅 Дата регистрации: `{format_datetime_md(db_user.created_at)}`\n"
    details_text += f"🕰️ Последняя активность: `{format_datetime_md(db_user.last_active_at) if db_user.last_active_at else 'Никогда'}`\n"
    details_text += f"🚫 Заблокирован: `{'Да' if db_user.is_blocked else 'Нет'}`\n"
    details_text += f"📊 Запросов к БД: `{db_user.db_request_count}`\n"

    user_actions_kb = get_admin_user_actions_keyboard(db_user)
    
    if isinstance(message_or_cq, types.CallbackQuery):
        await message_or_cq.message.edit_text(details_text, reply_markup=user_actions_kb, parse_mode="MarkdownV2")
    else: 
        await message_or_cq.answer(details_text, reply_markup=user_actions_kb, parse_mode="MarkdownV2")


@admin_user_mgmt_router.callback_query(F.data == "admin_users_menu", AdminTelegramFilter())
async def handle_admin_users_menu_callback(callback_query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback_query.answer()
    logger.debug(f"Admin {callback_query.from_user.id} pressed 'admin_users_menu'.")
    users_menu_kb = get_admin_users_menu_keyboard()
    await callback_query.message.edit_text(
        "Управление пользователями:",
        reply_markup=users_menu_kb
    )

@admin_user_mgmt_router.callback_query(F.data == "admin_users_menu_back", AdminTelegramFilter())
async def handle_admin_users_menu_back_callback(callback_query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    logger.debug(f"Admin {callback_query.from_user.id} pressed 'admin_users_menu_back'.")
    await handle_admin_users_menu_callback(callback_query, state, session)


@admin_user_mgmt_router.callback_query(F.data.startswith("admin_list_users_page_"), AdminTelegramFilter())
async def handle_admin_list_users_page_callback(callback_query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback_query.answer()
    page_str = callback_query.data.split("_")[-1]
    logger.debug(f"Admin {callback_query.from_user.id} requested user list page, callback_data: {callback_query.data}, extracted page_str: {page_str}")
    try:
        page = int(page_str)
    except ValueError:
        logger.warning(f"Invalid page number in callback data: {callback_query.data}, defaulting to page 0.")
        page = 0

    total_users = await count_users(db=session)
    logger.debug(f"Total users found: {total_users}")
    if total_users == 0:
        await callback_query.message.edit_text(
            "👥 В базе данных пока нет ни одного пользователя\.", 
            reply_markup=get_admin_users_menu_keyboard()
        )
        return

    total_pages = math.ceil(total_users / USERS_PER_PAGE)
    logger.debug(f"Calculated total_pages: {total_pages}, current_page: {page}")

    users = await get_users(db=session, skip=page * USERS_PER_PAGE, limit=USERS_PER_PAGE)
    logger.debug(f"Fetched {len(users) if users else 0} users for page {page}.")

    page_display_number = page + 1
    escaped_page_info = f"\(Страница {page_display_number}/{total_pages}\)"

    user_list_text = f"👥 **Список пользователей** {escaped_page_info}\nВсего в базе: {total_users}\n\n"
    if users:
        for user_obj in users:
            user_first_name = escape_md(user_obj.first_name or "")
            user_last_name = escape_md(user_obj.last_name or "")
            display_name_parts = [user_first_name, user_last_name]
            user_display_name = " ".join(filter(None, display_name_parts)).strip() or "N/A"
            username_tg = f"@{escape_md(user_obj.username)}" if user_obj.username else "N/A"

            user_list_text += (
                f"▫️ID: `{user_obj.id}` \| TG: `{user_obj.telegram_id}` \| {user_display_name} \({username_tg}\)\n"
            )
    else:
        user_list_text += "На этой странице нет пользователей\." 

    pagination_kb = get_admin_user_list_keyboard(current_page=page, total_pages=total_pages)
    
    try:
        await callback_query.message.edit_text(user_list_text, reply_markup=pagination_kb, parse_mode="MarkdownV2")
    except Exception as e: 
        logger.error(f"Error editing message for user list: {e}", exc_info=True)
        await callback_query.message.answer("Не удалось обновить список. Попробуйте еще раз.")


@admin_user_mgmt_router.callback_query(F.data == "admin_find_user_by_tg_id_prompt", AdminTelegramFilter())
async def handle_admin_find_user_by_tg_id_prompt_callback(callback_query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback_query.answer()
    logger.debug(f"Admin {callback_query.from_user.id} pressed 'admin_find_user_by_tg_id_prompt'. Setting state to AdminStates.awaiting_tg_id_for_search")
    await state.set_state(AdminStates.awaiting_tg_id_for_search)
    await callback_query.message.edit_text(
        "Введите Telegram ID пользователя, которого хотите найти.\n"
        "Вы можете получить его, например, от пользователя или из логов.\n"
        "\nДля отмены введите /cancel_admin_action",
        reply_markup=None 
    )

@admin_user_mgmt_router.message(AdminStates.awaiting_tg_id_for_search, AdminTelegramFilter())
async def handle_admin_receive_tg_id_for_search(message: types.Message, state: FSMContext, session: AsyncSession):
    user_input_tg_id = message.text
    logger.debug(f"Admin {message.from_user.id} submitted '{user_input_tg_id}' in AdminStates.awaiting_tg_id_for_search.")
    if not user_input_tg_id or not user_input_tg_id.isdigit():
        await message.reply("Неверный формат Telegram ID. Пожалуйста, введите только цифры. Или /cancel_admin_action для отмены.")
        logger.debug(f"Invalid TG ID format received: {user_input_tg_id}")
        return

    telegram_id_to_find = int(user_input_tg_id)
    db_user = await get_user_by_telegram_id(db=session, telegram_id=telegram_id_to_find)
    
    if db_user:
        logger.info(f"Admin {message.from_user.id} found user {db_user.id} (TG: {telegram_id_to_find}) by TG ID.")
        await state.clear() 
        await display_user_details(message, db_user.id, session)
    else:
        logger.info(f"Admin {message.from_user.id} did not find user with TG ID {telegram_id_to_find}.")
        await message.reply(
            f"Пользователь с Telegram ID `{telegram_id_to_find}` не найден.\n"
            "Попробуйте другой ID или /cancel_admin_action для возврата в меню.",
            parse_mode="MarkdownV2"
        )

@admin_user_mgmt_router.callback_query(F.data.startswith("admin_block_user_"), AdminTelegramFilter())
async def handle_admin_block_user_callback(callback_query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback_query.answer("Блокирую пользователя...")
    user_db_id_str = callback_query.data.split("_")[-1]
    logger.debug(f"Admin {callback_query.from_user.id} initiated 'admin_block_user'. Callback data: {callback_query.data}, extracted user_db_id_str: {user_db_id_str}")
    try:
        user_db_id = int(user_db_id_str)
    except (ValueError, IndexError):
        logger.error(f"Invalid user_db_id in callback data: {callback_query.data}")
        await callback_query.message.answer("Ошибка: Неверный ID пользователя для блокировки.")
        return

    db_user = await get_user(db=session, user_id=user_db_id)
    if not db_user:
        await callback_query.message.answer(f"Ошибка: Пользователь с ID {user_db_id} не найден.")
        return

    admin_performing_action = await get_user_by_telegram_id(db=session, telegram_id=callback_query.from_user.id)
    if not admin_performing_action:
        logger.error(f"Admin user with TG ID {callback_query.from_user.id} not found in DB. Cannot log action.")
    
    updated_user = await block_user(db=session, telegram_id=db_user.telegram_id)
    if updated_user and updated_user.is_blocked:
        logger.info(f"Admin {callback_query.from_user.id} blocked user {db_user.id} (TG: {db_user.telegram_id}).")
        if admin_performing_action: 
            await create_admin_log(
                db=session,
                admin_user_id=admin_performing_action.id,
                action=AdminAction.USER_BLOCK, 
                target_user_id=db_user.id,
                details=f"User TG ID: {db_user.telegram_id}"
            )
        else:
            logger.error(f"Skipped admin logging for block action on user {db_user.telegram_id} by TG ID {callback_query.from_user.id} because admin DB entry not found.")
        await display_user_details(callback_query, db_user.id, session)
    else:
        await callback_query.message.answer(f"Не удалось заблокировать пользователя ID {db_user.id}. Проверьте логи.")


@admin_user_mgmt_router.callback_query(F.data.startswith("admin_unblock_user_"), AdminTelegramFilter())
async def handle_admin_unblock_user_callback(callback_query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback_query.answer("Разблокирую пользователя...")
    user_db_id_str = callback_query.data.split("_")[-1]
    logger.debug(f"Admin {callback_query.from_user.id} initiated 'admin_unblock_user'. Callback data: {callback_query.data}, extracted user_db_id_str: {user_db_id_str}")
    try:
        user_db_id = int(user_db_id_str)
    except (ValueError, IndexError):
        logger.error(f"Invalid user_db_id in callback data: {callback_query.data}")
        await callback_query.message.answer("Ошибка: Неверный ID пользователя для разблокировки.")
        return

    db_user = await get_user(db=session, user_id=user_db_id)
    if not db_user:
        await callback_query.message.answer(f"Ошибка: Пользователь с ID {user_db_id} не найден.")
        return

    admin_performing_action = await get_user_by_telegram_id(db=session, telegram_id=callback_query.from_user.id)
    if not admin_performing_action:
        logger.error(f"Admin user with TG ID {callback_query.from_user.id} not found in DB. Cannot log unblock action.")

    updated_user = await unblock_user(db=session, telegram_id=db_user.telegram_id)
    if updated_user and not updated_user.is_blocked:
        logger.info(f"Admin {callback_query.from_user.id} unblocked user {db_user.id} (TG: {db_user.telegram_id}).")
        if admin_performing_action:
            await create_admin_log(
                db=session,
                admin_user_id=admin_performing_action.id,
                action=AdminAction.USER_UNBLOCK, 
                target_user_id=db_user.id,
                details=f"User TG ID: {db_user.telegram_id}"
            )
        else:
            logger.error(f"Skipped admin logging for unblock action on user {db_user.telegram_id} by TG ID {callback_query.from_user.id} because admin DB entry not found.")
        await display_user_details(callback_query, db_user.id, session)
    else:
        await callback_query.message.answer(f"Не удалось разблокировать пользователя ID {db_user.id}. Проверьте логи.")


@admin_user_mgmt_router.callback_query(F.data.startswith("admin_set_role_"), AdminTelegramFilter())
async def handle_admin_set_role_callback(callback_query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    parts = callback_query.data.split("_")
    logger.debug(f"Admin {callback_query.from_user.id} initiated 'admin_set_role'. Callback data: {callback_query.data}, parts: {parts}")
    try:
        user_db_id = parts[-1]
        role_str = parts[-2]
        new_role = UserRole[role_str.upper()]
        logger.debug(f"Parsed role_str: {role_str}, user_db_id: {user_db_id}, new_role enum: {new_role}")
    except (ValueError, IndexError, KeyError) as e:
        logger.error(f"Invalid role/user_db_id in callback data: {callback_query.data}. Error: {e}")
        await callback_query.answer("Ошибка: Неверные данные для смены роли.")
        return

    await callback_query.answer(f"Меняю роль на {new_role.value}...")

    target_user = await get_user(db=session, user_id=int(user_db_id))
    if not target_user:
        await callback_query.message.answer(f"Ошибка: Пользователь с ID {user_db_id} не найден.")
        return
    
    admin_performing_action = await get_user_by_telegram_id(db=session, telegram_id=callback_query.from_user.id)
    if not admin_performing_action:
        logger.error(f"Admin user with TG ID {callback_query.from_user.id} not found in DB. Cannot log role change.")

    updated_user = await set_user_role(db=session, telegram_id=target_user.telegram_id, role=new_role)
    if updated_user and updated_user.role == new_role:
        logger.info(f"Admin {callback_query.from_user.id} set role {new_role.value} for user {target_user.id} (TG: {target_user.telegram_id}).")
        if admin_performing_action:
            await create_admin_log(
                db=session,
                admin_user_id=admin_performing_action.id,
                action=AdminAction.ROLE_CHANGE,
                target_user_id=target_user.id,
                details=f"User TG ID: {target_user.telegram_id}, New Role: {new_role.value}"
            )
        else:
            logger.error(f"Skipped admin logging for role change on user {target_user.telegram_id} to {new_role.value} by TG ID {callback_query.from_user.id} because admin DB entry not found.")
        await display_user_details(callback_query, target_user.id, session)
    else:
        await callback_query.message.answer(f"Не удалось изменить роль для пользователя ID {target_user.id}. Проверьте логи.")

@admin_user_mgmt_router.callback_query(F.data.startswith("admin_view_user_"), AdminTelegramFilter())
async def handle_admin_view_user_callback(callback_query: types.CallbackQuery, session: AsyncSession):
    await callback_query.answer()
    user_db_id_str = callback_query.data.split("_")[-1]
    logger.debug(f"Admin {callback_query.from_user.id} initiated 'admin_view_user'. Callback data: {callback_query.data}, extracted user_db_id_str: {user_db_id_str}")
    try:
        user_db_id = int(user_db_id_str)
    except (ValueError, IndexError):
        logger.error(f"Invalid user_db_id in callback data for view user: {callback_query.data}")
        await callback_query.message.answer("Ошибка: Неверный ID пользователя для просмотра.")
        return
    await display_user_details(callback_query, user_db_id, session)

@admin_user_mgmt_router.callback_query(F.data.startswith("admin_manage_trial_"), AdminTelegramFilter())
async def handle_admin_manage_trial_callback(callback_query: types.CallbackQuery, session: AsyncSession):
    await callback_query.answer()
    user_db_id_str = callback_query.data.split("_")[-1]
    logger.debug(f"Admin {callback_query.from_user.id} initiated 'admin_manage_trial'. Callback data: {callback_query.data}, extracted user_db_id_str: {user_db_id_str}")
    try:
        user_db_id = int(user_db_id_str)
    except (ValueError, IndexError):
        logger.error(f"Invalid user_db_id in callback data for manage trial: {callback_query.data}")
        await callback_query.message.answer("Ошибка: Неверный ID пользователя для управления триалом.")
        return

    db_user = await get_user(db=session, user_id=user_db_id)
    if not db_user:
        await callback_query.message.answer(f"Ошибка: Пользователь с ID {user_db_id} не найден.")
        return

    trial_keyboard = get_admin_manage_trial_keyboard(user_id=db_user.id, current_trial_end_date=db_user.trial_end_date)
    await callback_query.message.edit_text(
        f"🛠️ Управление триалом для пользователя {db_user.telegram_id} (ID: {db_user.id})",
        reply_markup=trial_keyboard
    )

@admin_user_mgmt_router.callback_query(F.data.startswith("admin_manage_sub_"), AdminTelegramFilter())
async def handle_admin_manage_subscription_callback(callback_query: types.CallbackQuery, session: AsyncSession):
    await callback_query.answer()
    user_db_id_str = callback_query.data.split("_")[-1]
    logger.debug(f"Admin {callback_query.from_user.id} initiated 'admin_manage_sub'. Callback data: {callback_query.data}, extracted user_db_id_str: {user_db_id_str}")
    try:
        user_db_id = int(user_db_id_str)
    except (ValueError, IndexError):
        logger.error(f"Invalid user_db_id in callback data for manage subscription: {callback_query.data}")
        await callback_query.message.answer("Ошибка: Неверный ID пользователя для управления подпиской.")
        return

    db_user = await get_user(db=session, user_id=user_db_id)
    if not db_user:
        await callback_query.message.answer(f"Ошибка: Пользователь с ID {user_db_id} не найден.")
        return

    subscription_keyboard = get_admin_manage_subscription_keyboard(
        user_id=db_user.id, 
        current_subscription_status=db_user.subscription_status.value, # Pass enum value
        current_plan_name=db_user.current_plan_name
    )
    await callback_query.message.edit_text(
        f"💳 Управление подпиской для пользователя {db_user.telegram_id} (ID: {db_user.id})",
        reply_markup=subscription_keyboard
    )

@admin_user_mgmt_router.callback_query(F.data.startswith("admin_grant_trial_"), AdminTelegramFilter())
async def handle_admin_grant_trial_action(callback_query: types.CallbackQuery, session: AsyncSession):
    parts = callback_query.data.split("_")
    try:
        user_id = int(parts[-2])
        days = int(parts[-1])
    except (ValueError, IndexError):
        logger.error(f"Invalid callback data for grant_trial: {callback_query.data}")
        await callback_query.answer("Ошибка: Неверные данные для предоставления триала.", show_alert=True)
        return

    await callback_query.answer(f"Предоставляю триал на {days} дней...")
    updated_user = await grant_trial_period(db=session, user_id=user_id, trial_days=days)

    if updated_user:
        logger.info(f"Admin {callback_query.from_user.id} granted {days}-day trial to user {user_id}.")
        admin_actor = await get_user_by_telegram_id(db=session, telegram_id=callback_query.from_user.id)
        if admin_actor:
            await create_admin_log(
                db=session, admin_user_id=admin_actor.id, action=AdminAction.TRIAL_GRANTED,
                target_user_id=user_id, details=f"{days}-day trial granted."
            )
        await display_user_details(callback_query, user_id, session)
    else:
        await callback_query.message.answer("Не удалось предоставить триал. Проверьте логи.", reply_markup=get_admin_panel_main_keyboard())

@admin_user_mgmt_router.callback_query(F.data.startswith("admin_cancel_trial_"), AdminTelegramFilter())
async def handle_admin_cancel_trial_action(callback_query: types.CallbackQuery, session: AsyncSession):
    try:
        user_id = int(callback_query.data.split("_")[-1])
    except (ValueError, IndexError):
        logger.error(f"Invalid callback data for cancel_trial: {callback_query.data}")
        await callback_query.answer("Ошибка: Неверные данные для отмены триала.", show_alert=True)
        return

    await callback_query.answer("Отменяю триал...")
    updated_user = await cancel_trial_period(db=session, user_id=user_id)

    if updated_user:
        logger.info(f"Admin {callback_query.from_user.id} cancelled trial for user {user_id}.")
        admin_actor = await get_user_by_telegram_id(db=session, telegram_id=callback_query.from_user.id)
        if admin_actor:
            await create_admin_log(
                db=session, admin_user_id=admin_actor.id, action=AdminAction.TRIAL_CANCELLED,
                target_user_id=user_id, details="Trial cancelled."
            )
        await display_user_details(callback_query, user_id, session)
    else:
        await callback_query.message.answer("Не удалось отменить триал. Проверьте логи.", reply_markup=get_admin_panel_main_keyboard())

@admin_user_mgmt_router.callback_query(F.data.startswith("admin_activate_sub_"), AdminTelegramFilter())
async def handle_admin_activate_subscription_action(callback_query: types.CallbackQuery, session: AsyncSession):
    prefix = "admin_activate_sub_"
    data_part = callback_query.data[len(prefix):]
    
    try:
        user_id_str, plan_id_key = data_part.split("_", 1) # Split only once to separate user_id from potentially complex plan_id
        user_id = int(user_id_str)
    except (ValueError, IndexError):
        logger.error(f"Invalid callback data for activate_subscription: {callback_query.data}. Could not parse user_id and plan_id_key from '{data_part}'")
        await callback_query.answer("Ошибка: Неверные данные для активации подписки.", show_alert=True)
        return

    available_plans = {
        "base_1m": {"name": "Базовый - 1 месяц", "duration_days": 30},
        "pro_1m": {"name": "Продвинутый - 1 месяц", "duration_days": 30},
        "pro_3m": {"name": "Продвинутый - 3 месяца", "duration_days": 90},
    }
    
    plan_details = available_plans.get(plan_id_key)
    if not plan_details:
        logger.error(f"Unknown plan_id_key '{plan_id_key}' for activate_subscription.")
        await callback_query.answer("Ошибка: Неизвестный план подписки.", show_alert=True)
        return

    await callback_query.answer(f"Активирую подписку '{plan_details['name']}'...")
    updated_user = await activate_user_subscription(
        db=session, user_id=user_id, 
        plan_name=plan_details['name'], 
        duration_days=plan_details['duration_days']
    )

    if updated_user:
        logger.info(f"Admin {callback_query.from_user.id} activated subscription '{plan_details['name']}' for user {user_id}.")
        admin_actor = await get_user_by_telegram_id(db=session, telegram_id=callback_query.from_user.id)
        if admin_actor:
            await create_admin_log(
                db=session, admin_user_id=admin_actor.id, action=AdminAction.SUBSCRIPTION_ACTIVATED,
                target_user_id=user_id, details=f"Activated plan: {plan_details['name']}"
            )
        await display_user_details(callback_query, user_id, session)
    else:
        await callback_query.message.answer("Не удалось активировать подписку. Проверьте логи.", reply_markup=get_admin_panel_main_keyboard())

@admin_user_mgmt_router.callback_query(F.data.startswith("admin_deactivate_sub_"), AdminTelegramFilter())
async def handle_admin_deactivate_subscription_action(callback_query: types.CallbackQuery, session: AsyncSession):
    try:
        user_id = int(callback_query.data.split("_")[-1])
    except (ValueError, IndexError):
        logger.error(f"Invalid callback data for deactivate_subscription: {callback_query.data}")
        await callback_query.answer("Ошибка: Неверные данные для деактивации подписки.", show_alert=True)
        return

    await callback_query.answer("Деактивирую подписку...")
    updated_user = await deactivate_user_subscription(db=session, user_id=user_id)

    if updated_user:
        logger.info(f"Admin {callback_query.from_user.id} deactivated subscription for user {user_id}.")
        admin_actor = await get_user_by_telegram_id(db=session, telegram_id=callback_query.from_user.id)
        if admin_actor:
            await create_admin_log(
                db=session, admin_user_id=admin_actor.id, action=AdminAction.SUBSCRIPTION_DEACTIVATED,
                target_user_id=user_id, details=f"Subscription deactivated. Was: {updated_user.current_plan_name or 'N/A'}"
            )
        await display_user_details(callback_query, user_id, session)
    else:
        await callback_query.message.answer("Не удалось деактивировать подписку. Проверьте логи.", reply_markup=get_admin_panel_main_keyboard())

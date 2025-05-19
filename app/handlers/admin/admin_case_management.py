import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession 
import math

from app.db.crud.case_crud import count_all_cases, get_cases
from app.ui.keyboards import (
    get_admin_cases_menu_keyboard, 
    get_admin_case_list_keyboard
)

from .filters import AdminTelegramFilter
from app.utils.formatters import format_date_md

logger = logging.getLogger(__name__)
admin_case_mgmt_router = Router(name="admin_case_management")

CASES_PER_PAGE = 10

@admin_case_mgmt_router.callback_query(F.data == "admin_cases_menu", AdminTelegramFilter())
async def handle_admin_cases_menu_callback(callback_query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback_query.answer()
    logger.debug(f"Admin {callback_query.from_user.id} pressed 'admin_cases_menu'.")
    cases_menu_kb = get_admin_cases_menu_keyboard()
    await callback_query.message.edit_text(
        "Управление кейсами:",
        reply_markup=cases_menu_kb
    )

@admin_case_mgmt_router.callback_query(F.data.startswith("admin_list_cases_page_"), AdminTelegramFilter())
async def handle_admin_list_cases_page_callback(callback_query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback_query.answer()
    page_str = callback_query.data.split("_")[-1]
    logger.debug(f"Admin {callback_query.from_user.id} requested case list page, callback_data: {callback_query.data}, extracted page_str: {page_str}")
    try:
        page = int(page_str)
    except ValueError:
        logger.warning(f"Invalid page number in callback data for case list: {callback_query.data}, defaulting to page 0.")
        page = 0

    total_cases = await count_all_cases(db=session)
    logger.debug(f"Total cases found: {total_cases}")

    if total_cases == 0:
        await callback_query.message.edit_text(
            "Кейсов в базе данных пока нет.", 
            reply_markup=get_admin_cases_menu_keyboard() 
        )
        return

    total_pages = math.ceil(total_cases / CASES_PER_PAGE)
    logger.debug(f"Calculated total_pages for cases: {total_pages}, current_page: {page}")
    
    cases = await get_cases(db=session, skip=page * CASES_PER_PAGE, limit=CASES_PER_PAGE)
    logger.debug(f"Fetched {len(cases) if cases else 0} cases for page {page}.")

    case_list_text = f"*Список кейсов \\(Страница {page + 1}/{total_pages}\\):*\nTotal: {total_cases}\n\n"
    if cases:
        for case_obj in cases:
            title_preview = (case_obj.title[:50] + '…') if case_obj.title and len(case_obj.title) > 50 else case_obj.title
            replacements = {
                "_": "\\_", "*": "\\*", "[": "\\[", "]": "\\]", "(": "\\(", ")": "\\)", 
                "~": "\\~", "`": "\\`", ">": "\\>", "#": "\\#", "+": "\\+", "-": "\\-", 
                "=": "\\=", "|": "\\|", "{": "\\{", "}": "\\}", ".": "\\.", "!": "\\!"
            }
            for char, escaped_char in replacements.items():
                if title_preview:
                    title_preview = title_preview.replace(char, escaped_char)
            
            date_generated = format_date_md(case_obj.generated_at)
            case_list_text += (
                f"ID: `{case_obj.id}` \\| {date_generated} \\| {title_preview if title_preview else 'N/A'}\n"
            )
    else:
        case_list_text += "На этой странице кейсов нет."

    pagination_kb = get_admin_case_list_keyboard(current_page=page, total_pages=total_pages)
    
    try:
        await callback_query.message.edit_text(case_list_text, reply_markup=pagination_kb, parse_mode="MarkdownV2")
    except Exception as e:
        logger.error(f"Error editing message for case list: {e}", exc_info=True)
        await callback_query.message.answer("Не удалось обновить список кейсов. Попробуйте еще раз.") 

@admin_case_mgmt_router.callback_query(F.data == "admin_add_case_manual_prompt", AdminTelegramFilter())
async def handle_admin_add_case_manual_placeholder_callback(callback_query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback_query.answer("Функция 'Добавить кейс вручную' в разработке.", show_alert=True)
    logger.info(f"Admin {callback_query.from_user.id} tried to access 'admin_add_case_manual_prompt'. Placeholder activated.")

@admin_case_mgmt_router.callback_query(F.data == "admin_find_case_by_id_prompt", AdminTelegramFilter())
async def handle_admin_find_case_by_id_placeholder_callback(callback_query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback_query.answer("Функция 'Найти кейс (по ID)' в разработке.", show_alert=True)
    logger.info(f"Admin {callback_query.from_user.id} tried to access 'admin_find_case_by_id_prompt'. Placeholder activated.") 
    
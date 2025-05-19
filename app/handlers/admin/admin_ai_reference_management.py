import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import math

from app.db.crud.ai_reference_crud import (
    create_ai_reference,
    get_ai_reference,
    get_all_ai_references,
    count_ai_references,
    update_ai_reference,
    delete_ai_reference
)
from app.db.models import AIReference, AISourceType
from app.ui.keyboards import (
    get_admin_ai_references_menu_keyboard,
    get_admin_ai_reference_list_keyboard,
    get_admin_ai_reference_actions_keyboard,
    get_admin_panel_main_keyboard,
    get_admin_ai_source_type_select_keyboard,
    InlineKeyboardBuilder
)
from app.states.admin_states import AdminStates
from .filters import AdminTelegramFilter
from app.utils.formatters import escape_md
from aiogram.utils.formatting import Text, Bold, Italic, Code

logger = logging.getLogger(__name__)
admin_ai_ref_router = Router(name="admin_ai_reference_management")

REFS_PER_PAGE = 10

async def display_ai_reference_details(message_or_cq: types.Message | types.CallbackQuery, reference_id: int, session: AsyncSession, state: FSMContext):
    target_message = message_or_cq.message if isinstance(message_or_cq, types.CallbackQuery) else message_or_cq
    
    ref = await get_ai_reference(db=session, reference_id=reference_id)
    if not ref:
        await target_message.answer(f"⚠️ Источник ИИ с ID `{reference_id}` не найден\.")

        if isinstance(message_or_cq, types.CallbackQuery):
            await handle_ai_references_menu_callback(message_or_cq, session) 
        else:
            await target_message.answer("Меню источников ИИ:", reply_markup=get_admin_ai_references_menu_keyboard())
        return

    text = f"📚 **Источник ИИ: ID `{ref.id}`**\n\n"
    text += f"Тип: `{escape_md(ref.source_type.name.replace('_', ' ').title())}`\n"
    text += f"Описание: {escape_md(ref.description)}\n"
    if ref.url:
        text += f"URL: {escape_md(ref.url)}\n"
    if ref.citation_details:
        text += f"Детали цитирования: {escape_md(ref.citation_details)}\n"
    text += f"Активен: `{'Да' if ref.is_active else 'Нет'}`\n"
    text += f"Создан: `{escape_md(ref.created_at.strftime('%Y-%m-%d %H:%M'))}`\n"
    text += f"Обновлен: `{escape_md(ref.updated_at.strftime('%Y-%m-%d %H:%M'))}`\n"

    keyboard = get_admin_ai_reference_actions_keyboard(reference_id=ref.id, is_active=ref.is_active)
    
    if isinstance(message_or_cq, types.CallbackQuery):
        if message_or_cq.message:
            await message_or_cq.message.edit_text(text, reply_markup=keyboard, parse_mode="MarkdownV2")
        else:
             await message_or_cq.answer("Действие выполнено, но не могу отредактировать исходное сообщение.")
    else:
        await message_or_cq.answer(text, reply_markup=keyboard, parse_mode="MarkdownV2")

@admin_ai_ref_router.callback_query(F.data == "admin_ai_references_menu", AdminTelegramFilter())
async def handle_ai_references_menu_callback(callback_query: types.CallbackQuery, session: AsyncSession):
    await callback_query.answer()
    keyboard = get_admin_ai_references_menu_keyboard()
    if callback_query.message:
        await callback_query.message.edit_text("Управление источниками ИИ:", reply_markup=keyboard)
    else:
        await callback_query.bot.send_message(callback_query.from_user.id, "Управление источниками ИИ:", reply_markup=keyboard)


@admin_ai_ref_router.callback_query(F.data == "admin_ai_references_menu_back", AdminTelegramFilter())
async def handle_ai_references_menu_back_callback(callback_query: types.CallbackQuery, session: AsyncSession):
    await handle_ai_references_menu_callback(callback_query, session)

@admin_ai_ref_router.callback_query(F.data.startswith("admin_list_ai_references_page_"), AdminTelegramFilter())
async def handle_list_ai_references_page_callback(callback_query: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback_query.answer()
    page = int(callback_query.data.split("_")[-1])
    
    total_refs = await count_ai_references(db=session)
    if total_refs == 0:
        if callback_query.message:
            no_refs_text = Text("В базе данных пока нет источников ИИ.")
            await callback_query.message.edit_text(
                no_refs_text.as_markdown(), 
                reply_markup=get_admin_ai_references_menu_keyboard(),
                parse_mode="MarkdownV2"
            )
        return

    total_pages = math.ceil(total_refs / REFS_PER_PAGE)
    refs = await get_all_ai_references(db=session, skip=page * REFS_PER_PAGE, limit=REFS_PER_PAGE)
    
    content_elements = [
        Bold(f"📚 Список источников ИИ (Страница {page + 1}/{total_pages})"),
        Text("\n"),
        Text(f"Всего: {total_refs}\n\n")
    ]

    if refs:
        for ref in refs:
            active_status = "✅" if ref.is_active else "❌"
            
            description_text = ref.description if ref.description else ""
            desc_snippet = description_text[:40]
            if len(description_text) > 40:
                desc_snippet += "..."

            line_items = [
                Text(active_status),
                Text(" ID: "), Code(str(ref.id)),
                Text(" | "), Text(ref.source_type.name.replace('_', ' ').title()),
                Text(" | "), Text(desc_snippet),
                Text(" ["), # Text will escape '['
                Code(f"/view_ai_ref_{ref.id}"),
                Text("]\n") # Text will escape ']'
            ]
            content_elements.extend(line_items)
    else:
        content_elements.append(Text("На этой странице нет источников."))
        
    final_text_object = Text(*content_elements)
    text_to_send = final_text_object.as_markdown()
        
    keyboard = get_admin_ai_reference_list_keyboard(current_page=page, total_pages=total_pages)
    if callback_query.message:
        await callback_query.message.edit_text(text_to_send, reply_markup=keyboard, parse_mode="MarkdownV2")

@admin_ai_ref_router.callback_query(F.data.startswith("view_ai_ref_"), AdminTelegramFilter()) 
async def handle_view_ai_reference_from_list_callback(callback_query: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    try:
        ref_id_str = callback_query.data.split("_")[-1]
        ref_id = int(ref_id_str)
    except (IndexError, ValueError):
        logger.warning(f"Could not parse ref_id from callback_data: {callback_query.data}")
        await callback_query.answer("Ошибка: Неверный ID источника.", show_alert=True)
        return
    await callback_query.answer()
    await display_ai_reference_details(callback_query, ref_id, session, state)

@admin_ai_ref_router.callback_query(F.data == "admin_add_ai_reference_prompt", AdminTelegramFilter())
async def handle_add_ai_reference_prompt_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await state.clear()
    await state.set_state(AdminStates.awaiting_ai_ref_type)
    keyboard = get_admin_ai_source_type_select_keyboard()
    if callback_query.message:
        await callback_query.message.edit_text("Выберите тип нового источника ИИ:", reply_markup=keyboard)

@admin_ai_ref_router.callback_query(F.data.startswith("admin_select_ai_ref_type_"), AdminTelegramFilter())
async def handle_select_ai_ref_type_callback(callback_query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    source_type_str = callback_query.data.split("_")[-1]
    try:
        source_type_enum = AISourceType(source_type_str) 
    except ValueError:
        await callback_query.answer("Ошибка: Неверный тип источника.", show_alert=True)
        logger.warning(f"Invalid source type string from callback: {source_type_str}")
        return

    await state.update_data(source_type=source_type_enum)
    await state.set_state(AdminStates.awaiting_ai_ref_description)
    await callback_query.answer()
    if callback_query.message:
        await callback_query.message.edit_text(
            f"Тип выбран: {source_type_enum.name.replace('_', ' ').title()}\.\n\nВведите **описание** источника \(например, название книги, статьи, краткое описание URL\):"
            f"\n\nДля отмены введите /cancel_admin_action",
            parse_mode="MarkdownV2"
        )

@admin_ai_ref_router.message(AdminStates.awaiting_ai_ref_description, AdminTelegramFilter())
async def handle_ai_ref_description_message(message: types.Message, state: FSMContext, session: AsyncSession):
    description = message.text
    if not description or len(description.strip()) < 3:
        await message.reply("Описание слишком короткое. Пожалуйста, введите подробное описание (мин. 3 символа) или /cancel_admin_action для отмены.")
        return
    
    await state.update_data(description=description.strip())
    fsm_data = await state.get_data()
    source_type: AISourceType = fsm_data.get('source_type')

    content_elements = []
    if source_type == AISourceType.URL:
        await state.set_state(AdminStates.awaiting_ai_ref_url)
        content_elements.extend([
            Text("Теперь введите полный ", Bold("URL"), " (начиная с http:// или https://):")
        ])
        if fsm_data.get('editing_ref_id') and fsm_data.get('original_url'):
            content_elements.extend([
                Text("\n(Текущий URL: ", Italic(escape_md(fsm_data.get('original_url'))), ")")
            ])
        content_elements.append(Text("\n\nДля отмены /cancel_admin_action"))
    else: 
        await state.set_state(AdminStates.awaiting_ai_ref_citation)
        content_elements.extend([
            Text("Теперь введите ", Bold("детали цитирования"), " (авторы, год, страницы и т.д.). Если нет, введите 'нет':")
        ])
        if fsm_data.get('editing_ref_id') and fsm_data.get('original_citation'):
            content_elements.extend([
                Text("\n(Текущее цитирование: ", Italic(escape_md(fsm_data.get('original_citation'))), ")")
            ])
        content_elements.append(Text("\n\nДля отмены /cancel_admin_action"))
    
    prompt_message_text = Text(*content_elements)
    await message.reply(prompt_message_text.as_markdown(), parse_mode="MarkdownV2")

@admin_ai_ref_router.message(AdminStates.awaiting_ai_ref_url, AdminTelegramFilter())
async def handle_ai_ref_url_message(message: types.Message, state: FSMContext, session: AsyncSession):
    url = message.text.strip()
    if not url.startswith(("http://", "https://")):
        await message.reply("URL должен начинаться с http:// или https://. Пожалуйста, введите корректный URL или /cancel\_admin\_action для отмены.")
        return

    await state.update_data(url=url)
    await state.set_state(AdminStates.awaiting_ai_ref_citation)
    fsm_data = await state.get_data()
    
    content_elements = [Text("URL принят. Теперь введите ", Bold("детали цитирования"), " (если есть). Если нет, введите 'нет':")]
    if fsm_data.get('editing_ref_id') and fsm_data.get('original_citation'):
        content_elements.extend([
            Text("\n(Текущее цитирование: ", Italic(escape_md(fsm_data.get('original_citation'))), ")")
        ])
    content_elements.append(Text("\n\nДля отмены /cancel_admin_action"))
    
    prompt_message_text = Text(*content_elements)
    await message.reply(prompt_message_text.as_markdown(), parse_mode="MarkdownV2")

@admin_ai_ref_router.message(AdminStates.awaiting_ai_ref_citation, AdminTelegramFilter())
async def handle_ai_ref_citation_message(message: types.Message, state: FSMContext, session: AsyncSession):
    citation = message.text.strip()
    if citation.lower() == 'нет':
        citation = None
    
    await state.update_data(citation_details=citation)
    fsm_data = await state.get_data()
    
    source_payload = {
        "source_type": fsm_data.get("source_type"),
        "description": fsm_data.get("description"),
        "url": fsm_data.get("url"), 
        "citation_details": fsm_data.get("citation_details")
    }
    if source_payload["source_type"] != AISourceType.URL:
        source_payload["url"] = None 

    editing_ref_id = fsm_data.get('editing_ref_id')
    saved_ref = None
    try:
        if editing_ref_id:
            logger.info(f"Attempting to update AI Reference ID: {editing_ref_id} with data: {source_payload}")
            saved_ref = await update_ai_reference(db=session, reference_id=editing_ref_id, update_data=source_payload)
            await message.answer(f"Источник ИИ ID `{editing_ref_id}` успешно обновлен!")
        else:
            logger.info(f"Attempting to create AI Reference with data: {source_payload}")
            saved_ref = await create_ai_reference(db=session, source_data=source_payload)
            await message.answer("Новый источник ИИ успешно создан!")
    except Exception as e:
        logger.error(f"Error creating/updating AI reference: {e}", exc_info=True)
        await message.answer(f"Произошла ошибка при сохранении: {escape_md(str(e))}. Попробуйте снова.")
        await state.clear()
        mock_cq = types.CallbackQuery(id="mock_cq_save_error", from_user=message.from_user, chat_instance=message.chat.id, message=message, data="admin_ai_references_menu") 
        await handle_ai_references_menu_callback(mock_cq, session)
        return

    await state.clear()
    if saved_ref:
        await display_ai_reference_details(message, saved_ref.id, session, state)
    else: 
        mock_cq = types.CallbackQuery(id="mock_cq_save_fallback", from_user=message.from_user, chat_instance=message.chat.id, message=message, data="admin_ai_references_menu") 
        await handle_ai_references_menu_callback(mock_cq, session)
        
@admin_ai_ref_router.callback_query(F.data.startswith("admin_toggle_ai_reference_active_"), AdminTelegramFilter())
async def handle_toggle_ai_ref_active_callback(callback_query: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    ref_id = int(callback_query.data.split("_")[-1])
    ref = await get_ai_reference(db=session, reference_id=ref_id)
    if not ref:
        await callback_query.answer("Источник не найден!", show_alert=True)
        return
    
    updated_ref = await update_ai_reference(db=session, reference_id=ref_id, update_data={"is_active": not ref.is_active})
    if updated_ref:
        await callback_query.answer(f"Статус изменен на {'Активен' if updated_ref.is_active else 'Неактивен'}")
        await display_ai_reference_details(callback_query, ref_id, session, state)
    else:
        await callback_query.answer("Ошибка при обновлении статуса.", show_alert=True)

@admin_ai_ref_router.callback_query(F.data.startswith("admin_delete_ai_reference_confirm_"), AdminTelegramFilter())
async def handle_delete_ai_ref_confirm_callback(callback_query: types.CallbackQuery, session: AsyncSession):
    ref_id = int(callback_query.data.split("_")[-1])
    ref = await get_ai_reference(db=session, reference_id=ref_id)
    if not ref:
        await callback_query.answer("Источник не найден!", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"admin_delete_ai_reference_execute_{ref_id}")
    builder.button(text="❌ Нет, отмена", callback_data=f"view_ai_ref_{ref_id}") 
    await callback_query.answer()
    if callback_query.message:
        await callback_query.message.edit_text(
            f"Вы уверены, что хотите удалить источник ИИ ID `{ref_id}`: **{escape_md(ref.description)}**?",
            reply_markup=builder.as_markup(),
            parse_mode="MarkdownV2"
        )

@admin_ai_ref_router.callback_query(F.data.startswith("admin_delete_ai_reference_execute_"), AdminTelegramFilter())
async def handle_delete_ai_ref_execute_callback(callback_query: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    ref_id = int(callback_query.data.split("_")[-1])
    deleted = await delete_ai_reference(db=session, reference_id=ref_id)
    if deleted:
        await callback_query.answer("Источник ИИ удален.", show_alert=True)
        if callback_query.message:
            await callback_query.message.edit_text("Источник удален. Возврат к списку...")
        mock_cq_data_for_list = types.CallbackQuery(id=callback_query.id, from_user=callback_query.from_user, chat_instance=callback_query.chat_instance if callback_query.message else callback_query.from_user.id , message=callback_query.message, data="admin_list_ai_references_page_0")
        await handle_list_ai_references_page_callback(mock_cq_data_for_list, session, state)
    else:
        await callback_query.answer("Ошибка при удалении источника.", show_alert=True)
        await display_ai_reference_details(callback_query, ref_id, session, state) 

@admin_ai_ref_router.callback_query(F.data.startswith("admin_edit_ai_reference_prompt_"), AdminTelegramFilter())
async def handle_edit_ai_ref_prompt_callback(callback_query: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    ref_id = int(callback_query.data.split("_")[-1])
    ref = await get_ai_reference(db=session, reference_id=ref_id)
    if not ref:
        await callback_query.answer("Источник не найден!", show_alert=True)
        return

    await state.clear()
    await state.update_data(
        editing_ref_id=ref.id, 
        source_type=ref.source_type, 
        original_description=ref.description, 
        original_url=ref.url,
        original_citation=ref.citation_details
    )
    
    await state.set_state(AdminStates.awaiting_ai_ref_description)
    await callback_query.answer()
    if callback_query.message:
        text_content = Text(
            "✏️ ", Bold(f"Редактирование источника ID {ref.id}"),
            " (Тип: ", Italic(ref.source_type.name.replace('_', ' ').title()), ")\n",
            "Введите ", Bold("новое описание"), " (старое: ", Italic(ref.description), "):\n\n",
            "Для отмены введите ", Code("/cancel_admin_action")
        )
        await callback_query.message.edit_text(
            text_content.as_markdown(),
            parse_mode="MarkdownV2"
        )

logger.info("AI Reference Management admin router configured with handlers.") 

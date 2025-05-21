import logging
import json
from aiogram import Router, types, F
from aiogram.utils.markdown import hbold
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.fsm.context import FSMContext
import datetime

try:
    from aiogram.utils.text_splitter import TextSplitter
    TEXT_SPLITTER_AVAILABLE = True
except ImportError:
    TEXT_SPLITTER_AVAILABLE = False
    pass

from app.db.crud.user_crud import get_user_by_telegram_id
from app.db.crud.case_crud import create_case, get_case
from app.db.crud.solution_crud import create_solution
from app.db.crud.ai_reference_crud import get_active_ai_references_for_prompt
from app.db.models import Solution
from app.ui.keyboards import get_after_case_keyboard, get_after_solution_analysis_keyboard
from app.services.ai_service import generate_case_from_ai, analyze_solution_with_ai
from app.states.solve_case import SolveCaseStates

logger = logging.getLogger(__name__)
case_lifecycle_router = Router(name="case_lifecycle_handlers")

MAX_MESSAGE_LENGTH = 4096

def manual_text_splitter(text: str, max_chunk_size: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Manually splits text into chunks of a maximum size, respecting Telegram limits."""
    if not TEXT_SPLITTER_AVAILABLE:
        logger.warning(
            "aiogram.utils.text_splitter.TextSplitter not found. Using manual fallback for splitting long messages. "
            "Consider updating aiogram to v3.0.0b8+ for the native utility."
        )
    chunks = []
    current_chunk = ""
    for char in text:
        if len(current_chunk.encode('utf-8')) + len(char.encode('utf-8')) > max_chunk_size:
            chunks.append(current_chunk)
            current_chunk = char
        else:
            current_chunk += char
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


async def _generate_and_send_case(
    message_or_callback_query: types.Message | types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    is_another_case: bool = False
):

    user = message_or_callback_query.from_user
    if isinstance(message_or_callback_query, types.CallbackQuery):
        await message_or_callback_query.answer()
        await message_or_callback_query.message.answer("⏳ Генерирую новый кейс для вас, подождите немного...")
    else:
        await message_or_callback_query.answer("⏳ Генерирую кейс для вас, это может занять некоторое время...")

    active_references = await get_active_ai_references_for_prompt(db=session)
    if not active_references:
        logger.warning(f"No active AI references found in DB for user {user.id} during case generation.")

    case_data = await generate_case_from_ai(active_references=active_references)

    if not case_data or not case_data.get("title") or not case_data.get("description"):
        error_message = "К сожалению, не удалось сгенерировать кейс в данный момент. Попробуйте, пожалуйста, позже."
        logger.error(f"Failed to generate case from AI for user {user.id}. Case data: {case_data}. References used: {len(active_references) if active_references else 0}")
        if isinstance(message_or_callback_query, types.CallbackQuery):
            await message_or_callback_query.message.answer(error_message)
        else:
            await message_or_callback_query.answer(error_message)
        return

    case_title = case_data["title"]
    case_description = case_data["description"]
    ai_model_name = "gpt-4o-mini"
    prompt_version_placeholder = "generic_case_prompt_v1_json_output_with_refs" 

    try:
        new_case = await create_case(
            db=session,
            title=case_title,
            case_text=case_description,
            ai_model_used=ai_model_name,
            prompt_version=prompt_version_placeholder,
        )
        await session.flush()
        logger.info(f"Case {new_case.id} (AI-generated, another_case={is_another_case}) created for user {user.id}. Refs count: {len(active_references) if active_references else 0}")

        response_text = f"{hbold(new_case.title)}\n\n{new_case.case_text}"
        
        target_message_callable = message_or_callback_query.message.answer if isinstance(message_or_callback_query, types.CallbackQuery) else message_or_callback_query.answer
        
        await target_message_callable(
            response_text,
            reply_markup=get_after_case_keyboard()
        )
        
        await state.set_state(SolveCaseStates.awaiting_solution)
        await state.update_data(current_case_id=new_case.id, case_title=new_case.title)
        logger.info(f"User {user.id} set to state SolveCaseStates.awaiting_solution for case_id {new_case.id} (another_case={is_another_case})")

    except Exception as e:
        logger.error(f"Error processing AI-generated case (another_case={is_another_case}) for user {user.id}: {e}", exc_info=True)
        error_msg = "Произошла ошибка при сохранении или отправке сгенерированного кейса. Пожалуйста, попробуйте еще раз позже."
        target_error_callable = message_or_callback_query.message.answer if isinstance(message_or_callback_query, types.CallbackQuery) else message_or_callback_query.answer
        await target_error_callable(error_msg)


@case_lifecycle_router.message(F.text == "📝 Новый кейс")
async def handle_new_case_button(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик для кнопки '📝 Новый кейс' из главного меню.
    """
    logger.info(f"User {message.from_user.id} requested a new case via '📝 Новый кейс' button.")
    await _generate_and_send_case(message, state, session, is_another_case=False)


@case_lifecycle_router.message(F.text == "💼 Получить кейс")
async def handle_request_case_button(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик для кнопки '💼 Получить кейс'.
    """
    logger.info(f"User {message.from_user.id} requested a new case via button.")
    await _generate_and_send_case(message, state, session, is_another_case=False)

@case_lifecycle_router.callback_query(F.data == "request_another_case")
async def handle_request_another_case_callback(
    callback_query: types.CallbackQuery, 
    state: FSMContext,
    session: AsyncSession
):
    """
    Обработчик для кнопки '🔀 Запросить другой кейс' (инлайн).
    """
    logger.info(f"User {callback_query.from_user.id} requested another case via inline button.")
    await _generate_and_send_case(callback_query, state, session, is_another_case=True)

@case_lifecycle_router.callback_query(F.data == "request_case_again")
async def handle_request_case_again_callback(
    callback_query: types.CallbackQuery, 
    state: FSMContext,
    session: AsyncSession
):
    """
    Обработчик для кнопки '💼 Получить новый кейс' (после анализа).
    """
    logger.info(f"User {callback_query.from_user.id} requested case again via button after analysis.")
    await _generate_and_send_case(callback_query, state, session, is_another_case=True)

@case_lifecycle_router.message(SolveCaseStates.awaiting_solution, F.text & ~F.text.startswith('/'))
async def handle_solution_submission(
    message: types.Message, 
    state: FSMContext,
    session: AsyncSession
): 
    user_telegram_id = message.from_user.id
    logger.info(f"User {user_telegram_id} submitted solution in state {await state.get_state()}.")

    db_user = await get_user_by_telegram_id(db=session, telegram_id=user_telegram_id)

    if not db_user:
        logger.error(f"User with telegram_id {user_telegram_id} not found in DB during solution submission. They might need to /start.")
        await message.answer("Не удалось найти вашу учетную запись. Пожалуйста, попробуйте выполнить команду /start и затем отправьте решение снова.")
        await state.clear()
        return

    state_data = await state.get_data()
    current_case_id = state_data.get("current_case_id")
    case_title = state_data.get("case_title", "ранее полученный кейс")

    if not current_case_id:
        logger.warning(f"User {user_telegram_id} submitted solution, but no current_case_id found in state. State data: {state_data}")
        await message.answer("Не удалось определить, к какому кейсу относится ваше решение. Пожалуйста, запросите кейс заново.")
        await state.clear()
        return

    original_case = await get_case(db=session, case_id=current_case_id)
    if not original_case:
        logger.error(f"User {user_telegram_id} submitted solution for case_id {current_case_id}, but case not found in DB.")
        await message.answer("Произошла ошибка: не удалось найти исходный кейс. Пожалуйста, попробуйте запросить кейс заново.")
        await state.clear()
        return
    
    solution_text = message.text
    await message.answer("⏳ Анализирую ваше решение... Это может занять некоторое время.")

    active_references = await get_active_ai_references_for_prompt(db=session)
    if not active_references:
        logger.warning(f"No active AI references found in DB for user {user_telegram_id} during solution analysis for case {current_case_id}.")

    try:
        analysis_report = await analyze_solution_with_ai(
            original_case.case_text, 
            solution_text,
            active_references=active_references
        )
        if not (
            analysis_report and not analysis_report.get("error") and
            isinstance(analysis_report.get("strengths"), list) and
            isinstance(analysis_report.get("areas_for_improvement"), list) and
            isinstance(analysis_report.get("overall_impression"), str) and
            isinstance(analysis_report.get("solution_rating"), str)
        ):
            error_detail = analysis_report.get("raw_response") if analysis_report and analysis_report.get("error") else str(analysis_report)
            logger.error(f"AI analysis failed or returned unexpected structure for user {user_telegram_id}, case {current_case_id}. Report: {error_detail}")
            await message.answer("К сожалению, не удалось получить анализ вашего решения от AI (неверный формат или структура ответа). Попробуйте позже.")
            return

        strengths_text = "\n".join([f"- {s}" for s in analysis_report['strengths']]) if analysis_report['strengths'] else "\(Не отмечено\)" 
        improvements_text = "\n".join([f"- {i}" for i in analysis_report['areas_for_improvement']]) if analysis_report['areas_for_improvement'] else "\(Не отмечено\)"
        formatted_analysis = (
            f"{hbold('Анализ вашего решения для кейса:')} \"{case_title}\"\n\n"
            f"{hbold('Сильные стороны:')}\n{strengths_text}\n\n"
            f"{hbold('Области для улучшения:')}\n{improvements_text}\n\n"
            f"{hbold('Общее впечатление:')}\n{analysis_report.get('overall_impression', 'N/A')}\n\n"
            f"{hbold('Оценка решения:')} {analysis_report.get('solution_rating', 'N/A')}"
        )
        raw_analysis_json_string = json.dumps(analysis_report, ensure_ascii=False)
        solution = await create_solution(
            db=session,
            case_id=current_case_id,
            user_id=db_user.id, 
            solution_text=solution_text,
            ai_analysis=raw_analysis_json_string 
        )
        await session.flush() 
        logger.info(f"Solution {solution.id} and AI analysis saved for user {db_user.id}, case {current_case_id}. Refs count: {len(active_references) if active_references else 0}")

        if TEXT_SPLITTER_AVAILABLE:
            splitter = TextSplitter(max_len=MAX_MESSAGE_LENGTH)
            analysis_chunks = splitter.split_text(formatted_analysis)
        else:
            analysis_chunks = manual_text_splitter(formatted_analysis, MAX_MESSAGE_LENGTH)
        
        for i, chunk in enumerate(analysis_chunks):
            reply_markup = get_after_solution_analysis_keyboard() if i == len(analysis_chunks) - 1 else None
            await message.answer(chunk, reply_markup=reply_markup)
        
        await state.clear()
        logger.info(f"State cleared for user {user_telegram_id} after solution analysis for case {current_case_id}.")

    except Exception as e:
        logger.error(f"Error during solution analysis or DB saving for user {user_telegram_id}, case {current_case_id}: {e}", exc_info=True)
        await message.answer(
            "Произошла серьезная ошибка во время анализа или сохранения вашего решения. Пожалуйста, сообщите администратору или попробуйте позже."
        )
        raise 
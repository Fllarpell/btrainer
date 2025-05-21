import logging
import json
from collections import Counter
from aiogram import Router, types, F, Bot
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.fsm.context import FSMContext

from app.ui.keyboards import get_main_menu_keyboard, get_subscribe_inline_keyboard, get_after_solution_analysis_keyboard, get_back_to_main_menu_keyboard

from app.db.crud.user_crud import get_user_by_telegram_id
from app.db.crud.solution_crud import (
    get_solutions_by_user, 
    count_solutions_by_user, 
    count_solutions_by_user_and_rating
)
from app.db import crud
from app.db.models import SubscriptionStatus, UserRole
from app.db.crud import transaction_crud
import uuid
from decimal import Decimal
from aiogram.types import LabeledPrice
from app.core.config import settings, is_admin
from app.states.feedback_states import FeedbackStates
from app.services import ai_service
from app.utils.formatters import format_datetime_md, escape_md

from app.handlers.payment_handlers import (
    MONTHLY_PLAN_TITLE,
    MONTHLY_PLAN_DESCRIPTION,
    MONTHLY_PLAN_PRICE_RUB,
    MONTHLY_PLAN_CURRENCY,
    MONTHLY_PLAN_ID,
    MONTHLY_PLAN_DURATION_DAYS
)

from app.handlers.user.user_onboarding_handlers import HELP_TEXT

from app.handlers.case.case_lifecycle_handlers import _generate_and_send_case
from app.states.solve_case import SolveCaseStates

logger = logging.getLogger(__name__)
feature_router = Router(name="feature_handlers") 


def get_user_rank(solved_count: int) -> str:
    """Determines a user's rank based on solved cases."""
    if solved_count == 0:
        return "🌱 Новичок"
    elif solved_count < 5:
        return "🧠 Практикант"
    elif solved_count < 15:
        return "💡 Стажер-терапевт"
    elif solved_count < 30:
        return "✨ Младший специалист"
    elif solved_count < 50:
        return "🏆 Опытный консультант"
    else:
        return "⭐ Мастер CBT"

async def _get_my_progress_content(user_telegram_id: int, session: AsyncSession) -> str:
    logger.debug(f"Fetching progress content for user {user_telegram_id}.")
    db_user = await get_user_by_telegram_id(db=session, telegram_id=user_telegram_id)

    if not db_user:
        logger.warning(f"User {user_telegram_id} requested progress but not found in DB.")
        return "Не удалось найти вашу учетную запись\\. Пожалуйста, попробуйте /start\\."

    quality_solved_count = await count_solutions_by_user_and_rating(
        db=session, 
        user_id=db_user.id, 
        target_rating="meets_expectations"
    )
    user_rank = get_user_rank(quality_solved_count)
    user_rank_escaped = escape_md(user_rank)

    solutions_for_display_limit = 3
    recent_solutions = await get_solutions_by_user(
        db=session, user_id=db_user.id, limit=solutions_for_display_limit 
    )

    ai_ratings = [sol.user_rating_of_analysis for sol in recent_solutions if sol.user_rating_of_analysis is not None]
    avg_ai_rating = sum(ai_ratings) / len(ai_ratings) if ai_ratings else None

    all_strengths = []
    all_areas_for_improvement = []
    parse_errors = 0
    for sol in recent_solutions:
        if sol.ai_analysis_text:
            try:
                analysis_data = json.loads(sol.ai_analysis_text)
                if isinstance(analysis_data.get("strengths"), list):
                    all_strengths.extend([str(s).strip() for s in analysis_data["strengths"] if str(s).strip()])
                if isinstance(analysis_data.get("areas_for_improvement"), list):
                    all_areas_for_improvement.extend([str(a).strip() for a in analysis_data["areas_for_improvement"] if str(a).strip()])
            except json.JSONDecodeError:
                parse_errors += 1
            except Exception:
                 parse_errors += 1
    if parse_errors > 0:
         logger.warning(f"Encountered {parse_errors} errors parsing AI analysis for user {user_telegram_id} in progress.")

    strength_counts = Counter(all_strengths)
    improvement_counts = Counter(all_areas_for_improvement)
    top_n = 3
    common_strengths = strength_counts.most_common(top_n)
    common_improvements = improvement_counts.most_common(top_n)
    ai_feedback_shown = False

    progress_lines = []
    progress_lines.append(f"🏆 Ваш Текущий Ранг: {user_rank_escaped}")
    progress_lines.append(f"💡 Решено кейсов \\(засчитано\\): *{quality_solved_count}*")

    if recent_solutions:
        most_recent_solution = recent_solutions[0]
        last_solved_date = format_datetime_md(most_recent_solution.submitted_at)
        progress_lines.append(f"🗓️ Последняя активность: {last_solved_date}")
        display_limit = 3
        if len(recent_solutions) > 0:
            recent_count = min(len(recent_solutions), display_limit)
            progress_lines.append(f"\n🔍 *Недавние решения \\({recent_count} из последних\\):*")
            for i, sol in enumerate(recent_solutions[:display_limit]):
                case_title = "*Неизвестный кейс*"
                if sol.case and sol.case.title:
                    case_title = escape_md(sol.case.title)
                progress_lines.append(f"{i+1}\\. {case_title}")
    else:
        progress_lines.append("\nПока здесь пустовато, но это легко исправить\\!")
        progress_lines.append("Начните с кнопки «📝 Новый кейс» – это отличный старт для практики\\.")

    if avg_ai_rating is not None:
        avg_rating_str = f"{avg_ai_rating:.1f}".replace('.', '\\.')
        ratings_count = len(ai_ratings)
        progress_lines.append(f"\n📈 Средняя оценка анализа решений: *{avg_rating_str}/5* \\(на основе {ratings_count} последних\\)")
        ai_feedback_shown = True

    if common_strengths:
        progress_lines.append("\n⭐ *Ваши сильные стороны \\(по последним анализам\\):*")
        for strength, count in common_strengths:
            escaped_strength = escape_md(strength)
            progress_lines.append(f"\\- {escaped_strength}")
        ai_feedback_shown = True
    
    if common_improvements:
        progress_lines.append("\n🛠️ *Области для роста \\(рекомендации из анализа\\):*")
        for improvement, count in common_improvements:
            escaped_improvement = escape_md(improvement)
            progress_lines.append(f"\\- {escaped_improvement}")
        ai_feedback_shown = True

    if ai_feedback_shown:
        progress_lines.append("\n_Каждый решенный кейс – это шаг к мастерству\\! Продолжайте в том же духе\\._")
    else:
        progress_lines.append("\n_Практика – ключ к успеху\\! С каждым новым кейсом вы будете открывать для себя больше инсайтов\\._")

    return "\n".join(progress_lines)

@feature_router.message(F.text == "📊 Мой прогресс")
async def handle_my_progress_button(message: types.Message, session: AsyncSession):
    user_telegram_id = message.from_user.id
    logger.info(f"User {user_telegram_id} requested 'Мой прогресс' via text button/command.")
    
    progress_text = await _get_my_progress_content(user_telegram_id, session)
    
    await message.answer(
        progress_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="MarkdownV2"
    )

async def _get_tariffs_data(user_telegram_id: int, user_first_name: str, session: AsyncSession) -> tuple[str, bool, str, str]:
    """Generates tariffs text and subscription button data."""
    logger.info(f"Fetching tariffs data for user {user_telegram_id}.")
    
    db_user = await get_user_by_telegram_id(db=session, telegram_id=user_telegram_id)
    show_subscribe_button = True

    title_escaped = escape_md(MONTHLY_PLAN_TITLE)
    desc_escaped = escape_md(MONTHLY_PLAN_DESCRIPTION)
    price_info = f"Цена: {MONTHLY_PLAN_PRICE_RUB:.2f} {MONTHLY_PLAN_CURRENCY}"
    price_info_escaped = escape_md(price_info)

    tariffs_text = (
        f"💎 *{title_escaped}*\n"
        f"{desc_escaped}\n"
        f"💸 {price_info_escaped}\n\n"
        f"*Что включено:*\n"
        f"✅ Доступ ко всем кейсам\n"
        f"✅ Неограниченное количество решений\n"
        f"✅ Подробный AI\\-анализ каждого решения\n"
        f"✅ Персональная статистика и прогресс\n"
        f"✅ Доступ к истории решений\n\n"
        f"_Подписка автоматически продлевается каждый месяц\\. "
        f"Вы можете отключить автопродление в любой момент в настройках Telegram\\._"
    )

    plan_id_for_button = MONTHLY_PLAN_ID
    button_text_for_subscribe = f"🚀 {escape_md(MONTHLY_PLAN_TITLE)}"

    return tariffs_text, show_subscribe_button, plan_id_for_button, button_text_for_subscribe

@feature_router.message(F.text == "💳 Тарифы и подписка")
async def handle_tariffs_button(message: types.Message, session: AsyncSession):
    user_telegram_id = message.from_user.id
    logger.info(f"User {user_telegram_id} pressed 'Тарифы и подписка' text button/command.")
    
    tariffs_text, show_subscribe, plan_id, plan_button_text = await _get_tariffs_data(
        user_telegram_id, message.from_user.first_name, session
    )

    reply_markup = get_main_menu_keyboard()
    if show_subscribe:
        reply_markup = get_subscribe_inline_keyboard(plan_id=plan_id, plan_title=plan_button_text)
    
    await message.answer(tariffs_text, reply_markup=reply_markup, parse_mode="MarkdownV2")

@feature_router.message(F.text == "💳 Оплатить доступ")
async def handle_payment_button(message: types.Message, session: AsyncSession):
    user_telegram_id = message.from_user.id
    logger.info(f"User {user_telegram_id} pressed 'Оплатить доступ' button.")

    if not settings.TELEGRAM_PAYMENT_PROVIDER_TOKEN:
        logger.error("Payment initiation failed: TELEGRAM_PAYMENT_PROVIDER_TOKEN is not set.")
        await message.answer("К сожалению, функция оплаты сейчас недоступна. Попробуйте позже.", reply_markup=get_main_menu_keyboard())
        return

    db_user = await get_user_by_telegram_id(db=session, telegram_id=user_telegram_id)
    if not db_user:
        logger.warning(f"User {user_telegram_id} tried to pay but not found in DB. Redirecting to /start.")
        await message.answer("Не удалось найти ваш аккаунт. Пожалуйста, начните с команды /start.", reply_markup=get_main_menu_keyboard())
        return

    if db_user.subscription_status == SubscriptionStatus.ACTIVE and db_user.subscription_expires_at:
        expires_at = db_user.subscription_expires_at
        expires_at_str = expires_at.strftime('%d.%m.%Y %H:%M UTC')
        await message.answer(
            f"У вас уже есть активная подписка '{db_user.current_plan_name or MONTHLY_PLAN_TITLE}', которая действует до {expires_at_str}.\n\nВы можете продлить её — новая дата окончания будет увеличена на 30 дней.",
            reply_markup=get_main_menu_keyboard()
        )
    # В любом случае отправляем invoice
    internal_transaction_id = f"btrainer_sub_{MONTHLY_PLAN_ID}_{uuid.uuid4()}"
    await transaction_crud.create_transaction(
        db=session,
        user_id=db_user.id,
        internal_transaction_id=internal_transaction_id,
        amount=Decimal(str(MONTHLY_PLAN_PRICE_RUB)),
        currency=MONTHLY_PLAN_CURRENCY,
        plan_name=MONTHLY_PLAN_ID
    )
    logger.info(f"Created PENDING transaction {internal_transaction_id} for user {user_telegram_id} for plan {MONTHLY_PLAN_ID}")

    prices = [LabeledPrice(label=MONTHLY_PLAN_TITLE, amount=int(MONTHLY_PLAN_PRICE_RUB * 100))]

    await message.bot.send_invoice(
        chat_id=message.chat.id,
        title=MONTHLY_PLAN_TITLE,
        description=MONTHLY_PLAN_DESCRIPTION,
        payload=internal_transaction_id, # Our unique internal transaction ID
        provider_token=settings.TELEGRAM_PAYMENT_PROVIDER_TOKEN,
        currency=MONTHLY_PLAN_CURRENCY,
        prices=prices,
        start_parameter="btrainer-monthly-sub", # Optional deep-linking parameter
        reply_markup=None
    )
    logger.info(f"Invoice for plan {MONTHLY_PLAN_ID} sent to user {user_telegram_id} with payload {internal_transaction_id}")

@feature_router.callback_query(F.data.startswith("subscribe_action:"))
async def handle_subscribe_callback(query: types.CallbackQuery, session: AsyncSession):
    user_telegram_id = query.from_user.id
    plan_id_from_callback = query.data.split(":")[1]

    logger.info(f"User {user_telegram_id} pressed inline subscribe button for plan_id: {plan_id_from_callback}")

    if not settings.TELEGRAM_PAYMENT_PROVIDER_TOKEN:
        logger.error(f"Payment initiation failed for user {user_telegram_id} (callback): TELEGRAM_PAYMENT_PROVIDER_TOKEN is not set.")
        await query.answer("К сожалению, функция оплаты сейчас недоступна. Попробуйте позже.", show_alert=False)
        return

    db_user = await get_user_by_telegram_id(db=session, telegram_id=user_telegram_id)
    if not db_user:
        logger.warning(f"User {user_telegram_id} (callback) tried to pay but not found in DB.")
        await query.answer("Не удалось найти ваш аккаунт. Пожалуйста, начните с команды /start.", show_alert=False)
        return

    if db_user.subscription_status == SubscriptionStatus.ACTIVE and db_user.subscription_expires_at:
        expires_at = db_user.subscription_expires_at
        expires_at_str = expires_at.strftime('%d.%m.%Y %H:%M UTC')
        # await query.answer(
        #     f"У вас уже есть активная подписка '{MONTHLY_PLAN_TITLE}', действует до {expires_at_str}. Вы можете продлить её — новая дата окончания будет увеличена на 30 дней."
        # )
    # В любом случае отправляем invoice
    if plan_id_from_callback == MONTHLY_PLAN_ID:
        current_plan_title = MONTHLY_PLAN_TITLE
        current_plan_description = MONTHLY_PLAN_DESCRIPTION
        current_plan_price_rub = MONTHLY_PLAN_PRICE_RUB
        current_plan_currency = MONTHLY_PLAN_CURRENCY
    else:
        logger.error(f"Unknown plan_id '{plan_id_from_callback}' received from subscribe_action for user {user_telegram_id}.")
        await query.answer("Выбран неизвестный тариф. Пожалуйста, попробуйте еще раз.", show_alert=False)
        return

    internal_transaction_id = f"btrainer_sub_{plan_id_from_callback}_{uuid.uuid4()}"
    await transaction_crud.create_transaction(
        db=session,
        user_id=db_user.id,
        internal_transaction_id=internal_transaction_id,
        amount=Decimal(str(current_plan_price_rub)),
        currency=current_plan_currency,
        plan_name=plan_id_from_callback
    )
    logger.info(f"Created PENDING transaction {internal_transaction_id} for user {user_telegram_id} (callback) for plan {plan_id_from_callback}")

    prices = [LabeledPrice(label=current_plan_title, amount=int(current_plan_price_rub * 100))]

    try:
        logger.info(f"Attempting to send invoice with provider token: {settings.TELEGRAM_PAYMENT_PROVIDER_TOKEN[:10]}...")
        await query.bot.send_invoice(
            chat_id=query.message.chat.id,
            title=current_plan_title,
            description=current_plan_description,
            payload=internal_transaction_id,
            provider_token=settings.TELEGRAM_PAYMENT_PROVIDER_TOKEN,
            currency=current_plan_currency,
            prices=prices,
            start_parameter=f"btrainer-sub-{plan_id_from_callback}",
        )
        await query.answer()
        logger.info(f"Invoice for plan {plan_id_from_callback} sent to user {user_telegram_id} (callback) with payload {internal_transaction_id}")

    except Exception as e:
        logger.error(f"Failed to send invoice to user {user_telegram_id} (callback) for plan {plan_id_from_callback}: {e}", exc_info=True)
        await query.answer("Не удалось выставить счет. Пожалуйста, попробуйте позже или свяжитесь с поддержкой.", show_alert=False)
        await query.message.answer("Произошла ошибка при попытке выставить счет. Пожалуйста, попробуйте позже или воспользуйтесь кнопкой '💳 Оплатить доступ' в главном меню.", reply_markup=get_main_menu_keyboard())

@feature_router.message(F.text == "💬 Оставить отзыв")
async def handle_leave_feedback_text_button(message: types.Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} pressed 'Оставить отзыв' text button.")
    await state.set_state(FeedbackStates.awaiting_feedback_text)
    await message.answer(
        "📝 Расскажите, что думаете! Ваш отзыв поможет нам стать лучше. "
        "Постарайтесь описать свои впечатления или предложения как можно подробнее – "
        "так мы сможем быстрее во всем разобраться и учесть ваше мнение. "
        "Отправьте всё одним сообщением, пожалуйста."
    )

@feature_router.message(FeedbackStates.awaiting_feedback_text, F.text & ~F.text.startswith('/'))
async def process_feedback_text(message: types.Message, session: AsyncSession, state: FSMContext):
    feedback_text = message.text
    user_telegram_id = message.from_user.id
    current_user_role = UserRole.USER

    if not feedback_text or len(feedback_text.strip()) < 10:
        await message.reply(
            "Хм, кажется, в вашем сообщении маловато деталей. "
            "Чтобы мы могли как следует вникнуть, расскажите, пожалуйста, подробнее (хотя бы пару предложений)."
        )
        return

    db_user = await get_user_by_telegram_id(db=session, telegram_id=user_telegram_id)
    if not db_user:
        logger.warning(f"User {user_telegram_id} tried to leave feedback but not found in DB.")
        await message.answer(
            "Не удалось найти вашу учетную запись. Пожалуйста, попробуйте /start и затем снова оставьте отзыв."
        )
        await state.clear()
        return
    current_user_role = db_user.role

    ai_analysis_result = None
    is_meaningful_ai = None
    ai_reason = "AI analysis not performed or failed."
    ai_category = "unknown"
    raw_ai_data = None

    await message.answer("✨ Спасибо! Ваш отзыв принят и скоро будет рассмотрен.")

    try:
        ai_analysis_result = await ai_service.analyze_feedback_substance(feedback_text)
        if ai_analysis_result:
            raw_ai_data = ai_analysis_result
            is_meaningful_ai = ai_analysis_result.get("is_meaningful")
            ai_reason = ai_analysis_result.get("reason", "No reason provided by AI.")
            ai_category = ai_analysis_result.get("category", "unknown")
            logger.info(f"AI analysis for feedback from {user_telegram_id}: Meaningful={is_meaningful_ai}, Category='{ai_category}', Reason='{ai_reason}'")
        else:
            logger.warning(f"AI analysis returned None for feedback from {user_telegram_id}.")
            ai_reason = "AI analysis did not return a result."

    except Exception as e:
        logger.error(f"Error during AI feedback analysis for user {user_telegram_id}: {e}", exc_info=True)
        ai_reason = f"Error during AI analysis: {str(e)}"

    try:
        new_feedback = await crud.create_feedback(
            db=session, 
            user_id=db_user.id, 
            text=feedback_text,
            is_meaningful_ai=is_meaningful_ai,
            ai_analysis_reason=ai_reason,
            ai_analysis_category=ai_category,
            raw_ai_response=raw_ai_data
        )
        logger.info(f"Feedback from user {db_user.telegram_id} saved with ID {new_feedback.id}, AI meaningful: {is_meaningful_ai}, Category: {ai_category}.")
        
        response_message = "✅ Готово! Ваш отзыв получен и бережно сохранен."
        response_message += "\nКаждое мнение важно для нас, и мы обязательно его изучим."

        await message.answer(
            response_message, 
            reply_markup=get_main_menu_keyboard(user_role=current_user_role)
        )
    except Exception as e:
        logger.error(f"Failed to save feedback (with AI analysis) for user {db_user.telegram_id}: {e}", exc_info=True)
        await message.answer(
            "Ой, что-то пошло не так, и ваш отзыв не сохранился. "
            "Пожалуйста, попробуйте отправить его еще раз чуть позже. Мы уже разбираемся!",
            reply_markup=get_main_menu_keyboard(user_role=current_user_role)
        )
    finally:
        await state.clear()

@feature_router.callback_query(F.data == "main_menu:request_case")
async def cq_main_menu_request_case(query: types.CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    logger.info(f"User {query.from_user.id} selected 'Request Case' from inline menu.")
    await query.answer("Загружаю новый кейс...")

    await _generate_and_send_case(message_or_callback_query=query, state=state, session=session)

    try:
        await query.message.edit_text(
            "✔️ Новый кейс был отправлен вам в отдельном сообщении ниже!",
            reply_markup=get_back_to_main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Error editing original menu message after sending case: {e}")

@feature_router.callback_query(F.data == "main_menu:my_progress")
async def cq_main_menu_my_progress(query: types.CallbackQuery, session: AsyncSession):
    logger.info(f"User {query.from_user.id} selected 'My Progress' from inline menu.")
    await query.answer()
    
    progress_text = await _get_my_progress_content(query.from_user.id, session)
    
    await query.message.edit_text(
        text=progress_text,
        reply_markup=get_back_to_main_menu_keyboard(),
        parse_mode="MarkdownV2"
    )

@feature_router.callback_query(F.data == "main_menu:leave_feedback")
async def cq_main_menu_leave_feedback(query: types.CallbackQuery, state: FSMContext):
    logger.info(f"User {query.from_user.id} selected 'Leave Feedback' from inline menu.")
    await query.answer()

    await state.set_state(FeedbackStates.awaiting_feedback_text)
    
    feedback_prompt_text = (
        "📝 Расскажите, что думаете! Ваш отзыв поможет нам стать лучше. "
        "Постарайтесь описать свои впечатления или предложения как можно подробнее – "
        "так мы сможем быстрее во всем разобраться и учесть ваше мнение. "
        "Отправьте всё одним сообщением, пожалуйста!"
    )

    await query.message.edit_text(
        text=feedback_prompt_text,
        reply_markup=get_back_to_main_menu_keyboard() # Only Back button
    )

@feature_router.callback_query(F.data == "main_menu:tariffs")
async def cq_main_menu_tariffs(query: types.CallbackQuery, session: AsyncSession):
    logger.info(f"User {query.from_user.id} selected 'Tariffs' from inline menu.")
    await query.answer()

    tariffs_text, show_subscribe, plan_id, plan_button_text = await _get_tariffs_data(
        query.from_user.id, query.from_user.first_name, session
    )

    builder = InlineKeyboardBuilder()
    if show_subscribe:
        builder.button(text=plan_button_text, callback_data=f"subscribe_action:{plan_id}")
    builder.button(text="⬅️ Назад в главное меню", callback_data="main_menu:show")
    builder.adjust(1)

    await query.message.edit_text(
        text=tariffs_text,
        reply_markup=builder.as_markup(),
        parse_mode="MarkdownV2"
    )

@feature_router.callback_query(F.data == "main_menu:help")
async def cq_main_menu_help(query: types.CallbackQuery, state: FSMContext):
    logger.info(f"User {query.from_user.id} selected 'Help' from inline menu.")
    await query.answer()
    await query.message.edit_text(
        text=HELP_TEXT,
        reply_markup=get_back_to_main_menu_keyboard(),
        parse_mode="HTML"
    )

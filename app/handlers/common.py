import logging
from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.utils.markdown import hbold
from sqlalchemy.orm import Session
import datetime

from app.db import crud
from app.db.models import SubscriptionStatus
from app.ui.keyboards import get_main_menu_keyboard, get_after_case_keyboard

common_router = Router(name=__name__) 

@common_router.message(CommandStart())
async def handle_start(
    message: types.Message, 
    db_session: Session, 
):
    user = message.from_user
    logger = logging.getLogger(__name__)
    logger.info(f"User {user.id} ({user.full_name}) started chat.")

    db_user = crud.get_user_by_telegram_id(db=db_session, telegram_id=user.id)
    main_menu_kb = get_main_menu_keyboard()

    if db_user:
        logger.info(f"User {user.id} already exists in DB. Updating activity.")
        crud.update_user_activity(db=db_session, telegram_id=user.id)
        if db_user.is_blocked:
            await message.answer("Ваш аккаунт заблокирован. Обратитесь к администратору.")
            logger.warning(f"Blocked user {user.id} tried to use /start.")
            return 
        greeting_message = f"С возвращением, {hbold(user.first_name)}!\n"
        greeting_message += "Готовы продолжить улучшать свои навыки?"
    else:
        logger.info(f"New user {user.id}. Creating new DB entry.")
        db_user = crud.create_user(
            db=db_session, 
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code
            # Пример добавления триального периода при регистрации:
            # subscription_status=SubscriptionStatus.TRIAL,
            # trial_start_date=datetime.datetime.now(datetime.timezone.utc),
            # trial_end_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
        )
        greeting_message = (
            f"Привет, {hbold(user.first_name)}! Я <b>BTrainer</b>.\n"
            f"Я помогаю КПТ-психотерапевтам улучшать свои профессиональные навыки с помощью практики на сгенерированных кейсах.\n\n"
            f"Используйте кнопки ниже для навигации:"
        )
        logger.info(f"User {db_user.telegram_id} (internal id: {db_user.id}) created in DB.")

    await message.answer(
        greeting_message,
        reply_markup=main_menu_kb
    )

@common_router.message(Command("help"))
async def handle_help(message: types.Message, db_session: Session):
    help_text = (
        "Я бот <b>BTrainer</b>, ваш помощник для практики навыков КПТ.\n\n"
        "Доступные команды:\n"
        "/start - начало работы, приветствие\n"
        "/case или кнопка '💼 Получить кейс' - получить новый терапевтический кейс\n"
        "/progress или кнопка '📊 Мой прогресс' - посмотреть ваш прогресс\n"
        "/tariffs или кнопка '💲 Тарифы' - узнать о тарифах и подписке\n"
        "/help или кнопка 'ℹ Помощь' - показать это сообщение\n\n"
        "Также вы можете использовать кнопки внизу экрана для быстрого доступа к этим командам."
    )
    await message.answer(help_text, reply_markup=get_main_menu_keyboard())

@common_router.message(F.text == "ℹ Помощь")
async def handle_help_button(message: types.Message, db_session: Session):
    await handle_help(message, db_session)

@common_router.message(F.text == "💼 Получить кейс")
async def handle_request_case_button(message: types.Message, db_session: Session):
    user = message.from_user
    logger = logging.getLogger(__name__)
    logger.info(f"User {user.id} requested a new case via button.")

    case_title_placeholder = "Кейс: Сложности в общении с коллегами"
    case_description_placeholder = (
        "Клиент, мужчина 35 лет, менеджер среднего звена, обратился с жалобами на "
        "постоянные конфликты с одним из коллег. Это вызывает у него сильный стресс, "
        "снижает продуктивность и ухудшает общую атмосферу в коллективе. "
        "Клиент описывает коллегу как 'агрессивного' и 'не желающего идти на компромисс'. "
        "Сам клиент старается избегать открытых конфронтаций, но чувствует, что напряжение растет. "
        "Запрос: помочь клиенту выработать стратегию поведения для разрешения конфликта или "
        "минимизации его негативного влияния."
    )
    ai_model_name = "DeepSeek_placeholder_v0.1"
    prompt_version_placeholder = "generic_case_prompt_v1"


    try:
        new_case = crud.create_case(
            db=db_session,
            title=case_title_placeholder,
            description=case_description_placeholder,
            ai_model_used=ai_model_name,
            prompt_version=prompt_version_placeholder,
            # created_by_user_id=user.id 
        )
        logger.info(f"Case {new_case.id} created and saved to DB for user {user.id}.")

        response_text = f"{hbold(new_case.title)}\n\n{new_case.description}"
        
        await message.answer(
            response_text,
            reply_markup=get_after_case_keyboard(case_id=new_case.id)
        )

    except Exception as e:
        logger.error(f"Error processing case request for user {user.id}: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при подготовке кейса. Пожалуйста, попробуйте еще раз позже."
        )

@common_router.message(F.text == "📊 Мой прогресс")
async def handle_my_progress_button(message: types.Message, db_session: Session):
    user_id = message.from_user.id
    logger = logging.getLogger(__name__)
    logger.info(f"User {user_id} requested their progress via button.")
    
    # TODO: Здесь будет логика получения данных о прогрессе пользователя из БД
    # (например, количество решенных кейсов, средние оценки и т.д.)
    
    await message.answer(
        "Вы выбрали 'Мой прогресс'. Здесь будет отображаться ваша статистика по решенным кейсам."
    )

@common_router.message(F.text == "💲 Тарифы")
async def handle_tariffs_button(message: types.Message, db_session: Session):
    """
    Обработчик для кнопки '💲 Тарифы'.
    Пока что просто отправляет заглушку.
    """
    user_id = message.from_user.id
    logger = logging.getLogger(__name__)
    logger.info(f"User {user_id} requested tariff information via button.")
    
    # TODO: Здесь будет логика отображения информации о тарифах
    # Возможно, с инлайн-кнопками для выбора тарифа и перехода к оплате.
    
    await message.answer(
        "Информация о тарифах и вариантах подписки будет здесь. Вы сможете выбрать подходящий план."
    )

@common_router.message(F.text == "💳 Оплатить доступ")
async def handle_payment_button(message: types.Message, db_session: Session):
    """
    Обработчик для кнопки '💳 Оплатить доступ'.
    Пока что просто отправляет заглушку.
    """
    user_id = message.from_user.id
    logger = logging.getLogger(__name__)
    logger.info(f"User {user_id} requested payment options via button.")

    # TODO: Здесь будет логика перехода к оплате (YooKassa API)
    # Возможно, сначала нужно будет показать доступные тарифы для оплаты,
    # если пользователь не пришел сюда с экрана тарифов.

    await message.answer(
        "Здесь будет информация о способах оплаты и возможность оплатить доступ к полному функционалу бота."
    )


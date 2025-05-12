from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="💼 Получить кейс"),
        KeyboardButton(text="📊 Мой прогресс")
    )
    builder.row(
        KeyboardButton(text="💲 Тарифы"),
        KeyboardButton(text="💳 Оплатить доступ")
    )
    builder.row(
        KeyboardButton(text="ℹ Помощь")
    )
    # resize_keyboard=True делает кнопки меньше, one_time_keyboard=False оставляет клавиатуру видимой
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False) 


def get_after_case_keyboard(case_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # builder.button(text="✏ Я готов(а) написать решение", callback_data=f"solve_case_{case_id}")
    builder.button(text="🔀 Запросить другой кейс", callback_data="request_another_case")
    builder.adjust(1)
    return builder.as_markup()

def get_after_solution_analysis_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💼 Получить новый кейс", callback_data="request_case_again")
    return builder.as_markup()

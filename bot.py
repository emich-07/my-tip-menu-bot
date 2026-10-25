import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from openai import AsyncOpenAI

logging.basicConfig(level=logging.INFO)

# ================= НАСТРОЙКИ =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
AI_KEY = os.getenv("AI_KEY")

ai_client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=AI_KEY,
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class MenuForm(StatesGroup):
    waiting_description = State()
    reviewing_menu = State()

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎥 Tip Menu (Chaturbate)", callback_data="platform:chaturbate")],
            [InlineKeyboardButton(text="💜 Tip Menu (Stripchat)", callback_data="platform:stripchat")],
            [InlineKeyboardButton(text="🎯 Цели для шоу во фри (Goal)", callback_data="platform:goal")],
        ]
    )
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Выбери, что ты хочешь создать:",
        reply_markup=keyboard,
    )

@dp.callback_query(F.data.startswith("platform:"))
async def platform_chosen(call: CallbackQuery, state: FSMContext):
    platform = call.data.split(":")[1]
    
    if platform == "goal":
        await state.update_data(platform="goal")
        await state.set_state(MenuForm.waiting_description)
        await call.answer()
        await call.message.edit_text(
            "✅ Ты выбрала: <b>Цели для шоу во фри (Goal)</b>\n\n"
            "Опиши, что ты делаешь на стриме (например: раздеваюсь, играю с игрушками, танцую).",
            parse_mode="HTML",
        )
        return

    names = {"chaturbate": "Chaturbate", "stripchat": "Stripchat"}
    platform_name = names.get(platform, platform)

    await state.update_data(platform=platform)
    await state.set_state(MenuForm.waiting_description)

    await call.answer()
    await call.message.edit_text(
        f"✅ Ты выбрала: <b>{platform_name}</b>\n\n"
        "Теперь опиши свободным текстом, что ты делаешь.",
        parse_mode="HTML",
    )

@dp.message(MenuForm.waiting_description)
async def description_received(message: Message, state: FSMContext):
    data = await state.get_data()
    platform = data.get("platform", "unknown")
    description = message.text

    # Проверка на запрещенные слова
    forbidden = ["встреч", "эскорт", "escort", "проститут", "менструац", "рвот", "фекал", "моч", "животн", "animal"]
    found = [word for word in forbidden if word in description.lower()]

    if found:
        await message.answer(
            f"⚠️ <b>Внимание!</b> Найдены запрещенные слова:\n<code>{', '.join(found)}</code>\n\n"
            "Отправь описание ещё раз без них.",
            parse_mode="HTML",
        )
        return

    await state.update_data(description=description)
    await state.set_state(MenuForm.reviewing_menu)
    
    await message.answer("⏳ Думаю, подожди пару секунд...")
    # Передаем previous_text=None, так как это первая генерация
    await generate_and_send_menu(message, platform, description, previous_text=None, state=state)

# Универсальная функция генерации
async def generate_and_send_menu(message: Message, platform: str, description: str, previous_text: str = None, state: FSMContext = None):
    
    # Если есть предыдущий текст, добавляем его в промпт, чтобы ИИ не повторялся
    avoid_repeat_prompt = ""
    if previous_text:
        avoid_repeat_prompt = (
            f"\nВАЖНО: Ранее уже был сгенерирован следующий список. НЕ ПОВТОРЯЙ эти позиции, придумай новые:\n{previous_text}\n"
        )

    if platform == "goal":
        system_prompt = (
            "Ты — профессиональный менеджер вебкам-моделей. Создай список ЭРОТИЧНЫХ И СЕКСУАЛЬНЫХ ЦЕЛЕЙ (Goals). "
            "ФОРМАТ: 'Эмодзи Действие (Цена)'. "
            "1. РОВНО 7-10 целей. 2. Цены СТРОГО ПО ВОЗРАСТАНИЮ. "
            "3. Логика: возбуждающее шоу, где шаг вытекает из предыдущего. "
            "4. Действия должны быть КОРОТКИМИ, ПОНЯТНЫМИ и ОЧЕНЬ ЭРОТИЧНЫМИ (например: 'Снять топ (50)', 'Lush на макс (100)', 'Полностью раздеться (200)'). Никаких длинных предложений. "
            "5. ТОЛЬКО список."
            f"{avoid_repeat_prompt}"
        )
        title = "Эротичные цели"
    else:
        system_prompt = (
            "Ты — профессиональный менеджер вебкам-моделей. Создай Tip Menu. "
            "ФОРМАТ: 'Эмодзи Действие (Цена)'. "
            "1. РОВНО 24 позиции. 2. Первые две: '👋 Hello (3)', '💌 One PM, please (7)'. "
            "3. Цены СТРОГО ПО ВОЗРАСТАНИЮ (от 3 до 9999). 4. Логика: от простого к сложному. "
            "5. 24-я позиция ОБЯЗАТЕЛЬНО 10000 (например: '👑 Dream tip (10000)'). "
            "6. ТОЛЬКО список."
            f"{avoid_repeat_prompt}"
        )
        title = f"Tip Menu для {platform}"

    try:
        response = await ai_client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": description}]
        )
        menu_text = response.choices[0].message.content

        # Сохраняем сгенерированный текст в состояние, чтобы при следующей генерации его избегать
        if state:
            await state.update_data(last_generated=menu_text)

        # Создаем кнопки
        buttons = [[InlineKeyboardButton(text="🔄 Сгенерировать заново", callback_data="regen")]]
        
        if platform == "goal":
            buttons.append([InlineKeyboardButton(text="🎁 Создать Tip Menu в этой же тематике", callback_data="switch_to_menu")])
        else:
            buttons.append([InlineKeyboardButton(text="🎯 Создать Цели в этой же тематике", callback_data="switch_to_goal")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

        await message.answer(
            f"🔥 <b>Вот твои {title}:</b>\n\n<pre>{menu_text}</pre>",
            parse_mode="HTML",
            reply_markup=kb
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка ИИ: {str(e)}")

# Обработчик кнопки "Перегенерировать"
@dp.callback_query(F.data == "regen")
async def regen_menu(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    description = data.get("description")
    platform = data.get("platform", "unknown")
    last_generated = data.get("last_generated") # Берем предыдущий результат

    if not description:
        await call.answer("Не могу найти описание. Напиши /start заново.", show_alert=True)
        return

    await call.answer("Генерирую новый вариант... 🔄")
    await generate_and_send_menu(call.message, platform, description, previous_text=last_generated, state=state)

# Обработчик переключения на Цели
@dp.callback_query(F.data == "switch_to_goal")
async def switch_to_goal(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    description = data.get("description")
    last_generated = data.get("last_generated") # Берем меню, чтобы цели его не повторяли
    
    if not description:
        await call.answer("Ошибка: описание потерялось. Напиши /start.", show_alert=True)
        return

    await state.update_data(platform="goal")
    await call.answer("Генерирую цели на основе твоего описания... 🎯")
    await generate_and_send_menu(call.message, "goal", description, previous_text=last_generated, state=state)

# Обработчик переключения на Меню
@dp.callback_query(F.data == "switch_to_menu")
async def switch_to_menu(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    description = data.get("description")
    last_generated = data.get("last_generated") # Берем цели, чтобы меню их не повторяло
    platform = data.get("last_platform", "chaturbate") 
    
    if not description:
        await call.answer("Ошибка: описание потерялось. Напиши /start.", show_alert=True)
        return

    await state.update_data(platform=platform)
    await call.answer("Генерирую Tip Menu на основе твоего описания... 🎁")
    await generate_and_send_menu(call.message, platform, description, previous_text=last_generated, state=state)

async def main():
    print("Бот запущен! Иди в Telegram и напиши ему /start")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

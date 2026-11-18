import asyncio
import logging
from logging.handlers import RotatingFileHandler
import os
from dotenv import load_dotenv
load_dotenv() # Загружаем ключи из файла .env

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    MenuButtonCommands, BotCommand
)
from openai import AsyncOpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        RotatingFileHandler("bot.log", maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# ================= НАСТРОЙКИ =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
AI_KEY = os.getenv("AI_KEY")

ai_client = AsyncOpenAI(
    base_url="https://gen.pollinations.ai/v1",
    api_key="sk_BGUFmk3diYpp6CFyD0xOAt8V0rNJaprn",
)

bot = Bot(token=BOT_TOKEN, timeout=30)
dp = Dispatcher(storage=MemoryStorage())

class MenuForm(StatesGroup):
    choosing_category = State() # <--- НОВОЕ
    choosing_mode = State()
    waiting_description = State()
    reviewing_menu = State()

async def send_main_menu(message: Message, state: FSMContext):
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎥 Tip Menu (Chaturbate)", callback_data="platform:chaturbate")],
            [InlineKeyboardButton(text="💜 Tip Menu (Stripchat)", callback_data="platform:stripchat")],
            [InlineKeyboardButton(text="🎯 Цели для шоу во фри (Goal)", callback_data="platform:goal")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ]
    )
    
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Выбери, что ты хочешь создать:",
        reply_markup=keyboard,
    )

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await send_main_menu(message, state)

@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    
    try:
        await call.message.edit_text(
            f"Привет, {call.from_user.first_name}! 👋\n\n"
            "Выбери, что ты хочешь создать:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🎥 Tip Menu (Chaturbate)", callback_data="platform:chaturbate")],
                    [InlineKeyboardButton(text="💜 Tip Menu (Stripchat)", callback_data="platform:stripchat")],
                    [InlineKeyboardButton(text="🎯 Цели для шоу во фри (Goal)", callback_data="platform:goal")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ]
            )
        )
    except Exception:
        try:
                await call.message.delete()
        except Exception as e:    
                logging.warning(f"Не удалось удалить сообщение: {e}")
        await send_main_menu(call.message, state)

@dp.callback_query(F.data.startswith("platform:"))
async def platform_chosen(call: CallbackQuery, state: FSMContext):
    platform = call.data.split(":")[1]
    await state.update_data(platform=platform)
    
    if platform != "goal":
        await state.update_data(last_platform=platform)

    await call.answer()

    names = {"chaturbate": "Chaturbate", "stripchat": "Stripchat", "goal": "Цели во фри (Goal)"}
    platform_name = names.get(platform, platform)

    # ЕСЛИ ЭТО ЦЕЛИ - СРАЗУ ИДЕМ В ВЫБОР РЕЖИМА (БЕЗ КАТЕГОРИЙ)
    if platform == "goal":
        await state.update_data(category="None")
        await state.set_state(MenuForm.choosing_mode)
        mode_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔥 Модель раздевается во фри чате", callback_data="mode:strips")],
                [InlineKeyboardButton(text="👗 Модель Ноу нюд (без обнажения)", callback_data="mode:nonude")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]
        )
        await call.message.edit_text(
            f"✅ Ты выбрала: <b>{platform_name}</b>\n\n"
            "Теперь выбери режим работы модели:",
            parse_mode="HTML",
            reply_markup=mode_keyboard
        )
        return

    # ЕСЛИ ЭТО TIP MENU - ПОКАЗЫВАЕМ КАТЕГОРИИ
    await state.set_state(MenuForm.choosing_category)
    category_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🩸 Шоу для месячных", callback_data="category:period")],
            [InlineKeyboardButton(text="🎄 Новый год", callback_data="category:halloween")],
            [InlineKeyboardButton(text="🛢️ Шоу с маслом", callback_data="category:oil")],
            [InlineKeyboardButton(text="🥛 Шоу с молоком", callback_data="category:milk")],
            [InlineKeyboardButton(text="👗 Шоу со сменой одежды", callback_data="category:outfit")],
            [InlineKeyboardButton(text="✨ Без тематики (обычное)", callback_data="category:None")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ]
    )

    await call.message.edit_text(
        f"✅ Ты выбрала: <b>{platform_name}</b>\n\n"
        "Выбери тематику для Tip Menu (или пропусти этот шаг):",
        parse_mode="HTML",
        reply_markup=category_keyboard
    )

@dp.callback_query(F.data.startswith("category:"))
async def category_chosen(call: CallbackQuery, state: FSMContext):
    category = call.data.split(":")[1]
    await state.update_data(category=category)
    await state.set_state(MenuForm.choosing_mode)
    await call.answer()

    # После выбора категории показываем выбор режима (как было раньше)
    mode_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Модель раздевается во фри чате", callback_data="mode:strips")],
            [InlineKeyboardButton(text="👗 Модель Ноу нюд (без обнажения)", callback_data="mode:nonude")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ]
    )

    cat_names = {
        "period": "🔴 Шоу для месячных", "halloween": "🎄 Новый год", 
        "oil": "🛢️ Шоу с маслом", "milk": "🥛 Шоу с молоком", 
        "outfit": "👗 Смена одежды", "None": "✨ Без тематики"
    }
    
    await call.message.edit_text(
        f"✅ Выбрана тематика: <b>{cat_names.get(category, category)}</b>\n\n"
        "Теперь выбери режим работы модели:",
        parse_mode="HTML",
        reply_markup=mode_keyboard
    )

@dp.callback_query(F.data.startswith("mode:"))
async def mode_chosen(call: CallbackQuery, state: FSMContext):
    mode = call.data.split(":")[1]
    await state.update_data(mode=mode)
    await state.set_state(MenuForm.waiting_description)
    await call.answer()

    mode_name = "🔥 Раздевается во фри чате" if mode == "strips" else "👗 Ноу нюд (No Nude)"

    await call.message.edit_text(
        f"✅ Выбран режим: <b>{mode_name}</b>\n\n"
        "Опиши свободным текстом, что ты делаешь (например: танцую, общаюсь, играю с игрушками, стримлю из спальни).",
        parse_mode="HTML",
    )

@dp.message(MenuForm.waiting_description)
async def description_received(message: Message, state: FSMContext):
    data = await state.get_data()
    platform = data.get("platform", "unknown")
    mode = data.get("mode", "strips")
    description = message.text

    forbidden = [
        # Русские (встречи, эскорт, жесть)
        "встреч", "эскорт", "проститут", "менструац", "рвот", "фекал", "моч", "животн", "живот", "собак", "кошк", "смерт", "убийств", "школьн", "детск",
        # Английские (встречи, эскорт, насилие, дети, животные)
        "escort", "meet", "real life", "irl", "animal", "dog", "cat", "child", "kid", "teen", "school", "underage", "blood", "vomit", "scat", "piss", "death", "kill", "gore"
    ]
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
    await generate_and_send_menu(message, platform, mode, description, previous_text=None, state=state)

@dp.message(MenuForm.reviewing_menu)
async def revision_received(message: Message, state: FSMContext):
    data = await state.get_data()
    previous_text = data.get("last_generated")
    platform = data.get("platform", "unknown")
    mode = data.get("mode", "strips")
    description = data.get("description", "")

    if not previous_text:
        await message.answer("Не могу найти предыдущее меню. Нажми /start, чтобы начать заново.")
        return

    revision_request = message.text
    await message.answer("⏳ Вношу корректировки, подожди пару секунд...")
    
    await generate_and_send_menu(
        message, platform, mode, description,
        previous_text=previous_text,
        state=state,
        revision_request=revision_request
    )

async def generate_and_send_menu(message: Message, platform: str, mode: str, description: str, previous_text: str = None, state: FSMContext = None, revision_request: str = None, category: str = None):
    avoid_repeat_prompt = ""
    if previous_text and not revision_request:
        avoid_repeat_prompt = (
            "\nCRITICAL WARNING: The following actions were ALREADY GENERATED. "
            "You are STRICTLY FORBIDDEN from using ANY of these actions, even with different prices or slight wording changes. "
            "Every single new position MUST be completely unique and different from this list:\n"
            f"{previous_text}\n"
        )

    # 1. БЛОК КАТЕГОРИЙ
    data = await state.get_data() if state else {}
    category = data.get("category", "None")
    category_prompt = ""
    
    if category == "period":
        category_prompt = (
            "\nCRITICAL THEME OVERRIDE: The model is on her period (Red Week). "
            "STRICTLY FORBIDDEN to mention pads, tampons, blood, or period products. "
            "The model WILL NOT remove her panties or bottoms. "
            "Focus ONLY on upper body, gentle teasing, sitting/lying poses. NO heavy activity, NO bottom removal. "
            "If the user says 'striptease', make it upper-body only. If 'dancing', make it a gentle sway."
        )
    elif category == "halloween":
        category_prompt = "\nCRITICAL THEME FUSION: The user selected 'New Year'. Merge the description with New Year elements (Santa, Christmas tree, gifts, snow, champagne, festive lights)."
    elif category == "oil":
        category_prompt = "\nCRITICAL THEME FUSION: The user selected 'Oil Show'. Merge the description with oil elements (slippery, massage, baby oil)."
    elif category == "milk":
        category_prompt = "\nCRITICAL THEME FUSION: The user selected 'Milk Show'. Merge the description with milk elements (pouring milk, milk bath)."
    elif category == "outfit":
        category_prompt = "\nCRITICAL THEME FUSION: The user selected 'Outfit Change'. Merge the description with clothing elements (lingerie, trying on outfits, unzipping)."

    # 2. БЛОК РЕЖИМОВ
    if mode == "nonude":
        mode_prompt = (
            "\nIMPORTANT: The model works in 'No Nude' mode. STRICTLY FORBIDDEN to generate positions with full nudity (nipples, genitals) and explicit sexual acts. "
            "Include only: teasing, hints, playing with clothes (pull down strap, show lingerie), seductive poses, focus on legs, look, lips."
        )
    else:
        mode_prompt = (
            "\nIMPORTANT: The model works in 'Strips in free chat' mode. Generate explicit positions with gradual undressing, showing intimate parts, and sexual acts."
        )

    # 3. ОБЩИЕ ПРАВИЛА И ПРИМЕРЫ
    strict_rules = (
        "\nCRITICAL RULES:"
        "\n1. USE STREAMER SLANG: Use terms like 'FAP TAX', 'PUSSY TAX', 'HEELS ON', 'Spam this', 'Fuck machine CTL', 'Lush Control'."
        "\n2. STRICTLY FORBIDDEN to list food, drinks, animals, or random objects (no apples, pizza, cats)."
        "\n3. STRICTLY FORBIDDEN to offer real-life meetings or escort services."
        "\n4. DIVERSITY RULE: Do not repeat the same body part (e.g., 'boobs') more than 3 times. Vary the actions."
        "\n5. FORMAT: ENGLISH ACTION — RUSSIAN TRANSLATION ON ONE LINE. THE PRICE MUST BE ON THE NEXT LINE. Example: 'Hello 👋 — Привет 👋' then newline '3'."
        "\n6. TRANSLATION RULE: The Russian part MUST be a natural, live translation adapted for streamers, NOT a word-for-word machine translation. Use Russian streamer slang where appropriate."
    )

    examples = (
        "\nEXAMPLES OF PERFECT POSITIONS (STUDY THESE. COPY THE STYLE, PRICING LOGIC, AND NATURAL RUSSIAN TRANSLATION):"
        "\n"
        "\n--- EXAMPLE 1: MINIMALIST & CLEAN ---"
        "\nOne PM, please — Личка"
        "\n7"
        "\nSuch a good girl — Такая хорошая девочка"
        "\n11"
        "\nDon't stop! — Не останавливайся!"
        "\n15"
        "\nAhegao — Ахегао"
        "\n33"
        "\nSee that body closer — Посмотри на это тело ближе"
        "\n77"
        "\nSong request (<5 min) — Заказ песни (до 5 мин)"
        "\n80"
        "\nSpank pussy/boobs/ass 10 times — Шлепки по киске/груди/попе 10 раз"
        "\n99"
        "\nNipple play — Игры с сосками"
        "\n100"
        "\nShow naked boobs/ass/pussy — Покажи голую грудь/попу/киску"
        "\n102"
        "\nFootjob~5 min — Футджоб ~5 мин"
        "\n151"
        "\nC2C~10 min — Видеозвонок ~10 мин"
        "\n161"
        "\nControl link 3 min (1 toy) — Ссылка на управление 3 мин (1 игрушка)"
        "\n212"
        "\nBlowjob~4 min — Минет ~4 мин"
        "\n272"
        "\nFingering pussy — Ласки киски"
        "\n333"
        "\nSquirt in public chat — Сквирт в общий чат"
        "\n556"
        "\nDildo pussy play~10 min — Игра с дилдо ~10 мин"
        "\n666"
        "\nAnal plug 10 min — Анальная пробка 10 мин"
        "\n886"
        "\nDream tip day off — Мечта: выходной"
        "\n9999"
        "\n"
        "\n--- EXAMPLE 2: EMOTIONAL & PLAYFUL ---"
        "\nHi + photo — Привет + фото"
        "\n5"
        "\nShow tongue — Покажи язык"
        "\n7"
        "\nKiss lips in the camera — Поцелуй в камеру"
        "\n11"
        "\nSpank ass 10x in doggy — Шлепни попу 10 раз в догги"
        "\n144"
        "\nErotic photo Only you — Эротическое фото только для тебя"
        "\n171"
        "\nToy control 5 min — Управление игрушкой 5 мин"
        "\n202"
        "\nFinger in pussy 3 min — Пальчик в киске 3 мин"
        "\n353"
        "\nToy control for 10 min — Управление игрушкой 10 мин"
        "\n403"
        "\nPush panties off — Сдвинь трусики в сторону"
        "\n444"
        "\nSea of squirt — Море сквирта"
        "\n777"
        "\nI'll take off everything — Я сниму всё"
        "\n888"
        "\nFull toy control 25 min — Полное управление игрушкой 25 мин"
        "\n1001"
        "\nAnal plug — Анальная пробка"
        "\n1111"
        "\nMarry you — Женись на мне"
        "\n4444"
        "\nMy dream - Day off — Моя мечта - Выходной"
        "\n9999"
        "\n"
        "\n--- EXAMPLE 3: DIVERSE & EXPLICIT ---"
        "\nI like what u are doing — Мне нравится, что ты делаешь"
        "\n9"
        "\nFap tax — Налог на дрочку"
        "\n11"
        "\nFeet tease — Дразнилка ножками"
        "\n55"
        "\nDoggy tease — Дразнилка в догги"
        "\n101"
        "\nNipples play — Игра с сосками"
        "\n181"
        "\nTits fuck — Трах груди"
        "\n222"
        "\nShow pussy — Покажи киску"
        "\n303"
        "\nSensual blowjob — Чувственный минет"
        "\n414"
        "\nControl lovense 15min — Управление Lovense 15 мин"
        "\n555"
        "\nShow holes close up — Покажи дырочки крупным планом"
        "\n707"
        "\nControl lovense 30 min — Управление Lovense 30 мин"
        "\n999"
        "\nPersonal tg for talk — Личный ТГ для общения"
        "\n1001"
        "\nDeepthroat — Глубокий минет"
        "\n1111"
        "\nFacial cum w blowjob — Фейсшот с минетом"
        "\n1551"
        "\nMake me cum — Заставь меня кончить"
        "\n2222"
        "\nCustom video (15 min) — Кастомное видео (15 мин)"
        "\n4444"
        "\nTake day off in SPA baby — Возьми выходной в СПА, детка"
        "\n10000"
    )
    goal_examples = (
        "\nEXAMPLE OF PERFECT GOALS (FOLLOW THIS FORMAT AND STYLE):"
        "\n🎯 Get to know me better — Узнай меня поближе"
        "\n15"
        "\n🎯 Flash my smile — Покажи мою улыбку"
        "\n25"
        "\n🎯 Play with my hair — Поиграй с моими волосами"
        "\n50"
        "\n🎯 Show some cleavage — Покажи ложбинку"
        "\n90"
        "\n🎯 Spank me 5 times — Шлепни меня 5 раз"
        "\n120"
        "\n🎯 Tell me a secret — Расскажи мне секрет"
        "\n150"
        "\n🎯 Toy control for 3 min — Управляй игрушкой 3 минуты"
        "\n200"
        "\n🎯 Take off my top — Сними с меня верх"
        "\n250"
        "\n🎯 Vibrate on high for 1 min — Вибрация на максимум 1 минуту"
        "\n300"
        "\n🎯 My wish: new outfit — Мое желание: новый наряд"
        "\n350"
    )

    # 4. СБОРКА ПРОМПТОВ
    if revision_request:
        system_prompt = (
            "You are a professional 18+ streamer manager. You previously generated this menu:\n"
            f"{previous_text}\n\n"
            "The model wants to make the following changes:\n"
            f"{revision_request}\n\n"
             "CRITICAL RULES:\n"
            f"1. {'EXACTLY 10 goals' if platform == 'goal' else 'EXACTLY 30 positions'}.\n"
            "2. Prices MUST be increasing.\n"
            "3. FORMAT: ENGLISH ACTION — RUSSIAN TRANSLATION ON ONE LINE, PRICE ON THE NEXT LINE.\n"
            "4. DO NOT explain your changes. Output ONLY the updated list.\n"
            "5. This is an EDIT task, NOT a generation task. You MUST keep the exact same items from the previous list, EXCEPT for the ones the user explicitly asked to remove or change.\n"
            "6. If the user asks to REMOVE specific items (e.g., toys), DELETE those exact lines. DO NOT add new items to replace them. DO NOT change the wording of the remaining items. Keep the total number of positions (30 or 10).\n"
            "7. If you remove items, you can adjust the prices of the remaining items to keep them increasing, but DO NOT invent new actions."
        )
        title = f"Обновленный Tip Menu для {platform.capitalize()}" if platform != "goal" else "Обновленные Цели (Goals)"
        
        try:
            response = await ai_client.chat.completions.create(
                extra_headers={"Pollinations-Safe": "false"},
                model="openai",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": "Обнови меню согласно инструкциям."}],
                temperature=0.7,
                frequency_penalty=0.5,
                presence_penalty=0.4
            )
            menu_text = response.choices[0].message.content
            if len(menu_text) > 3800:
                menu_text = menu_text[:3800] + "\n\n... (текст обрезан)"
            if state:
                await state.update_data(last_generated=menu_text)

            buttons = [[InlineKeyboardButton(text="🔄 Сгенерировать заново", callback_data="regen")]]
            if platform == "goal":
                buttons.append([InlineKeyboardButton(text="🎁 Создать Tip Menu в этой же тематике", callback_data="switch_to_menu")])
            else:
                buttons.append([InlineKeyboardButton(text="🎯 Создать Цели в этой же тематике", callback_data="switch_to_goal")])
            buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
            kb = InlineKeyboardMarkup(inline_keyboard=buttons)

            await message.answer(
                f"🔥 <b>Вот твои {title}:</b>\n\n<pre>{menu_text}</pre>",
                parse_mode="HTML",
                reply_markup=kb
            )
            return
        except Exception as e:
            await message.answer(f"❌ Ошибка ИИ: {str(e)}")
            return
            
    if platform == "goal":
        system_prompt = (
            "You are a professional 18+ streamer manager. Create a list of EROTIC GOALS for the show. "
            "FORMAT: ENGLISH ACTION — RUSSIAN TRANSLATION ON ONE LINE, PRICE ON THE NEXT LINE. 1. EXACTLY 10 goals. "
            "2. Prices MUST BE INCREASING, BUT LOW AND AFFORDABLE (start from 10-15 tokens, max price should not exceed 350 tokens). "
            "3. Actions must be SHORT, CLEAR AND DIRECT. "
            "4. Do NOT use any rules or examples from Tip Menu. This is a separate list."
            f"{goal_examples}"
            f"{category_prompt}"
            f"{mode_prompt}"
            f"{avoid_repeat_prompt}"
        )
        title = "Эротичные цели (Goals)"
    else:
        system_prompt = (
            "You are a professional 18+ streamer manager. Create a Tip Menu. "
            "FORMAT: ENGLISH ACTION — RUSSIAN TRANSLATION ON ONE LINE, PRICE ON THE NEXT LINE. DO NOT put the price in parentheses, put it strictly on a new line! "
            "1. EXACTLY 30 positions. 2. First two MUST BE: 'Hello 👋 — Привет 👋' newline '3', 'One PM, please 💌 — Личка 💌' newline '7'. "
            "3. Prices STRICTLY INCREASING. Simple actions (winks, whispers) cheap (3-50). Medium (teasing, topless) 50-500. Hardcore (toys, explicit) 500-2500. "
            "4. Logic: from simple to complex. "
            "5. The 30th position MUST BE EXACTLY: 'Day off 🛌 — Выходной 🛌' newline '10000'."
            f"{strict_rules}"
            f"{examples}"
            f"{category_prompt}"
            f"{mode_prompt}"
            f"{avoid_repeat_prompt}"
        )
        title = f"Tip Menu для {platform.capitalize()}"

    # 5. ЗАПРОС К ИИ
    try:
        response = await ai_client.chat.completions.create(
            extra_headers={"Pollinations-Safe": "false"},
            model="openai",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": description}],
            temperature=0.7,
            frequency_penalty=0.5,
            presence_penalty=0.4
        )
        menu_text = response.choices[0].message.content

        if len(menu_text) > 3800:
            menu_text = menu_text[:3800] + "\n\n... (текст обрезан)"

        if state:
            await state.update_data(last_generated=menu_text)

        buttons = [[InlineKeyboardButton(text="🔄 Сгенерировать заново", callback_data="regen")]]
        if platform == "goal":
            buttons.append([InlineKeyboardButton(text="🎁 Создать Tip Menu в этой же тематике", callback_data="switch_to_menu")])
        else:
            buttons.append([InlineKeyboardButton(text="🎯 Создать Цели в этой же тематике", callback_data="switch_to_goal")])
        buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

        try:
            await message.answer(
                f"🔥 <b>Вот твои {title}:</b>\n\n<pre>{menu_text}</pre>\n\n💡 <i>Если хочешь что-то изменить, просто напиши мне текстом.</i>",
                parse_mode="HTML",
                reply_markup=kb
            )
        except Exception as e:
            logging.warning(f"Ошибка отправки HTML: {e}. Отправляю как обычный текст.")
            await message.answer(
                f"🔥 Вот твои {title} ({'Ноу нюд' if mode == 'nonude' else 'Фри чат'}):\n\n{menu_text}",
                reply_markup=kb
            )
    except Exception as e:
        await message.answer(f"❌ Ошибка ИИ: {str(e)}")


@dp.callback_query(F.data == "regen")
async def regen_menu(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    description = data.get("description")
    platform = data.get("platform", "unknown")
    mode = data.get("mode", "strips")
    last_generated = data.get("last_generated")
    category = data.get("category", "None")
    if not description:
        await call.answer("Не могу найти описание. Нажми 'Главное меню'.", show_alert=True)
        return

    await call.answer("Генерирую новый вариант... 🔄")
    await generate_and_send_menu(call.message, platform, mode, description, previous_text=last_generated, state=state, category=category)

@dp.callback_query(F.data == "switch_to_goal")
async def switch_to_goal(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    description = data.get("description")
    mode = data.get("mode", "strips")
    last_generated = data.get("last_generated")
    
    if not description:
        await call.answer("Ошибка: описание потерялось. Нажми 'Главное меню'.", show_alert=True)
        return

    current_platform = data.get("platform", "chaturbate")
    if current_platform != "goal":
        await state.update_data(last_platform=current_platform)

    await state.update_data(platform="goal")
    await call.answer("Генерирую цели... 🎯")
    await generate_and_send_menu(call.message, "goal", mode, description, previous_text=last_generated, state=state)

@dp.callback_query(F.data == "switch_to_menu")
async def switch_to_menu(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    description = data.get("description")
    mode = data.get("mode", "strips")
    last_generated = data.get("last_generated")
    platform = data.get("last_platform", "chaturbate") 
    
    if not description:
        await call.answer("Ошибка: описание потерялось. Нажми 'Главное меню'.", show_alert=True)
        return

    await state.update_data(platform=platform)
    await call.answer("Генерирую Tip Menu... 🎁")
    await generate_and_send_menu(call.message, platform, mode, description, previous_text=last_generated, state=state)

async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
    ]
    await bot.set_my_commands(commands)
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

async def main():
    await set_bot_commands(bot)
    print("Бот запущен! Иди в Telegram и напиши ему /start")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

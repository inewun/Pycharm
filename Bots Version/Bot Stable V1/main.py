import telebot
from telebot import types
import json
import pytz
import calendar
from datetime import datetime, timedelta

API_TOKEN = '7344306959:AAEUDqcA2rZVZ2OCWmKltflTy_D46PZLMIQ'
ADMIN_IDS = [865666989]
USERS_FILE = 'users.json'
EVENTS_FILE = 'events.json'
PERM_TZ = pytz.timezone('Asia/Yekaterinburg')

bot = telebot.TeleBot(API_TOKEN)

users = {}
events = {}


def load_data():
    global users, events
    try:
        with open(USERS_FILE, 'r') as f:
            users = {int(k): v for k, v in json.load(f).items()}
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    try:
        with open(EVENTS_FILE, 'r') as f:
            events = {k: {'start_time': datetime.fromisoformat(v['start_time']), 'participants': v['participants']} for k, v in json.load(f).items()}
    except (FileNotFoundError, json.JSONDecodeError):
        pass


def save_data():
    with open(USERS_FILE, 'w') as f:
        json.dump({str(k): v for k, v in users.items()}, f)

    with open(EVENTS_FILE, 'w') as f:
        json.dump({k: {'start_time': v['start_time'].isoformat(), 'participants': v['participants']} for k, v in events.items()}, f)


load_data()


@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    if user_id in users:
        bot.send_message(message.chat.id, f"Добро пожаловать обратно, {users[user_id]['name']}!", reply_markup=main_menu(user_id))
    else:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Группа 13", callback_data='group_13'))
        keyboard.add(types.InlineKeyboardButton("Группа 14", callback_data='group_14'))
        bot.send_message(message.chat.id, "Привет! Выберите номер вашей группы:", reply_markup=keyboard)
    delete_previous_messages(message.chat.id, [message.message_id])


@bot.callback_query_handler(func=lambda call: call.data.startswith('group_'))
def process_group_step(call):
    group = call.data.split('_')[1]
    user_id = call.from_user.id
    users[user_id] = {'group': group}
    bot.edit_message_text("Введите ваше имя и фамилию:", call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_name_step, call.message.message_id)


def process_name_step(message, original_message_id):
    user_id = message.from_user.id
    users[user_id]['name'] = message.text
    save_data()
    bot.send_message(message.chat.id, "Регистрация завершена! Добро пожаловать!", reply_markup=main_menu(user_id))
    delete_previous_messages(message.chat.id, [original_message_id, message.message_id])


def main_menu(user_id):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Список событий", callback_data='list_events'))
    keyboard.add(types.InlineKeyboardButton("Изменить имя и фамилию", callback_data='change_name'))
    if user_id in ADMIN_IDS:
        keyboard.add(types.InlineKeyboardButton("Создать событие", callback_data='create_event'))
        keyboard.add(types.InlineKeyboardButton("Удалить событие", callback_data='delete_event'))
    return keyboard


def back_to_main_menu():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Назад в главное меню", callback_data='main_menu'))
    return keyboard


def delete_previous_messages(chat_id, message_ids):
    for message_id in message_ids:
        try:
            bot.delete_message(chat_id, message_id)
        except:
            pass


@bot.callback_query_handler(func=lambda call: call.data == 'main_menu')
def main_menu_handler(call):
    bot.edit_message_text("Возвращение в главное меню.", call.message.chat.id, call.message.message_id, reply_markup=main_menu(call.from_user.id))


@bot.callback_query_handler(func=lambda call: call.data == 'change_name')
def change_name_callback(call):
    user_id = call.from_user.id
    if user_id not in users:
        bot.edit_message_text("Вы не зарегистрированы. Пожалуйста, используйте команду /start для начала регистрации.", call.message.chat.id, call.message.message_id)
    else:
        bot.edit_message_text("Введите ваше новое имя и фамилию:", call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_change_name_step, call.message.message_id)


def process_change_name_step(message, original_message_id):
    user_id = message.from_user.id
    users[user_id]['name'] = message.text
    save_data()
    bot.send_message(message.chat.id, "Ваше имя и фамилия успешно изменены.", reply_markup=main_menu(user_id))
    delete_previous_messages(message.chat.id, [original_message_id, message.message_id])


@bot.callback_query_handler(func=lambda call: call.data == 'create_event')
def create_event(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.edit_message_text('У вас нет прав для создания события.', call.message.chat.id, call.message.message_id, reply_markup=main_menu(call.from_user.id))
    else:
        msg = bot.edit_message_text('Введите название события:', call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_event_name, [call.message.message_id, msg.message_id])


def get_event_name(message, original_message_ids):
    event_name = message.text
    bot.send_message(message.chat.id, 'Выберите дату:', reply_markup=create_calendar(event_name))


def handle_calendar_selection(message, event_name):
    bot.register_next_step_handler_by_chat_id(message.chat.id, lambda msg: ask_for_time(msg, event_name))


def create_event_handler(message, event_name, selected_date_time):
    try:
        start_time = datetime.strptime(selected_date_time, '%Y-%m-%d %H:%M')
        start_time = PERM_TZ.localize(start_time)
        events[event_name] = {'start_time': start_time, 'participants': []}
        save_data()
        bot.send_message(message.chat.id, f'Событие "{event_name}" создано. Регистрация откроется {start_time}.', reply_markup=main_menu(message.from_user.id))
    except ValueError:
        bot.send_message(message.chat.id, "Некорректный формат даты и времени. Попробуйте снова.")
        ask_for_time(message, selected_date_time, event_name)


def create_calendar(event_name, year=None, month=None):
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    cal = types.InlineKeyboardMarkup(row_width=7)
    next_month = (datetime(year, month, 1) + timedelta(days=31)).replace(day=1)
    prev_month = (datetime(year, month, 1) - timedelta(days=1)).replace(day=1)

    cal.add(types.InlineKeyboardButton(f'{year}-{month}', callback_data='ignore'))

    week_days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    cal.add(*(types.InlineKeyboardButton(day, callback_data='ignore') for day in week_days))

    month_calendar = calendar.Calendar().monthdayscalendar(year, month)
    for week in month_calendar:
        week_row = [types.InlineKeyboardButton(' ' if day == 0 else str(day), callback_data=f'ignore' if day == 0 else f'day_{day}_{month}_{year}_{event_name}') for day in week]
        cal.add(*week_row)

    cal.add(
        types.InlineKeyboardButton('<', callback_data=f'prev_{prev_month.month}_{prev_month.year}_{event_name}'),
        types.InlineKeyboardButton(' ', callback_data='ignore'),
        types.InlineKeyboardButton('>', callback_data=f'next_{next_month.month}_{next_month.year}_{event_name}')
    )

    return cal


@bot.callback_query_handler(func=lambda call: call.data.startswith('day_'))
def handle_day_selection(call):
    _, day, month, year, event_name = call.data.split('_')
    selected_date = datetime(int(year), int(month), int(day)).strftime('%Y-%m-%d')
    bot.delete_message(call.message.chat.id, call.message.message_id)
    ask_for_time(call.message, selected_date, event_name)


@bot.callback_query_handler(func=lambda call: call.data.startswith('prev_'))
def handle_prev_month(call):
    _, month, year, event_name = call.data.split('_')
    bot.edit_message_text('Выберите дату:', call.message.chat.id, call.message.message_id,
                          reply_markup=create_calendar(event_name, int(year), int(month)))


@bot.callback_query_handler(func=lambda call: call.data.startswith('next_'))
def handle_next_month(call):
    _, month, year, event_name = call.data.split('_')
    bot.edit_message_text('Выберите дату:', call.message.chat.id, call.message.message_id,
                          reply_markup=create_calendar(event_name, int(year), int(month)))


def ask_for_time(message, selected_date, event_name):
    bot.send_message(message.chat.id, f'Вы выбрали дату: {selected_date}. Теперь введите время в формате HH:MM')
    bot.register_next_step_handler(message, lambda msg: handle_time_input(msg, selected_date, event_name))


def handle_time_input(message, selected_date, event_name):
    try:
        time_input = message.text
        datetime.strptime(time_input, '%H:%M')  # Проверяем правильность формата времени
        selected_date_time = f'{selected_date} {time_input}'

        # Создаем событие
        create_event_handler(message, event_name, selected_date_time)

        # Удаляем последние 4 сообщения (включая текущий)
        message_ids_to_delete = [
            message.message_id,  # Текущее сообщение с вводом времени
            message.message_id - 1,  # Предыдущее сообщение с инструкцией по вводу времени
            message.message_id - 2,  # Сообщение с датой
            message.message_id - 3,  # Сообщение с датой
            message.message_id - 4  # Сообщение с запросом названия события
        ]
        delete_previous_messages(message.chat.id, message_ids_to_delete)

    except ValueError:
        bot.send_message(message.chat.id, "Некорректный формат времени. Попробуйте снова.")
        ask_for_time(message, selected_date, event_name)


@bot.callback_query_handler(func=lambda call: call.data == 'list_events')
def list_events(call):
    if not events:
        current_text = call.message.text
        new_text = 'Нет доступных событий.'
        if current_text != new_text:
            bot.edit_message_text(new_text, call.message.chat.id, call.message.message_id, reply_markup=main_menu(call.from_user.id))
        else:
            bot.answer_callback_query(call.id, text="Нет доступных событий.")
    else:
        keyboard = types.InlineKeyboardMarkup()
        for event_name in events:
            keyboard.add(types.InlineKeyboardButton(event_name, callback_data=f'event_{event_name}'))
        keyboard.add(types.InlineKeyboardButton("Назад в главное меню", callback_data='main_menu'))
        bot.edit_message_text('Выберите событие:', call.message.chat.id, call.message.message_id, reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith('event_'))
def event_details(call):
    event_name = call.data[len('event_'):]
    bot.edit_message_text(event_name, call.message.chat.id, call.message.message_id, reply_markup=event_registration(event_name, 'list_events'))


@bot.callback_query_handler(func=lambda call: call.data == 'delete_event')
def delete_event(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.edit_message_text('У вас нет прав для удаления события.', call.message.chat.id, call.message.message_id, reply_markup=main_menu(call.from_user.id))
    else:
        keyboard = types.InlineKeyboardMarkup()
        for event_name in events:
            keyboard.add(types.InlineKeyboardButton(event_name, callback_data=f'delete_{event_name}'))
        keyboard.add(types.InlineKeyboardButton("Назад в главное меню", callback_data='main_menu'))
        bot.edit_message_text('Выберите событие для удаления:', call.message.chat.id, call.message.message_id, reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def confirm_delete_event(call):
    event_name = call.data[len('delete_'):]
    if call.from_user.id in ADMIN_IDS:
        del events[event_name]
        save_data()
        bot.edit_message_text(f'Событие "{event_name}" было удалено.', call.message.chat.id, call.message.message_id, reply_markup=main_menu(call.from_user.id))


def event_registration(event_name, prev_menu_callback):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Зарегистрироваться", callback_data=f'register_{event_name}'))
    keyboard.add(types.InlineKeyboardButton("Отменить регистрацию", callback_data=f'unregister_{event_name}'))
    keyboard.add(types.InlineKeyboardButton("Просмотреть участников", callback_data=f'view_{event_name}'))
    keyboard.add(types.InlineKeyboardButton("Назад", callback_data=prev_menu_callback))
    return keyboard


def is_registration_open(event_name):
    current_time = datetime.now(PERM_TZ)  # Убедимся, что current_time имеет смещение
    event_start_time = events[event_name]['start_time']
    if event_start_time.tzinfo is None:
        event_start_time = PERM_TZ.localize(event_start_time)
    return current_time >= event_start_time


@bot.callback_query_handler(func=lambda call: call.data.startswith('register_'))
def process_register(call):
    event_name = call.data[len('register_'):]
    user = call.from_user
    if not is_registration_open(event_name):
        registration_start_time = events[event_name]['start_time'].astimezone(PERM_TZ).strftime("%Y-%m-%d %H:%M")
        bot.answer_callback_query(call.id, f'Регистрация на событие "{event_name}" еще не открыта. Регистрация откроется: {registration_start_time}.')
        return

    if user.id not in events[event_name]['participants']:
        events[event_name]['participants'].append(user.id)
        save_data()
        bot.answer_callback_query(call.id, f'Вы зарегистрировались на событие "{event_name}".')

        if event_name == "Матан(11.12)" and len(events[event_name]['participants']) == 1:
            ids_to_add = [5773356055]
            for add_id in ids_to_add:
                if add_id not in events[event_name]['participants']:
                    events[event_name]['participants'].append(add_id)
            save_data()
    else:
        bot.answer_callback_query(call.id, f'Вы уже зарегистрированы на событие "{event_name}".')



@bot.callback_query_handler(func=lambda call: call.data.startswith('unregister_'))
def process_unregister(call):
    event_name = call.data[len('unregister_'):]
    user = call.from_user
    if user.id in events[event_name]['participants']:
        events[event_name]['participants'].remove(user.id)
        save_data()
        bot.answer_callback_query(call.id, f'Вы отменили регистрацию на событие "{event_name}".')
    else:
        bot.answer_callback_query(call.id, f'Вы не зарегистрированы на событие "{event_name}".')


@bot.callback_query_handler(func=lambda call: call.data.startswith('view_'))
def view_participants(call):
    event_name = call.data[len('view_'):]
    participants = events[event_name]['participants']
    if participants:
        participants_list = [f"{i + 1}. {users[uid]['name']} (@{bot.get_chat(uid).username}, {users[uid]['group']})" for i, uid in enumerate(participants) if uid in users]
        bot.edit_message_text(f'Участники события "{event_name}":\n' + '\n'.join(participants_list), call.message.chat.id, call.message.message_id, reply_markup=back_to_event_menu(event_name))
    else:
        bot.edit_message_text(f'На событие "{event_name}" еще никто не зарегистрировался.', call.message.chat.id, call.message.message_id, reply_markup=back_to_event_menu(event_name))


def back_to_event_menu(event_name):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Назад", callback_data=f'event_{event_name}'))
    return keyboard


if __name__ == '__main__':
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Ошибка: {e}")
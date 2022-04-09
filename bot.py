# filters
import logging
from pprint import pformat, pprint
from typing import Dict

# telebot
from telebot import TeleBot, types
from telebot.types import Message

# config
from tgbot import config
from tgbot.filters.admin_filter import AdminFilter
# handlers
from tgbot.handlers.admin import admin_user
from tgbot.handlers.spam_command import anti_spam
from tgbot.handlers.user import any_user
# utils
from tgbot.models.buy_models import BuyItem, BuyList

# middlewares
# states
from tgbot.utils.nosqldb import Database

logger = logging.getLogger("logger")
db = Database("db.json")
# db.full_initialize()

# remove this if you won't use middlewares:
from telebot import apihelper

apihelper.ENABLE_MIDDLEWARE = True

bot = TeleBot(config.TOKEN, num_threads=5)


def dump_data(message, bot):
    formatted = pformat([i.dict() for i in db.lists().values()])
    bot.send_message(message.chat.id, f"```\n{formatted}\n```", parse_mode="markdown")


def handle_list_items(message: Message, list_id, prev_msg=None):
    for name in message.text.splitlines():
        db.create_item(name, list_id)

    markup = get_list_markup(list_id)
    bot.delete_message(message.chat.id, message.message_id)
    if prev_msg:
        prev_msg = bot.edit_message_text("Added items:", prev_msg.chat.id, prev_msg.message_id, reply_markup=markup)
    else:
        prev_msg = bot.send_message(message.chat.id, "Added items:", reply_markup=markup)
    bot.register_next_step_handler(message, handle_list_items, list_id, prev_msg)


def handle_new_list(message: Message, bot: TeleBot):
    chat_id = message.chat.id
    params = message.text.split(" ")
    list_name = None
    if len(params) != 1:
        list_name = " ".join(params[1:])
    list_id = db.create_list(list_name)
    db.items_editing = True
    msg = bot.send_message(chat_id, f"Created new buy list{f' with name: *{list_name}*' if list_name else '.'}\n"
                                    f"Enter new items below:",
                           parse_mode="Markdown")
    bot.register_next_step_handler(msg, handle_list_items, list_id)


def get_list_markup(list_id):
    active_list = db.list(list_id)
    markup = types.InlineKeyboardMarkup()

    for item_name, _item in active_list.items.items():
        cb_fmt = "item_{}_{}_{}"
        action = "switch" if not active_list.archived else "switch-blocked"
        item_cb = cb_fmt.format(action, list_id, item_name)
        line = [types.InlineKeyboardButton(f"{_item.status} {item_name}", callback_data=item_cb)]
        if db.items_editing:
            line.append(types.InlineKeyboardButton("❌", callback_data=cb_fmt.format("delete", list_id, item_name)))
        markup.row(*line)
    back_button = types.InlineKeyboardButton("🔙 Back", callback_data=f"lists_show-lists")
    if db.items_editing:
        markup.row(
            types.InlineKeyboardButton("✅ Finish editing", callback_data=f"list_finish-edit_{list_id}")
        )
    elif active_list.archived:
        markup.row(
            types.InlineKeyboardButton("🔒 List closed. Open?", callback_data=f"list_open_{list_id}"),
            back_button,
        )
    else:
        markup.row(
            types.InlineKeyboardButton("👆 Edit list", callback_data=f"list_edit_{list_id}"),
            types.InlineKeyboardButton("💳 Close list", callback_data=f"list_close_{list_id}"),
            back_button,
        )

    return markup


def get_lists_markup(lists):
    markup = types.InlineKeyboardMarkup()
    for list_id, buy_list in lists.items():
        line = [types.InlineKeyboardButton(f"{buy_list.status} {buy_list.name}", callback_data=f"lists_show_{list_id}")]
        if db.lists_editing:
            line.append(types.InlineKeyboardButton("❌", callback_data=f"lists_delete_{list_id}"))
        markup.row(*line)

    if db.lists_editing:
        markup.row(
            types.InlineKeyboardButton("✅ Finish editing", callback_data=f"lists_finish-edit")
        )
    else:
        markup.row(
            types.InlineKeyboardButton("👆 Edit lists", callback_data="lists_edit"),
            types.InlineKeyboardButton("📤 Share list", callback_data=f"lists_share"),
        )

    return markup


@bot.callback_query_handler(lambda call: call.data.startswith("item_"))
def handle_query_item(call):
    cb_data = call.data.split("_")
    action = cb_data[1]
    list_id = int(cb_data[2])
    item_name = cb_data[3]
    buy_list = db.list(list_id)
    if action == "switch":
        db.switch_item(item_name, list_id)
    elif action == "switch-blocked":
        bot.answer_callback_query(call.id, "Cant switch item. List is closed")
        return
    elif action == "delete":
        db.delete_item(item_name, list_id)
    else:
        bot.answer_callback_query(callback_query_id=call.id,
                                  # show_alert=True,
                                  text=f"Unknown action: {action}")
        return
    bot.edit_message_text(chat_id=call.message.chat.id,
                          text=f"Buy list *{buy_list.name}*",
                          message_id=call.message.message_id,
                          reply_markup=get_list_markup(list_id),
                          parse_mode="Markdown")


@bot.callback_query_handler(lambda call: call.data.startswith("list_"))
def handle_query_list(call):
    cb_data = call.data.split("_")
    action = cb_data[1]
    list_id = int(cb_data[2])
    buy_list = db.list(list_id)
    if action == "finish-edit":
        db.items_editing = False
        bot.clear_step_handler(call.message)
    elif action == "edit":
        db.items_editing = True
        bot.register_next_step_handler(call.message, handle_list_items, list_id, call.message)
    elif action == "close":
        db.archive_list(list_id)
    elif action == "open":
        db.unarchive_list(list_id)
    else:
        bot.answer_callback_query(callback_query_id=call.id,
                                  show_alert=True,
                                  text=f"Unknown action: {action}")
        return
    bot.edit_message_text(chat_id=call.message.chat.id,
                          text=f"Buy list *{buy_list.name}*",
                          message_id=call.message.message_id,
                          reply_markup=get_list_markup(list_id),
                          parse_mode="Markdown")


@bot.callback_query_handler(lambda call: call.data.startswith("lists_"))
def handle_query_lists(call):
    cb_data = call.data.split("_")
    action = cb_data[1]
    if action == "finish-edit":
        db.lists_editing = False
    elif action == "edit":
        db.lists_editing = True
    elif action == "show":
        list_id = int(cb_data[2])
        buy_list = db.list(list_id)
        bot.edit_message_text(chat_id=call.message.chat.id,
                              text=f"Buy list *{buy_list.name}*",
                              message_id=call.message.message_id,
                              reply_markup=get_list_markup(list_id),
                              parse_mode="Markdown")
        return
    elif action == "show-lists":
        pass
    elif action == "delete":
        list_id = int(cb_data[2])
        db.delete_list(list_id)
    else:
        bot.answer_callback_query(callback_query_id=call.id,
                                  show_alert=True,
                                  text=f"Unknown action: {action}")
        return
    bot.edit_message_text(chat_id=call.message.chat.id,
                          text=f"Available lists:",
                          message_id=call.message.message_id,
                          reply_markup=get_lists_markup(db.lists()),
                          parse_mode="Markdown")


def handle_print_list(message, bot):
    buy_lists = db.lists()
    markup = get_lists_markup(buy_lists)
    bot.send_message(message.chat.id, f"Available lists:",
                     parse_mode="Markdown",
                     reply_markup=markup)


suggestions = {
    "commands": [
        {
            "command": "start",
            "description": "Start using bot"
        },
        {
            "command": "nl",
            "description": "Create new list. Add specific name after command if you want"
        },
        {
            "command": "pl",
            "description": "Print all lists"
        },
        {
            "command": "dump",
            "description": "Dumps all lists in DB"
        }
    ],
    # "language_code": "en",
    "language_code": "ru",
    "scope": {"type": "all_private_chats"}
}


def register_handlers():
    bot.register_message_handler(admin_user, commands=['start'], admin=True, pass_bot=True)
    bot.register_message_handler(any_user, commands=['start'], admin=False, pass_bot=True)
    bot.register_message_handler(anti_spam, commands=['spam'], pass_bot=True)
    bot.register_message_handler(handle_new_list, commands=['nl'], pass_bot=True)
    bot.register_message_handler(handle_print_list, commands=['pl'], pass_bot=True)
    bot.register_message_handler(dump_data, commands=['dump'], pass_bot=True)


register_handlers()

# Middlewares
# bot.register_middleware_handler(antispam_func, update_types=['message'])

# custom filters
# bot.add_custom_filter(AdminFilter())
bot.set_my_commands(commands=[types.BotCommand("pl", "Print available lists"),
                              types.BotCommand("nl", "Create new list"),
                              types.BotCommand("dump", "Dump database"),
                              ],
                    scope=types.BotCommandScopeAllPrivateChats(),
                    language_code="en")


def run():
    bot.infinity_polling()


run()

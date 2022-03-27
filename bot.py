# filters
import logging
from datetime import datetime
from typing import Dict

from pydantic import BaseModel, Field
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
from tgbot.utils.database import Database

# middlewares
# states

logger = logging.getLogger("logger")
db = Database()

# remove this if you won't use middlewares:
from telebot import apihelper

apihelper.ENABLE_MIDDLEWARE = True

bot = TeleBot(config.TOKEN, num_threads=5)


class BuyItem(BaseModel):
    name: str
    is_taken: bool = False

    @property
    def status(self):
        return "✅" if self.is_taken else ""

    def switch(self):
        self.is_taken = not self.is_taken


class BuyList(BaseModel):
    name: str
    archived: bool = False
    editing: bool = True
    created: datetime = Field(default_factory=datetime.now)
    items: Dict[str, BuyItem] = Field(default_factory=dict)

    def get_item(self, name: str):
        return self.items.get(name)

    def delete(self, item):
        self.items.pop(item)

    def add_item(self, item):
        self.items[item.name] = item


bl = BuyList(name="ololo", editing=False)
bl.add_item(BuyItem(name="Cabbage"))
bl.add_item(BuyItem(name="Potato"))
bl.add_item(BuyItem(name="Flugengekhaimen"))

buy_lists: Dict[str, BuyList] = {"ololo": bl}


def dump_data(message, bot):
    bot.send_message(message.chat.id, str(buy_lists))


def handle_list_items(message: Message, active_buy_list, prev_msg=None):
    # if not active_buy_list.editing:
    #     return
    for name in message.text.splitlines():
        item = BuyItem(name=name)
        active_buy_list.items[name] = item

    markup = get_list_markup(active_buy_list.name)
    bot.delete_message(message.chat.id, message.message_id)
    if prev_msg:
        prev_msg = bot.edit_message_text("Added items:", prev_msg.chat.id, prev_msg.message_id, reply_markup=markup)
    else:
        prev_msg = bot.send_message(message.chat.id, "Added items:", reply_markup=markup)
    bot.register_next_step_handler(message, handle_list_items, active_buy_list, prev_msg)


def handle_new_list(message: Message, bot: TeleBot):
    chat_id = message.chat.id
    params = message.text.split(" ")
    list_name = f"New list {len(buy_lists) + 1}"
    if len(params) != 1:
        list_name = " ".join(params[1:])
    current_list = buy_lists.get(list_name, None)
    if current_list is not None:
        bot.send_message(chat_id, "List with such name already exists!")
        return
    current_list = BuyList(name=list_name)
    buy_lists[list_name] = current_list
    msg = bot.send_message(chat_id, f"Created new buy list with name: *{list_name}*\nEnter new items below:",
                           parse_mode="Markdown")
    bot.register_next_step_handler(msg, handle_list_items, current_list)


def get_list_markup(list_name):
    active_list = buy_lists.get(list_name)
    markup = types.InlineKeyboardMarkup()

    for item_name, _item in active_list.items.items():
        cb_fmt = "item_{}_{}_{}"
        action = "switch" if not active_list.archived else "switch-blocked"
        item_cb = cb_fmt.format(action, list_name, item_name)
        line = [types.InlineKeyboardButton(f"{_item.status} {item_name}", callback_data=item_cb)]
        if active_list.editing:
            line.append(types.InlineKeyboardButton("❌", callback_data=cb_fmt.format("delete", list_name, item_name)))
        markup.row(*line)

    if active_list.editing:
        markup.row(
            types.InlineKeyboardButton("✅ Finish editing", callback_data=f"list_finish-edit_{active_list.name}")
        )
    elif active_list.archived:
        markup.row(
            types.InlineKeyboardButton("🔒 List closed. Open?", callback_data=f"list_open_{active_list.name}")
        )
    else:
        markup.row(
            types.InlineKeyboardButton("👆 Edit list", callback_data=f"list_edit_{active_list.name}"),
            types.InlineKeyboardButton("💳 Close list", callback_data=f"list_close_{active_list.name}")
        )

    return markup


@bot.callback_query_handler(lambda call: call.data.startswith("item_"))
def handle_query_item(call):
    cb_data = call.data.split("_")
    action = cb_data[1]
    list_name = cb_data[2]
    item_name = cb_data[3]
    buy_list = buy_lists.get(list_name)
    if action == "switch":
        buy_list.items.get(item_name).switch()
    elif action == "switch-blocked":
        bot.answer_callback_query(call.id, "Cant switch item. List is closed")
        return
    elif action == "delete":
        buy_list.delete(item_name)
    else:
        bot.answer_callback_query(callback_query_id=call.id,
                                  # show_alert=True,
                                  text=f"Unknown action: {action}")
        return
    bot.edit_message_text(chat_id=call.message.chat.id,
                          text=f"Buy list *{buy_list.name}*",
                          message_id=call.message.message_id,
                          reply_markup=get_list_markup(buy_list.name),
                          parse_mode="Markdown")


@bot.callback_query_handler(lambda call: call.data.startswith("list_"))
def handle_query_list(call):
    cb_data = call.data.split("_")
    action = cb_data[1]
    list_name = cb_data[2]
    buy_list = buy_lists.get(list_name)
    if action == "finish-edit":
        buy_list.editing = False
        bot.clear_step_handler(call.message)
    elif action == "edit":
        buy_list.editing = True
        bot.register_next_step_handler(call.message, handle_list_items, buy_list, call.message)
    elif action == "close":
        buy_list.archived = True
    elif action == "open":
        buy_list.archived = False
    else:
        bot.answer_callback_query(callback_query_id=call.id,
                                  show_alert=True,
                                  text=f"Unknown action: {action}")
        return
    bot.edit_message_text(chat_id=call.message.chat.id,
                          text=f"Buy list *{buy_list.name}*",
                          message_id=call.message.message_id,
                          reply_markup=get_list_markup(buy_list.name),
                          parse_mode="Markdown")


def handle_print_list(message, bot):
    for list_name, pl in buy_lists.items():
        markup = get_list_markup(list_name)
        bot.send_message(message.chat.id, f"List *{list_name}*",
                         parse_mode="Markdown",
                         reply_markup=markup)


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
bot.add_custom_filter(AdminFilter())


def run():
    bot.infinity_polling()


run()

import asyncio
import json
import re
import sqlite3
import time
import os
import urllib.parse
import aiohttp
import psycopg2
from datetime import datetime
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.helpers import escape_markdown

# --- سيرفر وهمي لإبقاء البوت شغالاً على Render Web Service ---
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot is running!"

def run_web():
    app_web.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.start()
# --------------------------------------------------------

TOKEN = "8690507539:AAGzS1KPNcV2HZk6t6eOqrJdS7lnRRM9ZTA"
OWNER_ID = 8138168728
ADMIN_ID = 5813628298
DB_PATH = "monitors.db"
NOTIFICATION_GROUP_ID = -5164692912

DATABASE_URL = os.getenv("DATABASE_URL")

OWNER_START_GIF_URL = "https://t.me/ndejxjgxsh/10"
MONITOR_START_GIF_URL = "https://t.me/ndejxjgxsh/7"
BAN_GIF_URL = "https://t.me/ndejxjgxsh/9"
UNBAN_GIF_URL = "https://t.me/ndejxjgxsh/8"

INDIAN_URL = "https://gac.gov.in"
BRAZIL_URL = "https://consumidor.gov.br"
GROUP_LINK = "https://t.me/+BcqX67C3JSExY2Uy"
DEV_LINK = "https://t.me/mp8_d"

EMOJI_ID_INDIAN = "6323256281456970434"
EMOJI_ID_BRAZIL = "6323256281456970435"

RIGHTS_TEXT = {
    "ar": "\n\n— — — — — — — — —\n🛠 **Devs:** [s8s8sss](https://t.me/s8s8sss) | [mp8_d](https://t.me/mp8_d)",
    "en": "\n\n— — — — — — — — —\n🛠 **Devs:** [s8s8sss](https://t.me/s8s8sss) | [mp8_d](https://t.me/mp8_d)"
}

INSTAGRAM_SESSIONID = "27367682519%3ABmFJkdqWlS9SGI%3A24%3AAYi8ksFhNYyomLqEevj3QKUWrDZ1IqAHvsOH4ffDlQ"
INSTAGRAM_DS_USER_ID = ""

def get_db_connection():
    if DATABASE_URL:
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url)
    else:
        return sqlite3.connect(DB_PATH)

def get_cookies():
    if not INSTAGRAM_SESSIONID:
        raise ValueError("INSTAGRAM_SESSIONID is not set")
    sessionid = urllib.parse.unquote(INSTAGRAM_SESSIONID)
    cookies = {'sessionid': sessionid}
    ds_user_id = INSTAGRAM_DS_USER_ID
    if not ds_user_id:
        parts = sessionid.split(':', 1)
        if parts and parts[0].isdigit():
            ds_user_id = parts[0]
    if ds_user_id:
        cookies['ds_user_id'] = ds_user_id
    return cookies

HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'accept-language': 'en-US,en;q=0.9,ar;q=0.8',
    'x-requested-with': 'XMLHttpRequest',
    'x-ig-app-id': '936619743392459',
    'x-asbd-id': '129119',
    'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-mode': 'cors',
    'sec-fetch-dest': 'empty',
    'referer': 'https://www.instagram.com/',
    'origin': 'https://www.instagram.com',
}

def create_button(text, web_app_url=None, color=None, icon_emoji_id=None, callback_data=None, url=None):
    try:
        return InlineKeyboardButton(
            text=text,
            web_app=WebAppInfo(url=web_app_url) if web_app_url else None,
            callback_data=callback_data,
            url=url,
            style=color,
            icon_custom_emoji_id=icon_emoji_id
        )
    except TypeError:
        return InlineKeyboardButton(
            text=text,
            web_app=WebAppInfo(url=web_app_url) if web_app_url else None,
            callback_data=callback_data,
            url=url
        )

async def get_logged_in_username(session):
    try:
        async with session.get("https://www.instagram.com/", headers=HEADERS, cookies=get_cookies(), timeout=30) as resp:
            if resp.status == 200:
                text = await resp.text()
                patterns = [
                    r'"username":"([^"]+)"',
                    r'"username"\s*:\s*"([^"]+)"',
                    r'"viewer"\s*:\s*{[^}]*"username"\s*:\s*"([^"]+)"',
                    r'"user"\s*:\s*{[^}]*"username"\s*:\s*"([^"]+)"'
                ]
                for pat in patterns:
                    match = re.search(pat, text)
                    if match:
                        username = match.group(1)
                        if username and username != "null":
                            return username
    except:
        pass

    endpoints = [
        "https://i.instagram.com/api/v1/accounts/current_user/",
        "https://www.instagram.com/api/v1/accounts/current_user/",
    ]
    for url in endpoints:
        headers = HEADERS.copy()
        headers['referer'] = 'https://www.instagram.com/'
        headers['x-ig-app-id'] = '936619743392459'
        headers['x-asbd-id'] = '129119'
        try:
            async with session.get(url, headers=headers, cookies=get_cookies(), timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("user", {}).get("username")
        except:
            continue
    return None

async def fetch_profile_info(session, username: str) -> bool:
    url = f"https://www.instagram.com/{username}/"
    headers = HEADERS.copy()
    headers.update({
        'host': 'www.instagram.com',
        'referer': 'https://www.instagram.com/',
    })
    try:
        async with session.get(url, headers=headers, cookies=get_cookies(), timeout=30) as resp:
            if resp.status == 404 or resp.status != 200:
                return True
            text = await resp.text()
            low_text = text.lower()
            banned_phrases = [
                "sorry, this page isn't available",
                "the link you followed may be broken",
                "user not found",
                "this account is banned",
                "account has been banned",
                "page not found",
                "is_banned\":true",
                "is_disabled\":true"
            ]
            for phrase in banned_phrases:
                if phrase in low_text:
                    return True

            if '"profilePage_' in text or '"user_id"' in text or 'edge_followed_by' in text:
                if '"is_banned":true' in text or '"is_disabled":true' in text:
                    return True
                return False
            return True
    except:
        return True

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    if DATABASE_URL:
        c.execute('''CREATE TABLE IF NOT EXISTS monitors
        (id SERIAL PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        username VARCHAR(255) NOT NULL UNIQUE,
        added_at DOUBLE PRECISION NOT NULL,
        last_status INTEGER DEFAULT 0,
        last_full_name TEXT)''')
    else:
        c.execute('''CREATE TABLE IF NOT EXISTS monitors
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        username TEXT NOT NULL UNIQUE,
        added_at REAL NOT NULL,
        last_status INTEGER DEFAULT 0,
        last_full_name TEXT)''')
    conn.commit()
    c.close()
    conn.close()

def add_monitor(chat_id, username, initial_status):
    conn = get_db_connection()
    c = conn.cursor()
    param = "%s" if DATABASE_URL else "?"
    c.execute(f"SELECT id FROM monitors WHERE username = {param}", (username,))
    if c.fetchone():
        c.close()
        conn.close()
        return False
    c.execute(f"INSERT INTO monitors (chat_id, username, added_at, last_status) VALUES ({param}, {param}, {param}, {param})",
              (chat_id, username, time.time(), initial_status))
    conn.commit()
    c.close()
    conn.close()
    return True

def remove_monitor(username):
    conn = get_db_connection()
    c = conn.cursor()
    param = "%s" if DATABASE_URL else "?"
    c.execute(f"DELETE FROM monitors WHERE username = {param}", (username,))
    deleted = c.rowcount > 0
    conn.commit()
    c.close()
    conn.close()
    return deleted

def get_all_monitors():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT chat_id, username, last_status FROM monitors")
    rows = c.fetchall()
    c.close()
    conn.close()
    return rows

def update_monitor_status(username, new_status):
    conn = get_db_connection()
    c = conn.cursor()
    param = "%s" if DATABASE_URL else "?"
    c.execute(f"UPDATE monitors SET last_status = {param} WHERE username = {param}", (new_status, username))
    conn.commit()
    c.close()
    conn.close()

async def monitor_loop(application):
    await asyncio.sleep(5)
    session = application.bot_data.get("http_session")
    if not session:
        return
    sem = asyncio.Semaphore(5)

    while True:
        try:
            monitors = get_all_monitors()
            if monitors:
                for chat_id, username, last_status in monitors:
                    async with sem:
                        current_banned = await fetch_profile_info(session, username)
                        new_status = 1 if current_banned else 0

                        if new_status != last_status:
                            update_monitor_status(username, new_status)
                            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            profile_link = f"https://instagram.com/{username}"
                            keyboard = [[InlineKeyboardButton("🔗 Open Instagram / فتح إنستغرام", url=profile_link)]]
                            reply_markup = InlineKeyboardMarkup(keyboard)

                            if new_status == 1:
                                caption = (
                                    f"🚨 **حساب محظور! / Banned Account!**\n\n"
                                    f"👤 User / اليوزر: `@{username}`\n"
                                    f"📊 Status / الحالة: 🔴 محظور (Banned)\n"
                                    f"⏰ Time / الوقت: `{current_time}`"
                                    f"{RIGHTS_TEXT['ar']}"
                                )
                            else:
                                caption = (
                                    f"🎉 **حساب متاح! / Unbanned Account!**\n\n"
                                    f"👤 User / اليوزر: `@{username}`\n"
                                    f"📊 Status / الحالة: 🟢 نشط (Active)\n"
                                    f"⏰ Time / الوقت: `{current_time}`"
                                    f"{RIGHTS_TEXT['ar']}"
                                )

                            for target_chat in list(set([chat_id, NOTIFICATION_GROUP_ID])):
                                gif_url = BAN_GIF_URL if new_status == 1 else UNBAN_GIF_URL
                                try:
                                    if gif_url:
                                        await application.bot.send_animation(target_chat, gif_url, caption=caption, parse_mode="Markdown", reply_markup=reply_markup)
                                    else:
                                        await application.bot.send_message(target_chat, caption, parse_mode="Markdown", reply_markup=reply_markup)
                                except:
                                    pass
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(30)

def is_admin(update):
    return update.effective_user.id in (OWNER_ID, ADMIN_ID)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇮🇶 العربية", callback_data="lang_ar"),
            InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")
        ]
    ])
    text = "🌐 **يرجى اختيار اللغة / Please select your language:**"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ar')
    user_id = update.effective_user.id
    is_owner = (user_id == OWNER_ID)

    if lang == "ar":
        btn_add = create_button("➕ إضافة حساب", callback_data="add_user")
        btn_delete = create_button("➖ حذف حساب", callback_data="delete_user")
        btn_group = create_button("👥 القناة الرسمية", url=GROUP_LINK)
        btn_dev = create_button("💬 التواصل مع المطور", url=DEV_LINK)
        btn_help = create_button("❓ التعليمات", callback_data="show_help")
        btn_check = create_button("🔍 فحص سريع", callback_data="check_user")
        btn_list = create_button("📜 قائمة المراقبة", callback_data="list_users")
        btn_india = create_button("🇮🇳 رابط الهندي", web_app_url=INDIAN_URL, icon_emoji_id=EMOJI_ID_INDIAN)
        btn_brazil = create_button("🇧🇷 رابط البرازيلي", web_app_url=BRAZIL_URL, icon_emoji_id=EMOJI_ID_BRAZIL)
        caption = f"⚡️ **لوحة التحكم المباشرة (24/7)**\nاختر الخدمة المطلوبة من الأسفل:{RIGHTS_TEXT['ar']}"
    else:
        btn_add = create_button("➕ Add Account", callback_data="add_user")
        btn_delete = create_button("➖ Remove Account", callback_data="delete_user")
        btn_group = create_button("👥 Official Channel", url=GROUP_LINK)
        btn_dev = create_button("💬 Contact Developer", url=DEV_LINK)
        btn_help = create_button("❓ Help", callback_data="show_help")
        btn_check = create_button("🔍 Quick Check", callback_data="check_user")
        btn_list = create_button("📜 Monitor List", callback_data="list_users")
        btn_india = create_button("🇮🇳 Indian Form", web_app_url=INDIAN_URL, icon_emoji_id=EMOJI_ID_INDIAN)
        btn_brazil = create_button("🇧🇷 Brazil Form", web_app_url=BRAZIL_URL, icon_emoji_id=EMOJI_ID_BRAZIL)
        caption = f"⚡️ **Control Panel (24/7)**\nSelect a service from below:{RIGHTS_TEXT['en']}"

    if is_owner:
        keyboard = [
            [btn_add, btn_delete],
            [btn_check, btn_list],
            [btn_india, btn_brazil],
            [btn_help, btn_dev],
            [btn_group]
        ]
    else:
        keyboard = [
            [btn_add, btn_delete],
            [btn_help, btn_dev],
            [btn_group]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        try:
            await update.callback_query.message.delete()
        except:
            pass
        await context.bot.send_animation(
            chat_id=update.effective_chat.id,
            animation=OWNER_START_GIF_URL if is_owner else MONITOR_START_GIF_URL,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ar')
    if lang == "ar":
        text = (
            f"📖 **دليل الاستخدام السريع:**\n\n"
            f"• `/chk username` ⇦ فحص حساب فوري.\n"
            f"• `/add username` ⇦ إضافة حساب للمراقبة.\n"
            f"• `/delete username` ⇦ حذف حساب من المراقبة.\n"
            f"• `/status` ⇦ عرض قائمة المراقبة للمجموعة."
            f"{RIGHTS_TEXT['ar']}"
        )
        back_btn = InlineKeyboardButton("🔙 العودة", callback_data="back_start")
    else:
        text = (
            f"📖 **Quick Guide:**\n\n"
            f"• `/chk username` ⇦ Check account status.\n"
            f"• `/add username` ⇦ Add to 24/7 monitor.\n"
            f"• `/delete username` ⇦ Remove from monitor.\n"
            f"• `/status` ⇦ View monitor list."
            f"{RIGHTS_TEXT['en']}"
        )
        back_btn = InlineKeyboardButton("🔙 Back", callback_data="back_start")

    keyboard = InlineKeyboardMarkup([[back_btn]])
    if update.callback_query:
        try:
            await update.callback_query.edit_message_caption(caption=text, parse_mode="Markdown", reply_markup=keyboard)
        except:
            await update.callback_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def chk_command(update, context):
    lang = context.user_data.get('lang', 'ar')
    if not context.args:
        msg = "⚠️ **الاستخدام:** `/chk username`\n⚠️ **Usage:** `/chk username`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return
    username = context.args[0].replace("@", "").strip()
    wait_txt = f"🔍 **جاري الفحص `@{username}`...**\n🔍 **Checking `@{username}`...**"
    wait_msg = await update.message.reply_text(wait_txt, parse_mode="Markdown")
    session = context.application.bot_data.get("http_session")

    is_banned = await fetch_profile_info(session, username)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Instagram", url=f"https://instagram.com/{username}")]])

    if lang == "ar":
        status_str = "🔴 محظور (Banned)" if is_banned else "🟢 نشط (Active)"
        caption = f"📊 **نتيجة الفحص:**\n\n👤 الحساب: `@{username}`\n📌 الحالة: **{status_str}**\n⏰ الوقت: `{current_time}`{RIGHTS_TEXT['ar']}"
    else:
        status_str = "🔴 Banned" if is_banned else "🟢 Active"
        caption = f"📊 **Check Result:**\n\n👤 User: `@{username}`\n📌 Status: **{status_str}**\n⏰ Time: `{current_time}`{RIGHTS_TEXT['en']}"

    gif_url = BAN_GIF_URL if is_banned else UNBAN_GIF_URL
    try:
        await wait_msg.delete()
        await context.bot.send_animation(update.effective_chat.id, gif_url, caption=caption, parse_mode="Markdown", reply_markup=reply_markup)
    except:
        await wait_msg.edit_text(caption, parse_mode="Markdown", reply_markup=reply_markup)

async def add_command(update, context):
    lang = context.user_data.get('lang', 'ar')
    if not context.args:
        msg = "⚠️ **الاستخدام:** `/add username`\n⚠️ **Usage:** `/add username`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return
    username = context.args[0].replace("@", "").strip()
    session = context.application.bot_data.get("http_session")

    is_banned = await fetch_profile_info(session, username)
    if add_monitor(update.effective_chat.id, username, 1 if is_banned else 0):
        txt = f"✅ **تمت الإضافة `@{username}` بنجاح!**{RIGHTS_TEXT['ar']}" if lang == "ar" else f"✅ **Added `@{username}` successfully!**{RIGHTS_TEXT['en']}"
    else:
        txt = f"⚠️ **الحساب `@{username}` مضاف مسبقاً.**" if lang == "ar" else f"⚠️ **`@{username}` is already added.**"
    await update.message.reply_text(txt, parse_mode="Markdown")

async def delete_command(update, context):
    lang = context.user_data.get('lang', 'ar')
    if not context.args:
        msg = "⚠️ **الاستخدام:** `/delete username`\n⚠️ **Usage:** `/delete username`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return
    username = context.args[0].replace("@", "").strip()
    if remove_monitor(username):
        txt = f"🗑 **تم حذف `@{username}` من المراقبة.**{RIGHTS_TEXT['ar']}" if lang == "ar" else f"🗑 **Removed `@{username}` from monitor.**{RIGHTS_TEXT['en']}"
    else:
        txt = f"⚠️ **الحساب `@{username}` غير موجود.**" if lang == "ar" else f"⚠️ **`@{username}` not found.**"
    await update.message.reply_text(txt, parse_mode="Markdown")

async def status_command(update, context):
    lang = context.user_data.get('lang', 'ar')
    monitors = get_all_monitors()
    current_chat_monitors = [m for m in monitors if m[0] == update.effective_chat.id]

    if not current_chat_monitors:
        msg = "📜 **لا توجد حسابات مراقبة هنا.**" if lang == "ar" else "📜 **No monitored accounts here.**"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    msg = "📋 **المراقبة الحالية:**\n\n" if lang == "ar" else "📋 **Monitored Accounts:**\n\n"
    for chat_id, username, last_status in current_chat_monitors:
        status = "🔴 محظور (Banned)" if last_status == 1 else "🟢 نشط (Active)"
        msg += f"• `@{username}` ⇦ {status}\n"
    msg += RIGHTS_TEXT[lang]
    await update.message.reply_text(msg, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("lang_"):
        context.user_data['lang'] = data.split("_")[1]
        await show_main_menu(update, context)
        return

    lang = context.user_data.get('lang', 'ar')

    if data == "show_help":
        await help_command(update, context)
        return
    elif data == "back_start":
        await show_main_menu(update, context)
        return

    if data == "add_user":
        context.user_data['awaiting_action'] = 'add'
        txt = "📥 **أرسل اليوزر للإضافة:**" if lang == "ar" else "📥 **Send username to add:**"
        await query.message.reply_text(txt, parse_mode="Markdown")
    elif data == "delete_user":
        context.user_data['awaiting_action'] = 'delete'
        txt = "🗑 **أرسل اليوزر للحذف:**" if lang == "ar" else "🗑 **Send username to remove:**"
        await query.message.reply_text(txt, parse_mode="Markdown")
    elif data == "check_user":
        context.user_data['awaiting_action'] = 'check'
        txt = "🔍 **أرسل اليوزر للفحص:**" if lang == "ar" else "🔍 **Send username to check:**"
        await query.message.reply_text(txt, parse_mode="Markdown")
    elif data == "list_users":
        await show_all_users(query.message, lang)

async def show_all_users(message, lang):
    rows = get_all_monitors()
    if not rows:
        txt = "📜 **لا توجد حسابات تحت المراقبة.**" if lang == "ar" else "📜 **No accounts under monitoring.**"
        await message.reply_text(txt, parse_mode="Markdown")
        return
    msg = "📋 **جميع الحسابات المراقبة:**\n\n" if lang == "ar" else "📋 **All Monitored Accounts:**\n\n"
    for chat_id, username, last_status in rows:
        status = "🔴 محظور (Banned)" if last_status == 1 else "🟢 نشط (Active)"
        msg += f"• `@{username}` ⇦ {status}\n"
    msg += RIGHTS_TEXT[lang]
    await message.reply_text(msg, parse_mode="Markdown")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    action = context.user_data.get('awaiting_action')
    if not action:
        return

    context.user_data.pop('awaiting_action', None)
    lang = context.user_data.get('lang', 'ar')
    username = update.message.text.strip().replace("@", "")
    session = context.application.bot_data.get("http_session")

    if action == 'add':
        is_banned = await fetch_profile_info(session, username)
        if add_monitor(update.effective_chat.id, username, 1 if is_banned else 0):
            txt = f"✅ **تم إضافة `@{username}` بنجاح!**{RIGHTS_TEXT['ar']}" if lang == "ar" else f"✅ **Added `@{username}` successfully!**{RIGHTS_TEXT['en']}"
        else:
            txt = f"⚠️ **اليوزر `@{username}` مضاف مسبقاً.**" if lang == "ar" else f"⚠️ **`@{username}` already exists.**"
        await update.message.reply_text(txt, parse_mode="Markdown")
    elif action == 'delete':
        if remove_monitor(username):
            txt = f"🗑 **تم حذف `@{username}`.**{RIGHTS_TEXT['ar']}" if lang == "ar" else f"🗑 **Removed `@{username}`.**{RIGHTS_TEXT['en']}"
        else:
            txt = f"⚠️ **اليوزر `@{username}` غير موجود.**" if lang == "ar" else f"⚠️ **`@{username}` not found.**"
        await update.message.reply_text(txt, parse_mode="Markdown")
    elif action == 'check':
        is_banned = await fetch_profile_info(session, username)
        status = "🔴 محظور (Banned)" if is_banned else "🟢 نشط (Active)"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Instagram", url=f"https://instagram.com/{username}")]])
        if lang == "ar":
            txt = f"📊 حالة `@{username}`: **{status}**{RIGHTS_TEXT['ar']}"
        else:
            txt = f"📊 Status of `@{username}`: **{status}**{RIGHTS_TEXT['en']}"
        await update.message.reply_text(txt, reply_markup=reply_markup, parse_mode="Markdown")

async def post_init(application):
    init_db()
    session = aiohttp.ClientSession()
    application.bot_data["http_session"] = session
    application.bot_data["monitor_task"] = asyncio.create_task(monitor_loop(application))

async def post_shutdown(application):
    monitor_task = application.bot_data.get("monitor_task")
    if monitor_task:
        monitor_task.cancel()

    session = application.bot_data.get("http_session")
    if session and not session.closed:
        await session.close()

import asyncio

def main():
    # إنشاء وضبط Event Loop صريح متوافق مع Python 3.14
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = Application.builder().token(TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("chk", chk_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CommandHandler("status", status_command))

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    keep_alive()
    main()
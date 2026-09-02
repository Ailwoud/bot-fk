if True:
  import asyncio
  import libsql
  import io
  import json
  import re
  import sqlite3
  import threading
  import time
  import os
  import importlib
  import pkgutil
  import urllib.parse
  import aiohttp
  from flask import Flask
  from datetime import datetime

  # The Replit package resolver can leave the unrelated "telegram" package
  # next to python-telegram-bot. Re-export missing official classes lazily so
  # the bot keeps using python-telegram-bot's installed implementation.
  import telegram as _telegram_package

  def _telegram_compat_getattr(name):
      for module_info in pkgutil.walk_packages(
          _telegram_package.__path__, _telegram_package.__name__ + "."
      ):
          try:
              module = importlib.import_module(module_info.name)
          except Exception:
              continue
          if hasattr(module, name):
              value = getattr(module, name)
              setattr(_telegram_package, name, value)
              return value
      raise AttributeError(name)

  _telegram_package.__getattr__ = _telegram_compat_getattr
  from telegram import InputFile, Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
  from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, TypeHandler, filters

  TOKEN = os.getenv("BOT_TOKEN", "")
  OWNER_ID = 8138168728
  ADMIN_IDS = {5813628298, 8242825436}
  ADMIN_ID = tuple(ADMIN_IDS)
  DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitors.db")
  NOTIFICATION_GROUP_ID = -5164692912

  OWNER_START_GIF_URL = "https://t.me/ndejxjgxsh/10"
  MONITOR_START_GIF_URL = "https://t.me/ndejxjgxsh/11"
  BAN_GIF_URL = "https://t.me/ndejxjgxsh/5"
  UNBAN_GIF_URL = "https://t.me/ndejxjgxsh/4"

  INDIAN_URL = "https://gac.gov.in"
  BRAZIL_URL = "https://consumidor.gov.br"
  GROUP_LINK = "https://t.me/ceceeee"

  EMOJI_ID_INDIAN = "6323256281456970434"
  EMOJI_ID_BRAZIL = "6323256281456970435"

  DEV1_USERNAME = "s8s8sss"

  MAX_USERNAMES_PER_BATCH = 30
  MAX_USERNAMES_PER_USER = 15
  MAX_FAST_USERNAMES_PER_USER = 5
  FAST_SCAN_INTERVAL = 10
  LEGACY_ACTIVATION_DAYS = 30
  MAX_DURATION_DAYS = 3650
  MAX_TEXT_FILE_BYTES = 512 * 1024
  INSTAGRAM_USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")

  web_app = Flask(__name__)

  @web_app.route("/")
  def health_check():
      return "OK"

  def run_web_server():
      port = int(os.getenv("PORT", 8080))
      web_app.run(host="0.0.0.0", port=port, use_reloader=False)

  INSTAGRAM_SESSIONID = os.getenv("INSTAGRAM_SESSIONID", "")
  INSTAGRAM_SESSIONIDS = os.getenv("INSTAGRAM_SESSIONIDS", "")
  INSTAGRAM_SESSIONS_FILE = os.getenv(
      "INSTAGRAM_SESSIONS_FILE",
      os.path.join(os.path.dirname(os.path.abspath(__file__)), "instagram_sessions.txt"),
  )
  INSTAGRAM_DS_USER_ID = os.getenv("INSTAGRAM_DS_USER_ID", "")
  CLOUDFLARE_PROXY_URL = os.getenv("CLOUDFLARE_PROXY_URL", "").strip()

  def proxy_url(original_url):
      """Convert an Instagram URL to route through Cloudflare Worker Proxy.
      If no proxy is configured, return the original URL.
      Preserves all URL paths and query parameters.
      """
      if not CLOUDFLARE_PROXY_URL:
          return original_url

      # Extract the path after instagram.com domain
      # Handle both www.instagram.com and i.instagram.com
      if "https://www.instagram.com" in original_url:
          path = original_url.replace("https://www.instagram.com", "")
      elif "https://i.instagram.com" in original_url:
          path = original_url.replace("https://i.instagram.com", "")
      else:
          # Not an Instagram URL, return as-is
          return original_url

      # Combine proxy URL with the path
      # Ensure proper URL formatting (no double slashes)
      proxy_base = CLOUDFLARE_PROXY_URL.rstrip('/')
      return f"{proxy_base}{path}"

  def instagram_request_candidates(original_url):
      """Try proxy first, then fall back to direct Instagram if the worker is blocked."""
      candidates = []
      seen = set()
      for candidate in [proxy_url(original_url), original_url]:
          if candidate and candidate not in seen:
              seen.add(candidate)
              candidates.append(candidate)
      return candidates

  def load_session_ids():
      """Read the primary secret first, then supported fallback sources."""
      values = []
      file_values = []
      try:
          with open(INSTAGRAM_SESSIONS_FILE, "r", encoding="utf-8") as file:
              file_values.extend(
                  line.strip()
                  for line in file
                  if line.strip() and not line.lstrip().startswith("#")
              )
      except OSError:
          pass
      if INSTAGRAM_SESSIONID.strip():
          values.append(INSTAGRAM_SESSIONID.strip())
      else:
          values.extend(
              part.strip()
              for part in re.split(r"[\s,;]+", INSTAGRAM_SESSIONIDS or "")
              if part.strip()
          )
          values.extend(file_values)
      unique_values = []
      seen = set()
      for value in values:
          if value not in seen:
              seen.add(value)
              unique_values.append(value)
      return unique_values

  INSTAGRAM_SESSION_POOL = load_session_ids()
  _session_cursor = 0
  _session_cursor_lock = threading.Lock()
  _session_file_lock = threading.Lock()
  _retired_sessions = set()
  SESSION_FAILURE = object()

  # ---------------------------------------------------------------------------
  # Translations (no emojis)
  # ---------------------------------------------------------------------------
  T = {
      "ar": {
          "choose_lang": "اختر لغتك:",
          "btn_lang_ar": "عربي",
          "btn_lang_en": "English",
          "start_group": (
              "أهلاً بكم في بوت مراقبة إنستغرام\n\n"
              "أضيفوا الحسابات للمراقبة، والبوت يرسل تنبيهاً عند تغيّر حالتها.\n"
              "اختاروا من الأزرار أو اكتبوا /help لعرض طريقة الاستخدام."
          ),
          "start_private": (
              "أهلاً بك في بوت مراقبة إنستغرام\n\n"
              "من هنا تقدر تفحص الحسابات وتضيفها للمراقبة.\n"
               "عند الإضافة راح تختار المراقبة العادية كل 30 ثانية.\n"
               "المراقبة السريعة كل 10 ثواني تظهر فقط إذا فعّلها الأدمن لحسابك."
          ),
          "btn_add": "إضافة للمراقبة",
          "btn_delete": "حذف من المراقبة",
          "btn_group": "القناة الرسمية",
          "btn_help": "تعليمات الاستخدام",
          "btn_check": "فحص حساب",
          "btn_list": "قائمة المراقبة",
           "btn_users": "قائمة التفعيلات",
          "btn_india": "الرابط الهندي",
          "btn_brazil": "الرابط البرازيلي",
           "btn_language": "تغيير اللغة",
            "btn_export": "إرسال اليوزرات المحفوظة",
            "btn_myid": "إرسال معرفي للأدمن",
            "btn_admin": "لوحة الأدمن",
          "btn_add_slow": "مراقبة كل 30 ثانية",
           "btn_add_fast": "مراقبة كل 10 ثواني",
          "btn_add_choose": "اختيار سرعة المراقبة",
          "btn_back": "العودة للرئيسية",
          "btn_open_ig": "فتح الحساب في إنستغرام",
          "help_text": (
              "دليل الاستخدام\n"
              "━━━━━━━━━━━━━━\n"
              "1) فحص حساب الآن:\n"
              "/chk username\n\n"
              "2) إضافة للمراقبة كل 30 ثانية:\n"
              "/add username1 username2\n\n"
              "3) الإضافة السريعة كل 10 ثواني:\n"
              "/addfast username1 username2\n\n"
              "4) حذف حساب:\n"
              "/delete username1 username2\n\n"
              "ملاحظات:\n"
              "• اكتب اليوزر بدون @ أو ارفعه بملف TXT، يوزر واحد بكل سطر.\n"
              "• الحد الأعلى في الطلب الواحد 30 يوزر.\n"
              "• الإضافة والفحص يحتاجان تفعيل الحساب.\n"
              "• الحد العادي يحدده الأدمن، وبحد أعلى 15 يوزراً.\n"
              "• الفحص السريع يظهر فقط لمن يحدده الأدمن، وبحد أعلى 5 يوزرات للشخص و30 يوزراً للنظام.\n"
              "• لتغيير اللغة اكتب /language."
          ),
           "admin_help_text": (
               "أوامر الأدمن\n"
               "━━━━━━━━━━━━━━\n"
               "/admin — فتح لوحة الأدمن.\n"
               "/active — تفعيل شخص خطوة بخطوة: ID ثم الاسم ثم حد العادي ثم حد السريع ثم المدة.\n"
               "مثال: اكتب /active واتبع الأسئلة.\n"
               "/deactivate ID — إلغاء تفعيل شخص.\n"
               "/users — عرض التفعيلات والاستخدام.\n"
               "/sessions — عرض عدد السيشنات المستخدمة.\n"
               "/status — عرض حسابات المجموعة.\n"
               "/export — إرسال ملف بكل الحسابات الحالية.\n"
               "/broadcast نص — إرسال رسالة للجميع."
           ),
          "devs_only": "عذراً، هذا الخيار للمطورين فقط.",
          "chk_usage": "الاستخدام الصحيح: /chk username",
          "chk_wait": "جاري التحقق من الحساب @{username}، لحظات...",
          "chk_error": "تعذر إكمال العملية حالياً. حاول مرة ثانية بعد قليل.",
          "chk_result": "نتيجة التحقق\n━━━━━━━━━━━━━━\nالحساب: @{username}\nالحالة: {status}\nوقت التحقق: {time}",
           "add_usage": "لإضافة حسابات اكتب:\n/add user1 user2\n\nاكتب اليوزرات بدون @، أو استخدم زر الإضافة من القائمة.",
           "add_wait": "جاري التحقق من {count} حساب وإضافتها للمراقبة...",
          "add_error": "تعذر تنفيذ الإضافة حالياً. حاول مرة ثانية.",
           "add_result_header": "نتيجة الإضافة\n━━━━━━━━━━━━━━",
           "add_line_added": "تمت إضافة @{username} — الحالة: {status}",
           "add_line_exists": "@{username} مضاف للمراقبة مسبقاً.",
           "delete_usage": "لحذف حسابات اكتب:\n/delete user1 user2\n\nتقدر تحذف الحسابات التي أضفتها، والأدمن يقدر يحذف أي حساب.",
           "delete_result_header": "نتيجة الحذف\n━━━━━━━━━━━━━━",
           "delete_line_removed": "تم حذف @{username} من المراقبة.",
           "delete_line_notfound": "لم يُعثر على @{username} ضمن حساباتك.",
          "status_admin_only": "هذا الأمر مخصص لـ المسؤولين فقط.",
          "status_empty": "لا توجد حسابات قيد المراقبة في هذه المجموعة.",
          "status_header": "قائمة الحسابات المراقبة حالياً\n----------------\n",
          "list_empty": "لا توجد حسابات تحت المراقبة.",
          "list_header": "جميع الحسابات المراقبة بالنظام\n----------------\n",
           "language_saved": "تم تغيير لغة هذه المحادثة إلى العربية.",
           "export_empty": "لا توجد يوزرات محفوظة حالياً.",
            "export_caption": "كل الحسابات الموجودة حالياً في المراقبة.",
            "prompt_add": (
                "إضافة حسابات للمراقبة\n"
                "━━━━━━━━━━━━━━\n"
                "اختَر سرعة المراقبة أولاً:\n"
                "• كل 30 ثانية: مناسب للمراقبة العادية.\n"
               "• كل 10 ثواني: للمستخدمين الذين لديهم صلاحية سريعة.\n\n"
                "للإلغاء اكتب /cancel."
           ),
            "prompt_add_slow": (
                "تم اختيار المراقبة كل 30 ثانية.\n\n"
                "أرسل اليوزرات بدون @، مفصولة بمسافة أو كل واحد بسطر.\n"
                "تقدر أيضاً ترفع ملف TXT، يوزر واحد بكل سطر.\n\n"
                "مثال:\nuser1\nuser2\nuser3\n\n"
                "للإلغاء اكتب /cancel."
           ),
            "prompt_add_fast": (
                 "تم اختيار المراقبة كل 10 ثواني.\n\n"
                "أرسل اليوزرات بدون @، مفصولة بمسافة أو كل واحد بسطر.\n"
                "تقدر أيضاً ترفع ملف TXT، يوزر واحد بكل سطر.\n\n"
                "مثال:\nuser1\nuser2\nuser3\n\n"
                "للإلغاء اكتب /cancel."
           ),
           "prompt_delete": (
               "حذف حسابات من المراقبة\n"
               "━━━━━━━━━━━━━━\n"
               "أرسل اليوزرات بدون @، مفصولة بمسافة أو كل واحد بسطر.\n\n"
               "للإلغاء اكتب /cancel."
          ),
           "prompt_check": "أرسل اليوزر المراد التحقق منه بدون @:",
           "invalid_username": "أرسل يوزراً صحيحاً بدون رموز أو نص إضافي.",
           "cancelled": "تم إلغاء العملية.",
           "too_many": "الحد الأعلى {max} يوزر في الطلب الواحد. أرسل الباقي على دفعات.",
           "msg_check_notallowed": "لا يوجد تصريح يسمح لك بهذه العملية.",
           "msg_check_result": "الحالة الحالية للحساب @{username}: {status}",
          "checklogin_notallowed": "غير مصرح لك.",
          "checklogin_success": "تم تسجيل الدخول بنجاح.\nUser: @{username}",
          "checklogin_fail": "فشل تسجيل الدخول.",
            "access_required": "حسابك غير مفعّل. راسل المطوّر حتى يفعّل حسابك.",
            "access_expired": "انتهت مدة تفعيل حسابك. راسل المطوّر لتجديد التفعيل.",
            "fast_access_required": "لا تملك صلاحية الفحص السريع كل 10 ثواني. اطلب من الأدمن تفعيلها.",
            "slow_quota_exceeded": "وصلت إلى حد المراقبة العادية. المتبقي: {remaining}.",
            "fast_quota_exceeded": "وصلت إلى حد المراقبة السريعة. المتبقي: {remaining}.",
            "my_id": "معرّف حسابك: {user_id}\nأرسل الرقم إلى الأدمن لتفعيل حسابك.",
           "admin_panel": (
               "لوحة الأدمن\n"
               "━━━━━━━━━━━━━━\n"
               "استخدم الأزرار أو اكتب /active لتفعيل شخص خطوة بخطوة.\n\n"
                "العادي = كل 30 ثانية\n"
                "السريع = كل 10 ثواني، ويظهر فقط لمن تمنحه الصلاحية.\n"
                "الحد الأعلى للسريع: 5 لكل شخص و30 للنظام."
           ),
              "grant_usage": "اكتب /active ثم أدخل البيانات خطوة بخطوة.",
            "revoke_usage": "الاستخدام: /deactivate user_id",
            "admin_grant_prompt": "نبدأ تفعيل مستخدم جديد.\nأرسل ID الشخص.\n\nللإلغاء اكتب /cancel.",
            "active_prompt_name": "أرسل اسم الشخص.",
            "active_prompt_slow": "كم حساباً عادياً مسموحاً له؟\nاكتب رقماً من 0 إلى 15.",
            "active_prompt_fast": "كم حساباً سريعاً مسموحاً له؟\nاكتب رقماً من 0 إلى 5.\nاكتب 0 لإلغاء صلاحية الفحص السريع.",
            "active_prompt_days": "كم يوم مدة التفعيل؟\nاكتب رقماً أكبر من صفر.",
            "active_invalid": "القيمة غير صحيحة. أرسل رقماً مناسباً أو اكتب /cancel.",
             "activation_error": "تعذر حفظ التفعيل حالياً. حاول مرة ثانية.",
             "active_success": "تم تفعيل الحساب\n━━━━━━━━━━━━━━\nID: {user_id}\nالمستخدم: {user_label}\nالمدة: {duration_days} يوم\nالعادي: {slow_used}/{slow_limit}\nالسريع: {fast_summary}",
            "admin_revoke_prompt": "أرسل معرف المستخدم المراد إلغاء تفعيله.\n\nأرسل /cancel للإلغاء.",
            "users_header": "قائمة التفعيلات والاستخدام\n━━━━━━━━━━━━━━\n",
            "users_empty": "لا توجد حسابات مفعّلة حالياً.",
             "revoke_success": "تم إلغاء تفعيل الحساب\nID: {user_id}\nالمستخدم: {user_label}\nوتم حذف حساباته من المراقبة.",
           "user_not_found": "لم يتم العثور على تصريح لهذا المستخدم.",
           "quota_exceeded": "تجاوزت حدك المسموح. المتبقي لك {remaining} يوزر.",
              "access_status_line": "ID: {user_id} | المستخدم: {user_label}\nالتفعيل: {active} | ينتهي: {expires_at}\nالعادي: {slow_used}/{slow_limit}\nالسريع: {fast_summary}",
           "broadcast_usage": "الاستخدام:\n/broadcast نص الرسالة",
           "broadcast_empty": "اكتب نص الرسالة بعد الأمر.",
           "broadcast_started": "جاري إرسال الرسالة إلى جميع المحادثات المسجلة...",
           "broadcast_done": "تم الإرسال إلى {sent} محادثة. فشل الإرسال إلى {failed} محادثة.",
             "sessions_status": "فحص السيشنات\n━━━━━━━━━━━━━━\nالشغالة: {working}/{total}\nالمتوقفة: {failed}\nضع السيشنات في ملف instagram_sessions.txt، كل سيشن بسطر.",
           "file_invalid": "ارفع ملف TXT فقط، ويفضل أن يكون اسم الملف واضحاً.",
           "file_too_large": "حجم الملف كبير. الحد الأعلى هو {max_kb} كيلوبايت.",
           "file_error": "تعذر قراءة الملف حالياً. حاول رفعه مرة ثانية.",
           "button_expired": "انتهت صلاحية هذا الزر. افتح القائمة من جديد.",
           "no_monitoring_options": "لا توجد سرعة مراقبة متاحة حالياً ضمن صلاحياتك أو الحد المسموح.",
           "invalid_access_values": "القيم غير صحيحة. الأيام أكبر من صفر، والحدود أرقام صحيحة من صفر أو أكثر.",
          "status_banned": "محظور",
           "status_active": "نشط",
           "status_unknown": "غير مؤكد — Instagram يمنع الفحص مؤقتاً",
           "ban_alert": "تنبيه تغيّر الحالة\n━━━━━━━━━━━━━━\nالحساب: @{username}\nالحالة: محظور أو غير متاح\nالوقت: {time}",
           "unban_alert": "تنبيه تغيّر الحالة\n━━━━━━━━━━━━━━\nالحساب: @{username}\nالحالة: نشط ويعمل\nالوقت: {time}",
      },
      "en": {
          "choose_lang": "Choose your language:",
          "btn_lang_ar": "Arabic",
          "btn_lang_en": "English",
          "start_group": (
              "Welcome to the Instagram Monitor Bot\n\n"
              "Add accounts to monitoring and get an alert when their status changes.\n"
              "Use the buttons below or send /help to see the commands."
          ),
          "start_private": (
              "Welcome to the Instagram Monitor Bot\n\n"
              "Check accounts and add them to monitoring from here.\n"
              "Standard monitoring runs every 30 seconds.\n"
              "Fast monitoring runs every 10 seconds only when an admin enables it."
          ),
          "btn_add": "Add to monitoring",
          "btn_delete": "Remove from monitoring",
          "btn_group": "Official Channel",
          "btn_help": "Help & Instructions",
          "btn_check": "Check Account",
          "btn_list": "Watchlist",
            "btn_users": "Activations",
          "btn_india": "India Report Link",
          "btn_brazil": "Brazil Report Link",
           "btn_language": "Change Language",
            "btn_export": "Send Saved Usernames",
            "btn_myid": "Send My ID to Admin",
            "btn_admin": "Admin Panel",
          "btn_add_slow": "Monitor every 30 seconds",
          "btn_add_fast": "Monitor every 10 seconds",
          "btn_add_choose": "Choose monitoring speed",
          "btn_back": "Back to Home",
          "btn_open_ig": "Open Account on Instagram",
          "help_text": (
              "Usage guide\n"
              "━━━━━━━━━━━━━━\n"
              "1) Check now:\n"
              "/chk username\n\n"
              "2) Add to monitoring every 30 seconds:\n"
              "/add username1 username2\n\n"
              "3) Add to monitoring every 10 seconds:\n"
              "/addfast username1 username2\n\n"
              "4) Remove accounts:\n"
              "/delete username1 username2\n\n"
              "Notes:\n"
              "• Write usernames without @, or upload a TXT file with one per line.\n"
              "• Maximum 30 usernames per request.\n"
              "• Adding and checking require an activated account.\n"
              "• The admin chooses the standard limit, up to 15 usernames.\n"
              "• Fast monitoring appears only for people authorized by an admin, up to 5 per person and 30 system-wide.\n"
              "• Use /language to change language."
          ),
           "admin_help_text": (
               "Admin commands\n"
               "━━━━━━━━━━━━━━\n"
               "/admin — open the admin panel.\n"
               "/active — activate step by step: ID, name, standard limit, fast limit, then duration.\n"
               "Example: send /active and follow the questions.\n"
               "/deactivate ID — deactivate a person.\n"
               "/users — show activations and usage.\n"
               "/sessions — show the configured session count.\n"
               "/status — show accounts in the group.\n"
               "/export — send a file with all current accounts.\n"
               "/broadcast text — send a message to everyone."
           ),
          "devs_only": "Sorry, this option is for developers only.",
          "chk_usage": "Correct usage: /chk username",
          "chk_wait": "Checking account @{username}, please wait...",
          "chk_error": "The operation could not be completed right now. Please try again shortly.",
          "chk_result": "Account check result\n━━━━━━━━━━━━━━\nAccount: @{username}\nStatus: {status}\nChecked: {time}",
            "add_usage": "To add accounts, send:\n/add user1 user2\n\nWrite usernames without @, or use the add button.",
            "add_wait": "Checking and adding {count} account(s) to monitoring...",
          "add_error": "The accounts could not be added right now. Please try again.",
            "add_result_header": "Add result\n━━━━━━━━━━━━━━",
            "add_line_added": "Added @{username} — status: {status}",
            "add_line_exists": "@{username} is already being monitored.",
            "delete_usage": "To remove accounts, send:\n/delete user1 user2\n\nYou can remove accounts you added; admins can remove any account.",
            "delete_result_header": "Remove result\n━━━━━━━━━━━━━━",
            "delete_line_removed": "@{username} was removed from monitoring.",
            "delete_line_notfound": "@{username} was not found among your accounts.",
          "status_admin_only": "This command is for admins only.",
          "status_empty": "No accounts are being monitored in this group.",
          "status_header": "Currently monitored accounts\n----------------\n",
          "list_empty": "No accounts are being monitored.",
          "list_header": "All accounts monitored by the system\n----------------\n",
           "language_saved": "This chat's language has been changed to English.",
           "export_empty": "There are no saved usernames yet.",
            "export_caption": "All accounts currently being monitored.",
            "prompt_add": (
                "Add accounts to monitoring\n"
                "━━━━━━━━━━━━━━\n"
                "Choose the monitoring speed first:\n"
                "• Every 30 seconds: standard monitoring.\n"
                "• Every 10 seconds: requires fast-monitoring permission.\n\n"
                "Send /cancel to abort."
           ),
            "prompt_add_slow": (
                "Monitoring speed: every 30 seconds.\n\n"
                "Send usernames without @, separated by spaces or new lines.\n"
                "You can also upload a TXT file with one username per line.\n\n"
                "Example:\nuser1\nuser2\nuser3\n\n"
                "Send /cancel to abort."
           ),
            "prompt_add_fast": (
                 "Monitoring speed: every 10 seconds.\n\n"
                "Send usernames without @, separated by spaces or new lines.\n"
                "You can also upload a TXT file with one username per line.\n\n"
                "Example:\nuser1\nuser2\nuser3\n\n"
                "Send /cancel to abort."
           ),
           "prompt_delete": (
               "Remove accounts from monitoring\n"
               "━━━━━━━━━━━━━━\n"
               "Send usernames without @, separated by spaces or new lines.\n\n"
               "Send /cancel to abort."
          ),
           "prompt_check": "Send the username to check, without @:",
           "invalid_username": "Please send a valid username without extra text.",
           "cancelled": "The operation was cancelled.",
          "too_many": "Max {max} usernames at once, please send them in batches.",
          "msg_check_notallowed": "You are not authorized.",
          "msg_check_result": "Current status of @{username}: {status}",
          "checklogin_notallowed": "You are not authorized.",
          "checklogin_success": "Logged in successfully.\nUser: @{username}",
          "checklogin_fail": "Login failed.",
              "access_required": "Your account is not activated. Contact the developer to activate it.",
               "access_expired": "Your activation has expired. Contact the developer to renew it.",
              "fast_access_required": "You do not have fast monitoring permission. Ask an admin to enable 10-second monitoring.",
              "slow_quota_exceeded": "Your standard monitoring limit is full. Remaining: {remaining}.",
              "fast_quota_exceeded": "Your fast-monitoring limit is full. Remaining: {remaining}.",
            "my_id": "Your ID is: {user_id}\nSend this number to an admin to activate your account.",
            "admin_panel": (
                 "Admin panel\n"
                 "━━━━━━━━━━━━━━\n"
                 "Use the buttons or send /active to activate a person step by step.\n\n"
                  "Standard = every 30 seconds\n"
                  "Fast = every 10 seconds, visible only to people you authorize.\n"
                  "Fast limit: 5 per person and 30 system-wide."
           ),
              "grant_usage": "Send /active and enter the values step by step.",
            "revoke_usage": "Usage: /deactivate user_id",
             "admin_grant_prompt": "We will activate a new user.\nSend the user ID.\n\nSend /cancel to abort.",
            "active_prompt_name": "Send the person's name.",
            "active_prompt_slow": "How many standard accounts are allowed?\nSend a number from 0 to 15.",
            "active_prompt_fast": "How many fast accounts are allowed?\nSend a number from 0 to 5.\nSend 0 to disable fast monitoring.",
            "active_prompt_days": "How many days should the activation last?\nSend a number greater than zero.",
            "active_invalid": "Invalid value. Send an allowed number or /cancel.",
             "activation_error": "The activation could not be saved right now. Please try again.",
             "active_success": "Account activated\n━━━━━━━━━━━━━━\nID: {user_id}\nUser: {user_label}\nDuration: {duration_days} days\nStandard: {slow_used}/{slow_limit}\nFast: {fast_summary}",
            "admin_revoke_prompt": "Send the user ID to deactivate.\n\nSend /cancel to abort.",
             "users_header": "Activations and usage\n━━━━━━━━━━━━━━\n",
             "users_empty": "There are no activated accounts yet.",
              "revoke_success": "Account deactivated\nID: {user_id}\nUser: {user_label}\nTheir monitored accounts were removed.",
           "user_not_found": "No access grant was found for this user.",
           "invalid_access_values": "Days must be greater than zero; limits must be whole numbers of zero or more.",
           "quota_exceeded": "You have reached your limit. You can add {remaining} more usernames.",
               "access_status_line": "ID: {user_id} | User: {user_label}\nActive: {active} | Expires: {expires_at}\nStandard: {slow_used}/{slow_limit}\nFast: {fast_summary}",
           "broadcast_usage": "Usage:\n/broadcast message text",
           "broadcast_empty": "Write the message text after the command.",
           "broadcast_started": "Sending the message to all registered chats...",
           "broadcast_done": "Sent to {sent} chats. Failed for {failed} chats.",
             "sessions_status": "Session check\n━━━━━━━━━━━━━━\nWorking: {working}/{total}\nNot working: {failed}\nPut sessions in instagram_sessions.txt, one session per line.",
           "file_invalid": "Please upload a TXT file with a valid filename.",
           "file_too_large": "The file is too large. The maximum is {max_kb} KB.",
           "file_error": "The file could not be read right now. Please upload it again.",
           "button_expired": "This button has expired. Open the menu again.",
           "no_monitoring_options": "No monitoring speed is currently available for your permissions or remaining quota.",
          "status_banned": "Banned",
          "status_active": "Active",
          "status_unknown": "Unknown — Instagram is temporarily rate-limiting checks",
           "ban_alert": "Status change alert\n━━━━━━━━━━━━━━\nAccount: @{username}\nStatus: Banned or unavailable\nTime: {time}",
           "unban_alert": "Status change alert\n━━━━━━━━━━━━━━\nAccount: @{username}\nStatus: Active\nTime: {time}",
      },
  }


  def rights_text(lang):
      label = "المبرمج" if lang == "ar" else "Developer"
      return (
          f"\n\n----------------\n"
          f"{label}: [@{DEV1_USERNAME}](https://t.me/{DEV1_USERNAME})"
      )


  def tr(lang, key, **kwargs):
      lang = lang if lang in T else "ar"
      text = T[lang].get(key, T["ar"].get(key, key))
      if kwargs:
          text = text.format(**kwargs)
      return text


  def escape_markdown(value):
      """Escape user-provided text before sending it as Telegram Markdown."""
      return re.sub(r"([\\_*`\[\]])", r"\\\1", str(value))


  def split_message(text, limit=3900):
      """Split long Telegram messages at line boundaries when possible."""
      text = str(text or "")
      if len(text) <= limit:
          return [text]

      chunks = []
      current = ""
      for line in text.splitlines(keepends=True):
          if len(line) > limit:
              if current:
                  chunks.append(current)
                  current = ""
              for start in range(0, len(line), limit):
                  chunks.append(line[start:start + limit])
              continue
          if current and len(current) + len(line) > limit:
              chunks.append(current)
              current = ""
          current += line
      if current:
          chunks.append(current)
      return chunks or [text[:limit]]


  async def reply_long(message, text, parse_mode="Markdown"):
      for chunk in split_message(text):
          await message.reply_text(chunk, parse_mode=parse_mode)


  async def edit_and_reply_long(editable_message, reply_message, text, parse_mode="Markdown"):
      chunks = split_message(text)
      try:
          await editable_message.edit_text(chunks[0], parse_mode=parse_mode)
      except Exception:
          await reply_message.reply_text(chunks[0], parse_mode=parse_mode)
      for chunk in chunks[1:]:
          await reply_message.reply_text(chunk, parse_mode=parse_mode)


  def format_status(lang, result):
      if result is True:
          return tr(lang, "status_banned")
      if result is False:
          return tr(lang, "status_active")
      return tr(lang, "status_unknown")


  def get_cookies(sessionid_value=None):
      global _session_cursor
      if sessionid_value is None and not INSTAGRAM_SESSION_POOL:
          raise ValueError("No Instagram session IDs are configured")

      if sessionid_value is None:
          with _session_cursor_lock:
              if not INSTAGRAM_SESSION_POOL:
                  raise ValueError("No Instagram session IDs are configured")
              sessionid_value = INSTAGRAM_SESSION_POOL[_session_cursor % len(INSTAGRAM_SESSION_POOL)]
              _session_cursor += 1

      sessionid = urllib.parse.unquote(sessionid_value)
      cookies = {'sessionid': sessionid}

      ds_user_id = INSTAGRAM_DS_USER_ID
      if not ds_user_id:
          parts = sessionid.split(':', 1)
          if parts and parts[0].isdigit():
              ds_user_id = parts[0]
      if ds_user_id:
          cookies['ds_user_id'] = ds_user_id

      return cookies


  def retire_session(session_id):
      """Remove a burned session from memory and its source file."""
      with _session_file_lock:
          if session_id in _retired_sessions:
              return None
          _retired_sessions.add(session_id)
          INSTAGRAM_SESSION_POOL[:] = [
              value for value in INSTAGRAM_SESSION_POOL if value != session_id
          ]

          removed_line = None
          try:
              with open(INSTAGRAM_SESSIONS_FILE, "r", encoding="utf-8") as file:
                  lines = file.readlines()
              kept_lines = []
              for line_number, line in enumerate(lines, start=1):
                  if line.strip() == session_id and removed_line is None:
                      removed_line = line_number
                      continue
                  kept_lines.append(line)
              if removed_line is not None:
                  with open(INSTAGRAM_SESSIONS_FILE, "w", encoding="utf-8") as file:
                      file.writelines(kept_lines)
          except OSError:
              pass
          return removed_line


  async def notify_retired_session(bot, line_number):
      if bot and line_number is not None:
          try:
              await bot.send_message(
                  NOTIFICATION_GROUP_ID,
                  f"تم تعطيل سيشن في السطر {line_number}",
              )
          except Exception:
              pass


  async def verify_instagram_sessions(session, bot=None):
      """Check every configured session and keep only working sessions for scans."""
      configured = list(INSTAGRAM_SESSION_POOL)
      statuses = []
      working_sessions = []
      for index, session_id in enumerate(configured, start=1):
          username = await get_logged_in_username(session, session_id=session_id)
          working = bool(username)
          statuses.append({
              "index": index,
              "working": working,
              "username": username,
          })
          if working:
              working_sessions.append(session_id)
          else:
              line_number = retire_session(session_id)
              await notify_retired_session(bot, line_number)

      INSTAGRAM_SESSION_POOL[:] = working_sessions
      return statuses

  HEADERS = {
      'User-Agent': 'Instagram 269.0.0.18.75 Android (26/8.0.0; 480dpi; 1080x1920; OnePlus; OnePlus3T; oneplus3; qcom; en_US; 314665258)',
      'Accept': '*/*',
      'Accept-Language': 'en-US,en;q=0.9',
      'X-IG-App-ID': '936619743392459',
      'X-Requested-With': 'XMLHttpRequest',
      'X-ASBD-ID': '129119',
      'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
  }

  def create_button(text, web_app_url=None, color=None, icon_emoji_id=None, callback_data=None, url=None):
      # Keep the interface plain: Telegram button colors/styles are not used.
      return InlineKeyboardButton(
          text=text,
          web_app=WebAppInfo(url=web_app_url) if web_app_url else None,
          callback_data=callback_data,
          url=url,
      )

  async def get_logged_in_username(session, session_id=None):
      cookies = get_cookies(session_id)

      for request_url in instagram_request_candidates("https://www.instagram.com/"):
          try:
              headers = HEADERS.copy()
              headers['referer'] = 'https://www.instagram.com/'
              async with session.get(request_url, headers=headers, cookies=cookies, timeout=30) as resp:
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
          except Exception:
              continue

      endpoints = [
          "https://i.instagram.com/api/v1/accounts/current_user/",
          "https://www.instagram.com/api/v1/accounts/current_user/",
      ]
      for url in endpoints:
          for request_url in instagram_request_candidates(url):
              headers = HEADERS.copy()
              headers['referer'] = 'https://www.instagram.com/'
              try:
                  async with session.get(request_url, headers=headers, cookies=cookies, timeout=30) as resp:
                      if resp.status == 200:
                          data = await resp.json()
                          username = data.get("user", {}).get("username")
                          if username:
                              return username
              except Exception:
                  continue

      for request_url in instagram_request_candidates("https://www.instagram.com/accounts/access_tool/current_user"):
          try:
              headers = HEADERS.copy()
              headers['referer'] = 'https://www.instagram.com/'
              async with session.get(request_url, headers=headers, cookies=cookies, timeout=30) as resp:
                  if resp.status == 200:
                      text = await resp.text()
                      match = re.search(r'"username"\s*:\s*"([^"]+)"', text)
                      if match:
                          return match.group(1)
          except Exception:
              continue

      return None

  async def fetch_profile_info(session, username: str, bot=None):
      original_url = f"https://www.instagram.com/{username}/"
      headers = HEADERS.copy()
      headers['Referer'] = 'https://www.instagram.com/'
      with _session_cursor_lock:
          session_ids = list(INSTAGRAM_SESSION_POOL)
          if session_ids:
              start = _session_cursor % len(session_ids)
              _session_cursor += 1
              session_ids = session_ids[start:] + session_ids[:start]

      for session_id in session_ids:
          try:
              async with session.get(
                  proxy_url(original_url),
                  headers=headers,
                  cookies=get_cookies(session_id),
                  timeout=30,
              ) as resp:
                  if resp.status == 404:
                      return True
                  text = await resp.text()
                  low_text = text.lower()
                  session_error = resp.status in (401, 403, 407, 429)
                  session_error = session_error or any(
                      marker in low_text
                      for marker in (
                          'login_required', 'challengerequired',
                          '/accounts/login', '/challenge/',
                          'please wait a few minutes', 'rate limit',
                          'temporarily blocked', 'checkpoint_required',
                      )
                  )
                  if resp.status != 200 or session_error:
                      raise RuntimeError("Instagram session rejected")

                  banned_phrases = [
                      "sorry, this page isn't available",
                      "the link you followed may be broken",
                      "user not found", "this account is banned",
                      "account has been banned", "page not found",
                      'is_banned":true', 'is_disabled":true',
                      'is_banned": true', 'is_disabled": true',
                  ]
                  if any(phrase in low_text for phrase in banned_phrases):
                      return True
                  if '"profilePage_' in text or '"user_id"' in text or 'edge_followed_by' in text:
                      return '"is_banned":true' in text or '"is_disabled":true' in text
                  if 'window.__INITIAL_STATE__' in text:
                      try:
                          json_str = text.split('window.__INITIAL_STATE__=')[1].split(';</script>')[0]
                          user_data = json.loads(json_str).get("user", {})
                          return bool(user_data.get("is_banned") or user_data.get("is_disabled"))
                      except (IndexError, json.JSONDecodeError, AttributeError):
                          return None
                  return None
          except RuntimeError:
              line_number = retire_session(session_id)
              await notify_retired_session(bot, line_number)
          except Exception:
              return None
      return None

  def get_db_connection():
      turso_url = os.getenv("TURSO_DB_URL", "").strip()
      turso_token = os.getenv("TURSO_AUTH_TOKEN", "").strip()
      if turso_url and turso_token:
          candidate_modules = [
              "libsql",
              "libsql_client",
              "turso",
          ]
          for module_name in candidate_modules:
              try:
                  module = importlib.import_module(module_name)
              except Exception:
                  continue

              connect_func = getattr(module, "connect", None)
              if callable(connect_func):
                  try:
                      return connect_func(turso_url, auth_token=turso_token)
                  except TypeError:
                      try:
                          return connect_func(turso_url, token=turso_token)
                      except TypeError:
                          pass

              client_cls = getattr(module, "Client", None)
              if callable(client_cls):
                  try:
                      return client_cls(url=turso_url, auth_token=turso_token)
                  except TypeError:
                      try:
                          return client_cls(turso_url, turso_token)
                      except TypeError:
                          pass
      return sqlite3.connect(DB_PATH, timeout=10)

  def init_db():
      conn = get_db_connection()
      use_libsql = not hasattr(conn, "cursor")

      def execute(query, params=()):
          if use_libsql:
              return conn.execute(query, params)
          c = conn.cursor()
          c.execute(query, params)
          return c

      def fetchall(result):
          if use_libsql:
              return getattr(result, "rows", [])
          return result.fetchall()

      def fetchone(result):
          if use_libsql:
              rows = getattr(result, "rows", [])
              return rows[0] if rows else None
          return result.fetchone()

      execute('''CREATE TABLE IF NOT EXISTS monitors
      (id INTEGER PRIMARY KEY AUTOINCREMENT,
      chat_id INTEGER NOT NULL,
      username TEXT NOT NULL UNIQUE,
      added_at REAL NOT NULL,
      last_status INTEGER DEFAULT 0,
      last_full_name TEXT)''')
      execute('''CREATE TABLE IF NOT EXISTS settings
      (chat_id INTEGER PRIMARY KEY,
      lang TEXT DEFAULT 'ar')''')
      execute('''CREATE TABLE IF NOT EXISTS chats
      (chat_id INTEGER PRIMARY KEY,
      chat_type TEXT NOT NULL,
      title TEXT,
      username TEXT,
      last_seen REAL NOT NULL)''')
      execute('''CREATE TABLE IF NOT EXISTS access_grants
      (user_id INTEGER PRIMARY KEY,
       user_label TEXT NOT NULL DEFAULT '',
       expires_at REAL NOT NULL DEFAULT 0,
       slow_limit INTEGER NOT NULL DEFAULT 15,
       fast_limit INTEGER NOT NULL DEFAULT 5,
       active INTEGER NOT NULL DEFAULT 1,
       fast_enabled INTEGER NOT NULL DEFAULT 0,
       created_at REAL NOT NULL)''')

      # Add new monitor metadata without destroying an existing database.
      table_info = execute("PRAGMA table_info(monitors)")
      monitor_columns = {row[1] for row in fetchall(table_info)}
      if "added_by" not in monitor_columns:
          execute("ALTER TABLE monitors ADD COLUMN added_by INTEGER NOT NULL DEFAULT 0")
      if "scan_interval" not in monitor_columns:
          execute("ALTER TABLE monitors ADD COLUMN scan_interval INTEGER NOT NULL DEFAULT 30")
      if "last_checked_at" not in monitor_columns:
          execute("ALTER TABLE monitors ADD COLUMN last_checked_at REAL NOT NULL DEFAULT 0")
      table_info = execute("PRAGMA table_info(access_grants)")
      access_columns = {row[1] for row in fetchall(table_info)}
      access_columns_to_add = {
          "user_label": "TEXT NOT NULL DEFAULT ''",
          "expires_at": "REAL NOT NULL DEFAULT 0",
          "slow_limit": "INTEGER NOT NULL DEFAULT 15",
          "fast_limit": "INTEGER NOT NULL DEFAULT 5",
          "active": "INTEGER NOT NULL DEFAULT 1",
          "fast_enabled": "INTEGER NOT NULL DEFAULT 0",
          "created_at": "REAL NOT NULL DEFAULT 0",
      }
      for column, definition in access_columns_to_add.items():
          if column not in access_columns:
              execute(f"ALTER TABLE access_grants ADD COLUMN {column} {definition}")

      execute(
          "CREATE TABLE IF NOT EXISTS app_meta "
          "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
      )
      legacy_row = fetchone(
          execute(
              "SELECT value FROM app_meta WHERE key = ?",
              ("legacy_expiry_migrated",),
          )
      )
      if legacy_row is None:
          # Old records created by the previous activation flow used zero
          # expiry. Convert them once, without extending them on every restart.
          execute(
              "UPDATE access_grants SET expires_at = ? WHERE expires_at = 0",
              (time.time() + LEGACY_ACTIVATION_DAYS * 86400,),
          )
          execute(
              "INSERT INTO app_meta (key, value) VALUES (?, ?)",
              ("legacy_expiry_migrated", str(int(time.time()))),
          )
      execute(
          "UPDATE monitors SET scan_interval = ? WHERE scan_interval = 5",
          (FAST_SCAN_INTERVAL,),
      )
      execute("UPDATE monitors SET added_by = ? WHERE added_by = 0", (OWNER_ID,))
      if hasattr(conn, "commit"):
          conn.commit()
      if hasattr(conn, "close"):
          conn.close()


  def register_chat(chat):
      if not chat:
          return
      title = getattr(chat, "title", None)
      username = getattr(chat, "username", None)
      conn = sqlite3.connect(DB_PATH, timeout=10)
      c = conn.cursor()
      c.execute(
          "INSERT INTO chats (chat_id, chat_type, title, username, last_seen) "
          "VALUES (?, ?, ?, ?, ?) "
          "ON CONFLICT(chat_id) DO UPDATE SET "
          "chat_type = excluded.chat_type, title = excluded.title, "
          "username = excluded.username, last_seen = excluded.last_seen",
          (chat.id, chat.type, title, username, time.time()),
      )
      conn.commit()
      conn.close()


  async def track_chat(update, context):
      register_chat(update.effective_chat)


  def get_broadcast_recipients():
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute(
          "SELECT chat_id FROM chats "
          "UNION SELECT chat_id FROM settings "
          "UNION SELECT chat_id FROM monitors "
          "ORDER BY chat_id"
      )
      chat_ids = [row[0] for row in c.fetchall()]
      conn.close()
      return chat_ids


  def get_lang(chat_id):
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute("SELECT lang FROM settings WHERE chat_id = ?", (chat_id,))
      row = c.fetchone()
      conn.close()
      return row[0] if row else None

  def set_lang(chat_id, lang):
      lang = lang if lang in T else "ar"
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute(
          "INSERT INTO settings (chat_id, lang) VALUES (?, ?) "
          "ON CONFLICT(chat_id) DO UPDATE SET lang = excluded.lang",
          (chat_id, lang)
      )
      conn.commit()
      conn.close()

  def lang_or_default(chat_id):
      return get_lang(chat_id) or "ar"

  def add_monitor(chat_id, username, initial_status, added_by=OWNER_ID, fast=False):
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute("SELECT id FROM monitors WHERE username = ?", (username,))
      if c.fetchone():
          conn.close()
          return False
      c.execute(
          "INSERT INTO monitors "
          "(chat_id, username, added_at, last_status, added_by, scan_interval, last_checked_at) "
          "VALUES (?, ?, ?, ?, ?, ?, ?)",
           (chat_id, username, time.time(), initial_status, added_by, FAST_SCAN_INTERVAL if fast else 30, 0),
      )
      conn.commit()
      conn.close()
      return True

  def remove_monitor(username, requester_id=None, requester_is_admin=False):
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      if requester_is_admin:
          c.execute("DELETE FROM monitors WHERE username = ?", (username,))
      else:
          c.execute(
              "DELETE FROM monitors WHERE username = ? AND added_by = ?",
              (username, requester_id),
          )
      deleted = c.rowcount > 0
      conn.commit()
      conn.close()
      return deleted

  def get_all_monitors():
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute(
          "SELECT chat_id, username, last_status, scan_interval, last_checked_at "
          "FROM monitors"
      )
      rows = c.fetchall()
      conn.close()
      return rows


  def get_saved_usernames():
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute("SELECT username FROM monitors ORDER BY username COLLATE NOCASE")
      usernames = [row[0] for row in c.fetchall()]
      conn.close()
      return usernames


  def update_monitor_status(username, new_status):
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute("UPDATE monitors SET last_status = ? WHERE username = ?", (new_status, username))
      conn.commit()
      conn.close()


  def update_monitor_checked(username, checked_at):
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute(
          "UPDATE monitors SET last_checked_at = ? WHERE username = ?",
          (checked_at, username),
      )
      conn.commit()
      conn.close()


  def get_access_grant(user_id):
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute(
          "SELECT user_id, user_label, expires_at, slow_limit, fast_limit, active, fast_enabled "
          "FROM access_grants WHERE user_id = ?",
          (user_id,),
      )
      row = c.fetchone()
      conn.close()
      if not row:
          return None
      expires_at = row[2]
      active = bool(row[5]) and (not expires_at or expires_at > time.time())
      return {
          "user_id": row[0],
          "user_label": row[1],
          "expires_at": expires_at,
          "slow_limit": row[3],
          "fast_limit": row[4],
          "active": active,
          "fast_enabled": bool(row[6]) and active,
      }


  def activate_user(user_id, user_label, slow_limit, fast_limit, duration_days):
      user_label = user_label.strip()
      expires_at = time.time() + (duration_days * 86400)
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute(
          "INSERT INTO access_grants "
          "(user_id, user_label, expires_at, slow_limit, fast_limit, active, fast_enabled, created_at) "
          "VALUES (?, ?, ?, ?, ?, 1, ?, ?) "
          "ON CONFLICT(user_id) DO UPDATE SET "
          "user_label = excluded.user_label, expires_at = excluded.expires_at, active = 1, "
          "slow_limit = excluded.slow_limit, fast_limit = excluded.fast_limit, "
          "fast_enabled = excluded.fast_enabled, created_at = excluded.created_at",
          (
              user_id,
              user_label,
              expires_at,
              slow_limit,
              fast_limit,
              1 if fast_limit > 0 else 0,
              time.time(),
          ),
      )
      conn.commit()
      conn.close()


  def revoke_access(user_id):
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      try:
          c.execute("BEGIN")
          c.execute("DELETE FROM monitors WHERE added_by = ?", (user_id,))
          monitors_deleted = c.rowcount
          c.execute("DELETE FROM access_grants WHERE user_id = ?", (user_id,))
          grant_deleted = c.rowcount
          conn.commit()
          return bool(monitors_deleted or grant_deleted)
      except Exception:
          conn.rollback()
          raise
      finally:
          conn.close()


  def get_access_rows():
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute(
          "SELECT user_id, user_label, expires_at, slow_limit, fast_limit, active, fast_enabled "
          "FROM access_grants ORDER BY user_id"
      )
      rows = c.fetchall()
      conn.close()
      return rows


  async def resolve_user_display(bot, user_id, lang="ar", stored_label=None):
      """Return the saved username/name, then Telegram profile data as a fallback."""
      if stored_label and stored_label.strip():
          return escape_markdown(stored_label.strip())

      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute("SELECT username FROM chats WHERE chat_id = ?", (user_id,))
      row = c.fetchone()
      conn.close()
      username = row[0] if row and row[0] else None

      if not username and bot:
          try:
              chat = await bot.get_chat(user_id)
              username = getattr(chat, "username", None)
          except Exception:
              username = None

      if username:
          return f"@{escape_markdown(username)}"
      if bot:
          try:
              chat = await bot.get_chat(user_id)
              first_name = getattr(chat, "first_name", None)
              last_name = getattr(chat, "last_name", None)
              full_name = " ".join(part for part in (first_name, last_name) if part)
              if full_name:
                  return escape_markdown(full_name)
          except Exception:
              pass
      return "الاسم غير مسجل" if lang == "ar" else "Name not registered"


  def get_usage(user_id, fast):
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute(
          "SELECT COUNT(*) FROM monitors WHERE added_by = ? AND scan_interval = ?",
          (user_id, FAST_SCAN_INTERVAL if fast else 30),
      )
      used = c.fetchone()[0]
      conn.close()
      return used


  def get_user_limits(user_id):
      if user_is_admin(user_id):
          return 10**9, 10**9
      grant = get_access_grant(user_id)
      if not grant or not grant["active"]:
          return 0, 0
      return max(0, grant["slow_limit"]), max(0, grant["fast_limit"])


  def get_user_monitor_count(user_id):
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute("SELECT COUNT(*) FROM monitors WHERE added_by = ?", (user_id,))
      used = c.fetchone()[0]
      conn.close()
      return used


  def get_fast_remaining(user_id):
      _, fast_limit = get_user_limits(user_id)
      return max(0, fast_limit - get_usage(user_id, True))


  def new_usernames_for_user(usernames):
      if not usernames:
          return []
      placeholders = ",".join("?" for _ in usernames)
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute(
          f"SELECT username FROM monitors WHERE lower(username) IN "
          f"({','.join('lower(?)' for _ in usernames)})",
          tuple(usernames),
      )
      existing = {row[0].lower() for row in c.fetchall()}
      conn.close()
      return [username for username in usernames if username.lower() not in existing]


  def normalize_username(value):
      """Return a canonical Instagram username or None for invalid input."""
      value = (value or "").strip()
      if value.startswith("@"):
          value = value[1:]
      if not INSTAGRAM_USERNAME_RE.fullmatch(value):
          return None
      return value.lower()


  def parse_usernames(text: str):
      """Split raw text into clean, valid, deduplicated usernames."""
      if not text:
          return []
      raw = re.split(r'[\s,]+', text.strip())
      seen = set()
      result = []
      for item in raw:
          u = normalize_username(item)
          if not u:
              continue
          if u in seen:
              continue
          seen.add(u)
          result.append(u)
      return result


  def set_pending_action(context, chat_id, action):
      context.user_data["awaiting_action"] = action
      context.user_data["awaiting_chat_id"] = chat_id


  def get_pending_action(context, chat_id):
      if context.user_data.get("awaiting_chat_id") != chat_id:
          return None
      return context.user_data.get("awaiting_action")


  def clear_pending_action(context):
      context.user_data.pop("awaiting_action", None)
      context.user_data.pop("awaiting_chat_id", None)


  async def monitor_loop(application):
      await asyncio.sleep(5)
      session = application.bot_data.get("http_session")
      if not session or not application.bot_data.get("instagram_ready"):
          return
      sem = asyncio.Semaphore(5)

      while True:
          try:
               monitors = get_all_monitors()
               if monitors:
                   now = time.time()
                   for chat_id, username, last_status, scan_interval, last_checked_at in monitors:
                       if last_checked_at and now - last_checked_at < scan_interval:
                           continue
                       async with sem:
                           current_banned = await fetch_profile_info(session, username, application.bot)
                           update_monitor_checked(username, time.time())
                           if current_banned is None:
                               # Inconclusive check (rate limit / blocked / odd
                               # response) - keep the previous status instead
                               # of guessing, and try again next cycle.
                               continue
                           new_status = 1 if current_banned else 0

                           if new_status != last_status:
                               update_monitor_status(username, new_status)
                               current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                               profile_link = f"https://instagram.com/{username}"

                               for target_chat in list(set([chat_id, NOTIFICATION_GROUP_ID])):
                                   t_lang = lang_or_default(target_chat)
                                   keyboard = [[InlineKeyboardButton(tr(t_lang, "btn_open_ig"), url=profile_link)]]
                                   reply_markup = InlineKeyboardMarkup(keyboard)
                                   key = "ban_alert" if new_status == 1 else "unban_alert"
                                   caption = tr(t_lang, key, username=escape_markdown(username), time=current_time) + rights_text(t_lang)
                                   gif_url = BAN_GIF_URL if new_status == 1 else UNBAN_GIF_URL
                                   try:
                                       await application.bot.send_animation(target_chat, gif_url, caption=caption, parse_mode="Markdown", reply_markup=reply_markup)
                                   except:
                                       try:
                                           await application.bot.send_message(target_chat, caption, parse_mode="Markdown", reply_markup=reply_markup)
                                       except:
                                           pass
                # The scheduler wakes often enough for 10-second monitors. Each
                # account still keeps its own 10s/30s interval above.
               await asyncio.sleep(1)
          except asyncio.CancelledError:
              break
          except Exception:
              try:
                   await asyncio.sleep(1)
              except asyncio.CancelledError:
                  break

  def is_admin(update):
      return bool(update.effective_user and (
          update.effective_user.id == OWNER_ID or
          update.effective_user.id in ADMIN_IDS
      ))


  def user_is_admin(user_id):
      return user_id == OWNER_ID or user_id in ADMIN_IDS


  def access_mode_allowed(user_id, fast=False):
      if user_is_admin(user_id):
          return True
      grant = get_access_grant(user_id)
      if not grant or not grant["active"]:
          return False
      if fast and (
          not grant or not grant["active"] or not grant["fast_enabled"] or grant["fast_limit"] <= 0
      ):
          return False
      if fast:
          return get_fast_remaining(user_id) > 0
      slow_limit, _ = get_user_limits(user_id)
      return get_usage(user_id, False) < slow_limit


  def active_access_exists(user_id):
      if user_is_admin(user_id):
          return True
      grant = get_access_grant(user_id)
      return bool(grant and grant["active"])


  def access_denial_key(user_id, fast=False):
      if user_is_admin(user_id):
          return None
      grant = get_access_grant(user_id)
      if not grant:
          return "access_required"
      if not grant["active"]:
          return "access_expired"
      if fast and (
          not grant or not grant["fast_enabled"] or grant["fast_limit"] <= 0
      ):
          return "fast_access_required"
      if fast and get_usage(user_id, True) >= get_user_limits(user_id)[1]:
          return "fast_quota_exceeded"
      if not fast and get_usage(user_id, False) >= get_user_limits(user_id)[0]:
          return "slow_quota_exceeded"
      return None


  async def require_access(update, lang, fast=False):
      user_id = update.effective_user.id
      denial_key = access_denial_key(user_id, fast)
      if not denial_key:
          return True
      kwargs = {}
      if denial_key == "slow_quota_exceeded":
          kwargs["remaining"] = max(0, get_user_limits(user_id)[0] - get_usage(user_id, False))
      elif denial_key == "fast_quota_exceeded":
          kwargs["remaining"] = get_fast_remaining(user_id)
      await update.message.reply_text(
          tr(lang, denial_key, **kwargs),
          parse_mode="Markdown",
      )
      return False


  async def require_any_access(update, lang):
      if active_access_exists(update.effective_user.id):
          return True
      await update.message.reply_text(tr(lang, "access_required"), parse_mode="Markdown")
      return False


  def quota_check(user_id, usernames, fast=False):
      """Return (allowed, remaining, denial_key) before a batch is scanned."""
      if user_is_admin(user_id):
          return True, 10**9, None
      grant = get_access_grant(user_id)
      if not grant:
          return False, 0, "access_required"
      if not grant["active"]:
          return False, 0, "access_expired"
      if fast and not grant["fast_enabled"]:
          return False, 0, "fast_access_required"
      new_count = len(new_usernames_for_user(usernames))
      used = get_usage(user_id, fast)
      limit = get_user_limits(user_id)[1 if fast else 0]
      remaining = max(0, limit - used)
      if new_count > remaining:
          return False, remaining, "fast_quota_exceeded" if fast else "slow_quota_exceeded"
      return True, remaining, None


  def build_admin_menu(lang):
      return InlineKeyboardMarkup([
          [
              create_button(tr(lang, "btn_admin"), callback_data="admin_panel", color="primary"),
              create_button(tr(lang, "btn_users"), callback_data="admin_users"),
          ],
          [
              create_button(tr(lang, "btn_add_choose"), callback_data="add_user", color="primary"),
              create_button(tr(lang, "btn_export"), callback_data="export_users"),
          ],
          [
              create_button(tr(lang, "btn_help"), callback_data="show_help"),
              create_button(tr(lang, "btn_language"), callback_data="choose_language"),
          ],
          [create_button(tr(lang, "btn_group"), url=GROUP_LINK, color="success")],
      ])


  def build_private_menu(lang, is_owner, has_access=False):
      btn_add = create_button(tr(lang, "btn_add"), color="primary", callback_data="add_user")
      btn_delete = create_button(tr(lang, "btn_delete"), color="danger", callback_data="delete_user")
      btn_group = create_button(tr(lang, "btn_group"), url=GROUP_LINK, color="success")
      btn_help = create_button(tr(lang, "btn_help"), callback_data="show_help")
      btn_language = create_button(tr(lang, "btn_language"), callback_data="choose_language")
      btn_myid = create_button(tr(lang, "btn_myid"), callback_data="show_myid")

      if is_owner:
          btn_check = create_button(tr(lang, "btn_check"), color="primary", callback_data="check_user")
          btn_list = create_button(tr(lang, "btn_list"), color="primary", callback_data="list_users")
          btn_india = create_button(tr(lang, "btn_india"), web_app_url=INDIAN_URL, color="primary", icon_emoji_id=EMOJI_ID_INDIAN)
          btn_brazil = create_button(tr(lang, "btn_brazil"), web_app_url=BRAZIL_URL, color="success", icon_emoji_id=EMOJI_ID_BRAZIL)
          btn_export = create_button(tr(lang, "btn_export"), callback_data="export_users")
          keyboard = [
              [btn_add, btn_delete],
              [btn_check, btn_list],
              [btn_india, btn_brazil],
              [btn_help, btn_language],
              [btn_export, btn_group]
          ]
      elif has_access:
          btn_check = create_button(tr(lang, "btn_check"), color="primary", callback_data="check_user")
          keyboard = [
              [btn_add, btn_delete],
              [btn_check, btn_help],
              [btn_language, btn_group],
          ]
      else:
          keyboard = [
              [btn_myid, btn_help],
              [btn_language, btn_group],
          ]
      return InlineKeyboardMarkup(keyboard)


  def build_add_interval_menu(lang, user_id):
      buttons = []
      if access_mode_allowed(user_id, fast=False):
          buttons.append(create_button(
              tr(lang, "btn_add_slow"),
              callback_data="select_add_slow",
              color="primary",
          ))
      if access_mode_allowed(user_id, fast=True):
          buttons.append(create_button(
              tr(lang, "btn_add_fast"),
              callback_data="select_add_fast",
              color="primary",
          ))

      rows = [[button] for button in buttons]
      rows.append([create_button(tr(lang, "btn_back"), callback_data="back_start")])
      return InlineKeyboardMarkup(rows)


  def build_admin_actions(lang):
      return InlineKeyboardMarkup([
          [
              create_button("تفعيل شخص" if lang == "ar" else "Activate person", callback_data="admin_activate", color="primary"),
              create_button("إلغاء تفعيل" if lang == "ar" else "Deactivate person", callback_data="admin_deactivate", color="danger"),
          ],
          [
              create_button("عرض التفعيلات" if lang == "ar" else "List activations", callback_data="admin_users"),
              create_button(tr(lang, "btn_export"), callback_data="export_users"),
          ],
          [create_button(tr(lang, "btn_back"), callback_data="back_start")],
      ])


  def build_group_menu(lang):
      return InlineKeyboardMarkup([
          [
              create_button(tr(lang, "btn_add"), callback_data="add_user", color="primary"),
              create_button(tr(lang, "btn_check"), callback_data="check_user", color="primary"),
          ],
          [
              create_button(tr(lang, "btn_delete"), callback_data="delete_user", color="danger"),
              create_button(tr(lang, "btn_language"), callback_data="choose_language"),
          ],
          [create_button(tr(lang, "btn_group"), url=GROUP_LINK, color="success")],
      ])


  async def send_private_start(update, context, lang):
      chat_id = update.effective_chat.id
      user_id = update.effective_user.id
      is_admin_user = user_is_admin(user_id)
      is_owner = user_id == OWNER_ID
      has_access = access_mode_allowed(user_id, fast=False) or access_mode_allowed(user_id, fast=True)
      reply_markup = build_admin_menu(lang) if is_admin_user else build_private_menu(lang, is_owner, has_access)
      caption = tr(lang, "start_private") + rights_text(lang)
      try:
          await context.bot.send_animation(
              chat_id=chat_id,
              animation=OWNER_START_GIF_URL if is_owner else MONITOR_START_GIF_URL,
              caption=caption,
              parse_mode="Markdown",
              reply_markup=reply_markup
          )
      except Exception:
          await context.bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=reply_markup)


  async def send_group_start(update, context, lang):
      chat_id = update.effective_chat.id
      caption = tr(lang, "start_group") + rights_text(lang)
      reply_markup = build_group_menu(lang)
      try:
          await context.bot.send_animation(
              chat_id,
              MONITOR_START_GIF_URL,
              caption=caption,
              parse_mode="Markdown",
              reply_markup=reply_markup,
          )
      except Exception:
          await context.bot.send_message(
              chat_id,
              caption,
              parse_mode="Markdown",
              reply_markup=reply_markup,
          )


  async def ask_language(update, context):
      keyboard = InlineKeyboardMarkup([[
          InlineKeyboardButton(T["ar"]["btn_lang_ar"], callback_data="lang_ar"),
          InlineKeyboardButton(T["en"]["btn_lang_en"], callback_data="lang_en"),
      ]])
      text = "اختر لغتك / Choose your language:"
      if update.message:
          await update.message.reply_text(text, reply_markup=keyboard)
      else:
          await update.effective_chat.send_message(text, reply_markup=keyboard)


  async def start(update, context):
      chat_id = update.effective_chat.id
      chat_type = update.effective_chat.type

      if chat_type in ("group", "supergroup"):
          lang = get_lang(chat_id)
          if lang is None:
              lang = "ar"
              set_lang(chat_id, lang)
          await send_group_start(update, context, lang)
          return

      lang = get_lang(chat_id)
      if lang is None:
          await ask_language(update, context)
          return

      await send_private_start(update, context, lang)


  async def language_command(update, context):
      await ask_language(update, context)


  async def help_command(update, context):
      chat_id = update.effective_chat.id
      lang = lang_or_default(chat_id)
      help_text = tr(lang, "help_text")
      if update.effective_user and user_is_admin(update.effective_user.id):
          help_text += "\n\n" + tr(lang, "admin_help_text")
      help_text += rights_text(lang)
      keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(tr(lang, "btn_back"), callback_data="back_start")]])

      if update.callback_query:
          try:
              await update.callback_query.edit_message_caption(caption=help_text, parse_mode="Markdown", reply_markup=keyboard)
          except Exception:
              await update.callback_query.message.reply_text(help_text, parse_mode="Markdown", reply_markup=keyboard)
      else:
          await update.message.reply_text(help_text, parse_mode="Markdown")

  async def chk_command(update, context):
      lang = lang_or_default(update.effective_chat.id)
      if not await require_any_access(update, lang):
          return
      if len(context.args) != 1:
          await update.message.reply_text(tr(lang, "chk_usage"), parse_mode="Markdown")
          return
      username = normalize_username(context.args[0])
      if not username:
          await update.message.reply_text(tr(lang, "invalid_username"), parse_mode="Markdown")
          return
      wait_msg = await update.message.reply_text(
          tr(lang, "chk_wait", username=escape_markdown(username)),
          parse_mode="Markdown",
      )
      session = context.application.bot_data.get("http_session")
      if not session:
          await wait_msg.edit_text(tr(lang, "chk_error"), parse_mode="Markdown")
          return

      is_banned = await fetch_profile_info(session, username, context.bot)
      current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      profile_link = f"https://instagram.com/{username}"
      reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(tr(lang, "btn_open_ig"), url=profile_link)]])

      status_str = tr(lang, "status_banned") if is_banned else tr(lang, "status_active")
      caption = tr(
          lang,
          "chk_result",
          username=escape_markdown(username),
          status=status_str,
          time=current_time,
      ) + rights_text(lang)
      gif_url = BAN_GIF_URL if is_banned else UNBAN_GIF_URL

      try:
          await wait_msg.delete()
          await context.bot.send_animation(update.effective_chat.id, gif_url, caption=caption, parse_mode="Markdown", reply_markup=reply_markup)
      except Exception:
          await wait_msg.edit_text(caption, parse_mode="Markdown", reply_markup=reply_markup)


  async def run_multi_add(session, chat_id, usernames, sem, added_by, bot=None, fast=False):
      async def one(u):
          async with sem:
              is_banned = await fetch_profile_info(session, u, bot)
              # If the check was inconclusive, add it as active for now -
              # the monitor loop will re-check and correct the status soon,
              # instead of us falsely reporting a brand-new account as banned.
              is_banned_resolved = bool(is_banned) if is_banned is not None else False
              added = add_monitor(
                  chat_id,
                  u,
                  1 if is_banned_resolved else 0,
                  added_by=added_by,
                  fast=fast,
              )
              return u, added, is_banned_resolved
      return await asyncio.gather(*[one(u) for u in usernames])


  async def run_multi_delete(usernames, requester_id, requester_is_admin=False):
      results = []
      for u in usernames:
          results.append((u, remove_monitor(u, requester_id, requester_is_admin)))
      return results


  def format_add_results(lang, results):
      lines = [tr(lang, "add_result_header")]
      for username, added, is_banned in results:
          if added:
              status = tr(lang, "status_banned") if is_banned else tr(lang, "status_active")
              lines.append(tr(lang, "add_line_added", username=escape_markdown(username), status=status))
          else:
              lines.append(tr(lang, "add_line_exists", username=escape_markdown(username)))
      return "\n".join(lines)


  def format_delete_results(lang, results):
      lines = [tr(lang, "delete_result_header")]
      for username, removed in results:
          if removed:
              lines.append(tr(lang, "delete_line_removed", username=escape_markdown(username)))
          else:
              lines.append(tr(lang, "delete_line_notfound", username=escape_markdown(username)))
      return "\n".join(lines)


  async def add_command(update, context):
      lang = lang_or_default(update.effective_chat.id)
      if not await require_access(update, lang):
          return
      if not context.args:
          await update.message.reply_text(tr(lang, "add_usage"), parse_mode="Markdown")
          return
      usernames = parse_usernames(" ".join(context.args))
      if not usernames:
          await update.message.reply_text(tr(lang, "add_usage"), parse_mode="Markdown")
          return
      if len(usernames) > MAX_USERNAMES_PER_BATCH:
          await update.message.reply_text(tr(lang, "too_many", max=MAX_USERNAMES_PER_BATCH), parse_mode="Markdown")
          return

      await process_add_batch(update, context, lang, usernames, fast=False)


  async def add_fast_command(update, context):
      lang = lang_or_default(update.effective_chat.id)
      if not await require_access(update, lang, fast=True):
          return
      if not context.args:
          await update.message.reply_text(tr(lang, "add_usage") + "\n/addfast user1 user2", parse_mode="Markdown")
          return
      usernames = parse_usernames(" ".join(context.args))
      if not usernames:
          await update.message.reply_text(tr(lang, "add_usage"), parse_mode="Markdown")
          return
      if len(usernames) > MAX_USERNAMES_PER_BATCH:
          await update.message.reply_text(tr(lang, "too_many", max=MAX_USERNAMES_PER_BATCH), parse_mode="Markdown")
          return
      await process_add_batch(update, context, lang, usernames, fast=True)

  async def delete_command(update, context):
      lang = lang_or_default(update.effective_chat.id)
      if not await require_any_access(update, lang):
          return
      if not context.args:
          await update.message.reply_text(tr(lang, "delete_usage"), parse_mode="Markdown")
          return
      usernames = parse_usernames(" ".join(context.args))
      if not usernames:
          await update.message.reply_text(tr(lang, "delete_usage"), parse_mode="Markdown")
          return
      results = await run_multi_delete(
          usernames,
          update.effective_user.id,
          user_is_admin(update.effective_user.id),
      )
      await reply_long(
          update.message,
          format_delete_results(lang, results) + rights_text(lang),
      )

  async def status_command(update, context):
      lang = lang_or_default(update.effective_chat.id)
      if not is_admin(update):
          await update.message.reply_text(tr(lang, "status_admin_only"), parse_mode="Markdown")
          return
      chat_id = update.effective_chat.id
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute("SELECT username, last_status, added_at FROM monitors WHERE chat_id = ?", (chat_id,))
      rows = c.fetchall()
      conn.close()
      if not rows:
          await update.message.reply_text(tr(lang, "status_empty"), parse_mode="Markdown")
          return
      msg = tr(lang, "status_header")
      for username, last_status, added_at in rows:
          status = tr(lang, "status_banned") if last_status == 1 else tr(lang, "status_active")
          added_date = time.strftime('%Y-%m-%d %H:%M', time.localtime(added_at))
          msg += f"@{escape_markdown(username)} -> {status} ({added_date})\n"

      msg += rights_text(lang)
      await reply_long(update.message, msg)


  async def send_saved_usernames(chat_id, lang, context):
      usernames = get_saved_usernames()
      if not usernames:
          await context.bot.send_message(chat_id, tr(lang, "export_empty"), parse_mode="Markdown")
          return

      file_content = ("\n".join(usernames) + "\n").encode("utf-8")
      document = InputFile(io.BytesIO(file_content), filename="saved_usernames.txt")
      await context.bot.send_document(
          chat_id=chat_id,
          document=document,
          caption=tr(lang, "export_caption"),
      )


  async def export_command(update, context):
      lang = lang_or_default(update.effective_chat.id)
      if not is_admin(update):
          await update.message.reply_text(tr(lang, "devs_only"), parse_mode="Markdown")
          return
      await send_saved_usernames(update.effective_chat.id, lang, context)


  async def broadcast_command(update, context):
      lang = lang_or_default(update.effective_chat.id)
      if not is_admin(update):
          await update.message.reply_text(tr(lang, "devs_only"), parse_mode="Markdown")
          return

      message = " ".join(context.args).strip()
      if not message:
          await update.message.reply_text(tr(lang, "broadcast_usage"), parse_mode="Markdown")
          return

      status_message = await update.message.reply_text(tr(lang, "broadcast_started"))
      sent = 0
      failed = 0
      for chat_id in get_broadcast_recipients():
          try:
              await context.bot.send_message(chat_id=chat_id, text=message)
              sent += 1
          except Exception:
              failed += 1
          await asyncio.sleep(0.05)

      await status_message.edit_text(
          tr(lang, "broadcast_done", sent=sent, failed=failed)
      )


  def format_expiry(expires_at, lang):
      if not expires_at:
          return "غير محددة" if lang == "ar" else "not set"
      return time.strftime("%Y-%m-%d %H:%M", time.localtime(expires_at))


  def format_fast_summary(lang, fast_used, fast_limit, fast_enabled):
      if not fast_enabled or fast_limit <= 0:
          return "غير مفعّلة" if lang == "ar" else "disabled"
      return (
          f"{fast_used}/{fast_limit}"
          if lang == "ar"
          else f"{fast_used}/{fast_limit}"
      )


  async def format_access_users(lang, bot):
      rows = get_access_rows()
      if not rows:
          return tr(lang, "users_empty")
      lines = [tr(lang, "users_header")]
      for user_id, user_label, expires_at, slow_limit, fast_limit, active, fast_enabled in rows:
          slow_used = get_usage(user_id, fast=False)
          fast_used = get_usage(user_id, fast=True)
          user_display = await resolve_user_display(bot, user_id, lang, user_label)
          lines.append(
              tr(
                  lang,
                  "access_status_line",
                  user_id=user_id,
                  user_label=user_display,
                  expires_at=format_expiry(expires_at, lang),
                  slow_limit=slow_limit,
                  slow_used=slow_used,
                  fast_used=fast_used,
                  active=(
                      "نعم" if active else "لا"
                  ) if lang == "ar" else (
                      "yes" if active else "no"
                  ),
                  fast_summary=format_fast_summary(lang, fast_used, fast_limit, fast_enabled),
              )
          )
      return "\n".join(lines)


  async def myid_command(update, context):
      lang = lang_or_default(update.effective_chat.id)
      await update.message.reply_text(
          tr(lang, "my_id", user_id=update.effective_user.id),
          parse_mode="Markdown",
      )


  async def admin_command(update, context):
      lang = lang_or_default(update.effective_chat.id)
      if not is_admin(update):
          await update.message.reply_text(tr(lang, "devs_only"), parse_mode="Markdown")
          return
      await update.message.reply_text(
          tr(lang, "admin_panel") + rights_text(lang),
          parse_mode="Markdown",
          reply_markup=build_admin_actions(lang),
      )


  async def users_command(update, context):
      lang = lang_or_default(update.effective_chat.id)
      if not is_admin(update):
          await update.message.reply_text(tr(lang, "devs_only"), parse_mode="Markdown")
          return
      await reply_long(
          update.message,
          (await format_access_users(lang, context.bot)) + rights_text(lang),
      )


  async def sessions_command(update, context):
      lang = lang_or_default(update.effective_chat.id)
      if not is_admin(update):
          await update.message.reply_text(tr(lang, "devs_only"), parse_mode="Markdown")
          return
      statuses = context.application.bot_data.get("session_statuses", [])
      working = sum(1 for item in statuses if item["working"])
      await update.message.reply_text(
          tr(
              lang,
              "sessions_status",
              working=working,
              total=len(statuses),
              failed=max(0, len(statuses) - working),
          ),
      )


  async def begin_activation(update, context):
      lang = lang_or_default(update.effective_chat.id)
      if not is_admin(update):
          await update.message.reply_text(tr(lang, "devs_only"), parse_mode="Markdown")
          return
      set_pending_action(context, update.effective_chat.id, "admin_activate_step")
      context.user_data["activation"] = {"step": "user_id"}
      await update.message.reply_text(
          tr(lang, "admin_grant_prompt"),
          parse_mode="Markdown",
      )


  async def activate_command(update, context):
      await begin_activation(update, context)


  async def active_command(update, context):
      await begin_activation(update, context)


  async def deactivate_command(update, context):
      lang = lang_or_default(update.effective_chat.id)
      if not is_admin(update):
          await update.message.reply_text(tr(lang, "devs_only"), parse_mode="Markdown")
          return
      if len(context.args) != 1:
          await update.message.reply_text(tr(lang, "revoke_usage"), parse_mode="Markdown")
          return
      try:
          user_id = int(context.args[0])
          if user_id <= 0:
              raise ValueError
      except ValueError:
          await update.message.reply_text(tr(lang, "revoke_usage"), parse_mode="Markdown")
          return
      grant = get_access_grant(user_id)
      if not revoke_access(user_id):
          await update.message.reply_text(tr(lang, "user_not_found"), parse_mode="Markdown")
          return
      user_display = await resolve_user_display(
          context.bot,
          user_id,
          lang,
          grant.get("user_label") if grant else None,
      )
      await update.message.reply_text(
          tr(
              lang,
              "revoke_success",
              user_id=user_id,
              user_label=user_display,
          ),
          parse_mode="Markdown",
      )


  async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
      query = update.callback_query
      await query.answer()

      user_id = query.from_user.id
      chat_id = query.message.chat_id
      data = query.data

      if data == "choose_language":
          await ask_language(update, context)
          return

      if data in ("lang_ar", "lang_en"):
          lang = "ar" if data == "lang_ar" else "en"
          set_lang(chat_id, lang)
          if query.message.chat.type in ("group", "supergroup"):
              await query.message.reply_text(
                  tr(lang, "language_saved"),
                  reply_markup=build_group_menu(lang),
              )
          else:
              await send_private_start(update, context, lang)
          return

      lang = lang_or_default(chat_id)

      if data == "show_help":
          await help_command(update, context)
          return
      elif data == "back_start":
          if query.message.chat.type in ("group", "supergroup"):
              await send_group_start(update, context, lang)
          else:
              await send_private_start(update, context, lang)
          return

      if data == "show_myid":
          await query.message.reply_text(
              tr(lang, "my_id", user_id=user_id),
              parse_mode="Markdown",
          )
          return

      admin_actions = {
          "admin_panel",
           "admin_activate",
           "admin_deactivate",
          "admin_users",
          "export_users",
          "list_users",
      }
      if data in admin_actions:
          if not user_is_admin(user_id):
              await query.message.reply_text(tr(lang, "devs_only"), parse_mode="Markdown")
              return
          if data == "admin_panel":
              await query.message.reply_text(
                  tr(lang, "admin_panel") + rights_text(lang),
                  parse_mode="Markdown",
                  reply_markup=build_admin_actions(lang),
              )
          elif data == "admin_users":
               await reply_long(
                   query.message,
                   (await format_access_users(lang, context.bot)) + rights_text(lang),
               )
          elif data == "admin_activate":
              set_pending_action(context, chat_id, "admin_activate_step")
              context.user_data["activation"] = {"step": "user_id"}
              await query.message.reply_text(tr(lang, "admin_grant_prompt"), parse_mode="Markdown")
          elif data == "admin_deactivate":
              set_pending_action(context, chat_id, "admin_deactivate")
              await query.message.reply_text(
                  tr(lang, "admin_revoke_prompt"),
                  parse_mode="Markdown",
              )
          elif data == "export_users":
              await send_saved_usernames(chat_id, lang, context)
          elif data == "list_users":
              await show_all_users(query.message, lang)
          return

      if data == "add_fast_user":
          if not access_mode_allowed(user_id, fast=True):
              key = access_denial_key(user_id, fast=True)
              kwargs = {}
              if key == "fast_quota_exceeded":
                  kwargs["remaining"] = get_fast_remaining(user_id)
              await query.message.reply_text(tr(lang, key, **kwargs), parse_mode="Markdown")
              return
          set_pending_action(context, chat_id, "add_fast")
          await query.message.reply_text(
              tr(lang, "prompt_add_fast"),
              parse_mode="Markdown",
          )
          return

      if data == "add_user":
          if not active_access_exists(user_id):
              await query.message.reply_text(tr(lang, "access_required"), parse_mode="Markdown")
              return
          interval_menu = build_add_interval_menu(lang, user_id)
          if len(interval_menu.inline_keyboard) == 1:
              await query.message.reply_text(tr(lang, "no_monitoring_options"), parse_mode="Markdown")
              return
          await query.message.reply_text(
              tr(lang, "prompt_add"),
              parse_mode="Markdown",
              reply_markup=interval_menu,
          )
          return

      if data in ("select_add_slow", "select_add_fast"):
          fast = data == "select_add_fast"
          if not access_mode_allowed(user_id, fast=fast):
              key = access_denial_key(user_id, fast=fast)
              kwargs = {}
              if key in ("slow_quota_exceeded", "fast_quota_exceeded"):
                  kwargs["remaining"] = max(
                      0,
                      get_fast_remaining(user_id) if fast else (
                          get_user_limits(user_id)[0] - get_usage(user_id, False)
                      ),
                  )
              await query.message.reply_text(tr(lang, key, **kwargs), parse_mode="Markdown")
              return
          set_pending_action(context, chat_id, "add_fast" if fast else "add")
          await query.message.reply_text(
              tr(lang, "prompt_add_fast" if fast else "prompt_add_slow"),
              parse_mode="Markdown",
          )
          return

      if data in ("delete_user", "check_user") and not active_access_exists(user_id):
          await query.message.reply_text(tr(lang, "access_required"), parse_mode="Markdown")
          return

      if data not in ["delete_user", "check_user"]:
          await query.message.reply_text(tr(lang, "button_expired"), parse_mode="Markdown")
          return

      if data == "delete_user":
          set_pending_action(context, chat_id, "delete")
          await query.message.reply_text(tr(lang, "prompt_delete"), parse_mode="Markdown")
      elif data == "check_user":
          set_pending_action(context, chat_id, "check")
          await query.message.reply_text(tr(lang, "prompt_check"), parse_mode="Markdown")

  async def show_all_users(message, lang):
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()
      c.execute("SELECT username, last_status, added_at FROM monitors")
      rows = c.fetchall()
      conn.close()
      if not rows:
          await message.reply_text(tr(lang, "list_empty"), parse_mode="Markdown")
          return
      msg = tr(lang, "list_header")
      for username, last_status, added_at in rows:
          status = tr(lang, "status_banned") if last_status == 1 else tr(lang, "status_active")
          added_date = time.strftime('%Y-%m-%d %H:%M', time.localtime(added_at))
          msg += f"@{escape_markdown(username)} -> {status} ({added_date})\n"

      msg += rights_text(lang)
      await reply_long(message, msg)


  async def cancel_command(update, context):
      if update.effective_chat.type not in ("private", "group", "supergroup"):
          return
      lang = lang_or_default(update.effective_chat.id)
      clear_pending_action(context)
      context.user_data.pop("activation", None)
      await update.message.reply_text(tr(lang, "cancelled"), parse_mode="Markdown")


  async def process_add_batch(update, context, lang, usernames, fast=False):
      if not usernames:
          await update.message.reply_text(tr(lang, "invalid_username"), parse_mode="Markdown")
          return
      if len(usernames) > MAX_USERNAMES_PER_BATCH:
          await update.message.reply_text(tr(lang, "too_many", max=MAX_USERNAMES_PER_BATCH), parse_mode="Markdown")
          return
      allowed, remaining, denial_key = quota_check(
          update.effective_user.id,
          usernames,
          fast=fast,
      )
      if not allowed:
          kwargs = {}
          if denial_key in ("slow_quota_exceeded", "fast_quota_exceeded"):
              kwargs["remaining"] = remaining
          await update.message.reply_text(
              tr(lang, denial_key, **kwargs),
              parse_mode="Markdown",
          )
          return
      session = context.application.bot_data.get("http_session")
      if not session:
          await update.message.reply_text(tr(lang, "add_error"), parse_mode="Markdown")
          return
      wait_msg = await update.message.reply_text(tr(lang, "add_wait", count=len(usernames)), parse_mode="Markdown")
      sem = asyncio.Semaphore(5)
      results = await run_multi_add(
          session,
          update.effective_chat.id,
          usernames,
          sem,
          added_by=update.effective_user.id,
          bot=context.bot,
          fast=fast,
      )
      await edit_and_reply_long(
          wait_msg,
          update.message,
          format_add_results(lang, results) + rights_text(lang),
      )


  async def process_delete_batch(update, context, lang, usernames):
      if not usernames:
          await update.message.reply_text(tr(lang, "invalid_username"), parse_mode="Markdown")
          return
      if not await require_any_access(update, lang):
          return
      results = await run_multi_delete(
          usernames,
          update.effective_user.id,
          user_is_admin(update.effective_user.id),
      )
      await reply_long(
          update.message,
          format_delete_results(lang, results) + rights_text(lang),
      )


  async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
      if update.effective_chat.type not in ("private", "group", "supergroup"):
          return

      chat_id = update.effective_chat.id
      lang = lang_or_default(chat_id)

      action = get_pending_action(context, chat_id)
      if not action:
          return

      text = (update.message.text or "").strip()
      if not text:
          await update.message.reply_text(tr(lang, "invalid_username"), parse_mode="Markdown")
          return

      if action == "admin_activate_step":
          if not user_is_admin(update.effective_user.id):
              clear_pending_action(context)
              context.user_data.pop("activation", None)
              await update.message.reply_text(tr(lang, "devs_only"), parse_mode="Markdown")
              return

          state = context.user_data.setdefault("activation", {"step": "user_id"})
          step = state.get("step")

          if step == "user_id":
              try:
                  user_id = int(text)
                  if user_id <= 0:
                      raise ValueError
              except ValueError:
                  await update.message.reply_text(tr(lang, "active_invalid"), parse_mode="Markdown")
                  return
              state["user_id"] = user_id
              state["step"] = "name"
              await update.message.reply_text(tr(lang, "active_prompt_name"), parse_mode="Markdown")
              return

          if step == "name":
              if len(text) > 100:
                  await update.message.reply_text(tr(lang, "active_invalid"), parse_mode="Markdown")
                  return
              state["user_label"] = text
              state["step"] = "slow_limit"
              await update.message.reply_text(tr(lang, "active_prompt_slow"), parse_mode="Markdown")
              return

          if step in ("slow_limit", "fast_limit", "duration_days"):
              try:
                  value = int(text)
              except ValueError:
                  await update.message.reply_text(tr(lang, "active_invalid"), parse_mode="Markdown")
                  return

              if step == "slow_limit":
                  if value < 0 or value > MAX_USERNAMES_PER_USER:
                      await update.message.reply_text(tr(lang, "active_invalid"), parse_mode="Markdown")
                      return
                  state["slow_limit"] = value
                  state["step"] = "fast_limit"
                  await update.message.reply_text(tr(lang, "active_prompt_fast"), parse_mode="Markdown")
                  return

              if step == "fast_limit":
                  if value < 0 or value > MAX_FAST_USERNAMES_PER_USER:
                      await update.message.reply_text(tr(lang, "active_invalid"), parse_mode="Markdown")
                      return
                  state["fast_limit"] = value
                  state["step"] = "duration_days"
                  await update.message.reply_text(tr(lang, "active_prompt_days"), parse_mode="Markdown")
                  return

              if value <= 0 or value > MAX_DURATION_DAYS:
                  await update.message.reply_text(tr(lang, "active_invalid"), parse_mode="Markdown")
                  return
              state["duration_days"] = value

              user_id = state["user_id"]
              user_label = state["user_label"]
              slow_limit = state["slow_limit"]
              fast_limit = state["fast_limit"]
              try:
                  activate_user(user_id, user_label, slow_limit, fast_limit, value)
              except Exception:
                  await update.message.reply_text(tr(lang, "activation_error"), parse_mode="Markdown")
                  return
              user_display = await resolve_user_display(context.bot, user_id, lang, user_label)
              slow_used = get_usage(user_id, fast=False)
              fast_summary = (
                  f"0/{fast_limit}"
                  if fast_limit > 0
                  else ("غير مفعّلة" if lang == "ar" else "disabled")
              )
              clear_pending_action(context)
              context.user_data.pop("activation", None)
              await update.message.reply_text(
                  tr(
                      lang,
                      "active_success",
                      user_id=user_id,
                      user_label=user_display,
                      duration_days=value,
                       slow_used=slow_used,
                      slow_limit=slow_limit,
                      fast_summary=fast_summary,
                  ),
                  parse_mode="Markdown",
              )
              return

      if action == "admin_deactivate":
          clear_pending_action(context)
          if not user_is_admin(update.effective_user.id):
              await update.message.reply_text(tr(lang, "devs_only"), parse_mode="Markdown")
              return
          try:
              user_id = int(text)
              if user_id <= 0:
                  raise ValueError
          except ValueError:
              await update.message.reply_text(tr(lang, "revoke_usage"), parse_mode="Markdown")
              return
          grant = get_access_grant(user_id)
          if not revoke_access(user_id):
              await update.message.reply_text(tr(lang, "user_not_found"), parse_mode="Markdown")
              return
          user_display = await resolve_user_display(
              context.bot,
              user_id,
              lang,
              grant.get("user_label") if grant else None,
          )
          await update.message.reply_text(
              tr(
                  lang,
                  "revoke_success",
                  user_id=user_id,
                  user_label=user_display,
              ),
              parse_mode="Markdown",
          )
          return

      if action in ('add', 'add_fast', 'delete'):
          usernames = parse_usernames(text)
          clear_pending_action(context)
          if action in ('add', 'add_fast'):
              await process_add_batch(update, context, lang, usernames, fast=(action == "add_fast"))
          else:
              await process_delete_batch(update, context, lang, usernames)
          return

      clear_pending_action(context)
      username = normalize_username(text)
      if not username:
          await update.message.reply_text(tr(lang, "invalid_username"), parse_mode="Markdown")
          return

      session = context.application.bot_data.get("http_session")
      if not session:
          await update.message.reply_text(tr(lang, "add_error"), parse_mode="Markdown")
          return

      if action == 'check':
          if not active_access_exists(update.effective_user.id):
              await update.message.reply_text(tr(lang, "access_required"), parse_mode="Markdown")
              return
          is_banned = await fetch_profile_info(session, username, context.bot)
          if is_banned is None:
              await update.message.reply_text(tr(lang, "chk_error"), parse_mode="Markdown")
              return
          status = tr(lang, "status_banned") if is_banned else tr(lang, "status_active")
          profile_link = f"https://instagram.com/{username}"
          reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(tr(lang, "btn_open_ig"), url=profile_link)]])
          await update.message.reply_text(
              tr(lang, "msg_check_result", username=escape_markdown(username), status=status) + rights_text(lang),
              reply_markup=reply_markup,
              parse_mode="Markdown"
          )


  async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
      if update.effective_chat.type not in ("private", "group", "supergroup"):
          return

      chat_id = update.effective_chat.id
      lang = lang_or_default(chat_id)
      action = get_pending_action(context, chat_id)
      if action not in ('add', 'add_fast', 'delete'):
          return

      document = update.message.document
      filename = (getattr(document, "file_name", None) or "").lower()
      if not document or not filename.endswith(".txt"):
          await update.message.reply_text(tr(lang, "file_invalid"), parse_mode="Markdown")
          return

      file_size = getattr(document, "file_size", None) or 0
      if file_size > MAX_TEXT_FILE_BYTES:
          await update.message.reply_text(
              tr(lang, "file_too_large", max_kb=MAX_TEXT_FILE_BYTES // 1024),
              parse_mode="Markdown",
          )
          return

      try:
          tg_file = await context.bot.get_file(document.file_id)
          file_bytes = await tg_file.download_as_bytearray()
          if len(file_bytes) > MAX_TEXT_FILE_BYTES:
              await update.message.reply_text(
                  tr(lang, "file_too_large", max_kb=MAX_TEXT_FILE_BYTES // 1024),
                  parse_mode="Markdown",
              )
              return
      except Exception:
          await update.message.reply_text(tr(lang, "file_error"), parse_mode="Markdown")
          return

      try:
          text = file_bytes.decode('utf-8')
      except UnicodeDecodeError:
          text = file_bytes.decode('utf-8', errors='ignore')

      usernames = parse_usernames(text)
      clear_pending_action(context)

      if action in ('add', 'add_fast'):
          await process_add_batch(update, context, lang, usernames, fast=(action == "add_fast"))
      else:
          await process_delete_batch(update, context, lang, usernames)

  async def checklogin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
      lang = lang_or_default(update.effective_chat.id)
      if update.effective_user.id != OWNER_ID:
          await update.message.reply_text(tr(lang, "checklogin_notallowed"), parse_mode="Markdown")
          return
      session = context.application.bot_data.get("http_session")
      if not session:
          await update.message.reply_text(tr(lang, "add_error"), parse_mode="Markdown")
          return
      username = await get_logged_in_username(session)
      if username:
          await update.message.reply_text(
              tr(lang, "checklogin_success", username=escape_markdown(username)) + rights_text(lang),
              parse_mode="Markdown",
          )
      else:
          await update.message.reply_text(tr(lang, "checklogin_fail") + rights_text(lang), parse_mode="Markdown")

  async def post_init(application):
      session = aiohttp.ClientSession()
      application.bot_data["http_session"] = session

      statuses = await verify_instagram_sessions(session, application.bot)
      application.bot_data["session_statuses"] = statuses
      application.bot_data["instagram_ready"] = bool(INSTAGRAM_SESSION_POOL)
      working = sum(1 for item in statuses if item["working"])
      print(f"Instagram sessions: {working}/{len(statuses)} working")
      for item in statuses:
          if item["working"]:
              print(f"Instagram session {item['index']}: working")
          else:
              print(f"Instagram session {item['index']}: not working")

      application.bot_data["monitor_task"] = asyncio.create_task(monitor_loop(application))

  async def post_shutdown(application):
      monitor_task = application.bot_data.get("monitor_task")
      if monitor_task:
          monitor_task.cancel()
          try:
              await monitor_task
          except asyncio.CancelledError:
              pass

      session = application.bot_data.get("http_session")
      if session and not session.closed:
          await session.close()

  def main():
      try:
          from keep_alive import keep_alive
          keep_alive()
      except ImportError:
          pass

      threading.Thread(target=run_web_server, daemon=True).start()

      init_db()
      app = Application.builder().token(TOKEN).post_init(post_init).post_shutdown (post_shutdown).build()

      app.add_handler(TypeHandler(Update, track_chat), group=-1)
      app.add_handler(CommandHandler("start", start))
      app.add_handler(CommandHandler("help", help_command))
      app.add_handler(CommandHandler("admin", admin_command))
      app.add_handler(CommandHandler("active", active_command))
      app.add_handler(CommandHandler("activate", activate_command))
      app.add_handler(CommandHandler("deactivate", deactivate_command))
      app.add_handler(CommandHandler("users", users_command))
      app.add_handler(CommandHandler("sessions", sessions_command))
      app.add_handler(CommandHandler("myid", myid_command))
      app.add_handler(CommandHandler("language", language_command))
      app.add_handler(CommandHandler("lang", language_command))
      app.add_handler(CommandHandler("chk", chk_command))
      app.add_handler(CommandHandler("add", add_command))
      app.add_handler(CommandHandler("addfast", add_fast_command))
      app.add_handler(CommandHandler("delete", delete_command))
      app.add_handler(CommandHandler("status", status_command))
      app.add_handler(CommandHandler("export", export_command))
      app.add_handler(CommandHandler("broadcast", broadcast_command))
      app.add_handler(CommandHandler("cancel", cancel_command))
      app.add_handler(CommandHandler("checklogin", checklogin_command))

      app.add_handler(CallbackQueryHandler(button_handler))
      app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
      app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

      print("Bot is running 24/7 with Instagram monitor and complaint buttons.")
      app.run_polling(bootstrap_retries=10, drop_pending_updates=True)

  if __name__ == "__main__":
      import asyncio
      try:
          loop = asyncio.get_event_loop()
      except RuntimeError:
          loop = asyncio.new_event_loop()
          asyncio.set_event_loop(loop)

      main()
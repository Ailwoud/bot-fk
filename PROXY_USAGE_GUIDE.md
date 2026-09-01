# استخدام Cloudflare Worker Proxy - دليل سريع

## ملخص التعديلات

تم تعديل `main.py` لإضافة دعم **Cloudflare Worker Proxy** بحيث يتم توجيه جميع طلبات Instagram عبره.

### ما تم تعديله:

| الجزء | التفاصيل |
|------|---------|
| **متغير جديد** | `CLOUDFLARE_PROXY_URL` من ملف `.env` |
| **دالة جديدة** | `proxy_url()` لتحويل URLs تلقائياً |
| **الطلبات المعدّلة** | جميع طلبات Instagram (5 أماكن في الكود) |
| **المحفوظ** | Headers, Cookies, منطق البوت بالكامل |

---

## خطوات الإعداد السريعة

### 1️⃣ إنشاء Cloudflare Worker

```bash
# اذهب إلى https://dash.cloudflare.com/
# Workers & Pages → Create Application → Create Worker

# انسخ كود CLOUDFLARE_WORKER_CODE.js إلى Worker
```

### 2️⃣ تحديث `.env`

```bash
# استبدل YOUR-WORKER-NAME بـ اسم Workerك الفعلي
CLOUDFLARE_PROXY_URL=https://my-ig-proxy.mysubdomain.workers.dev
```

### 3️⃣ إعادة تشغيل البوت

```bash
export $(cat .env | xargs) && python main.py
```

---

## التحقق من أن كل شيء يعمل

### اختبار 1: فحص حساب Instagram
```
/chk username
```
✅ إذا رأيت نتيجة الفحص → يعمل بنجاح

### اختبار 2: إضافة للمراقبة
```
/add user1 user2 user3
```
✅ إذا تمت الإضافة بدون أخطاء → يعمل بنجاح

### اختبر 3: التحقق من الـ Logs
```bash
# شغّل البوت وراقب الـ Output
Bot is running 24/7 with Instagram monitor and complaint buttons.
Instagram sessions: 1/1 working
Instagram session 1: working
```

---

## الخصائص المحفوظة

✅ **Headers محفوظة:**
- User-Agent
- X-IG-App-ID
- X-ASBD-ID
- Accept-Language
- Referer
- وغيرها...

✅ **Cookies محفوظة:**
- sessionid (من Instagram)
- ds_user_id (معرف المستخدم)

✅ **منطق البوت:**
- جميع الأوامر (add, delete, check, admin)
- جميع الأزرار والقوائم
- جميع الترجمات (عربي/إنجليزي)
- معالجة Turso و SQLite
- الإشعارات والتنبيهات

---

## في حالة المشاكل

### ❌ المشكلة: الـ Proxy غير مستجيب
**الحل:**
```bash
# تحقق من URL
echo $CLOUDFLARE_PROXY_URL

# اختبر الوصول المباشر
curl https://your-worker.workers.dev/
```

### ❌ المشكلة: 404 Not Found
**الحل:**
- تأكد من أن الـ Worker يستخدم الكود الصحيح
- تحقق من اسم الـ Worker في `.env`

### ❌ المشكلة: Cookies غير محفوظة
**الحل:**
- تحقق من أن Worker يمرر `request.headers`
- تأكد من أن الـ Referer سليم

---

## معلومات تقنية

### كيفية عمل `proxy_url()`:

```python
# مثال:
CLOUDFLARE_PROXY_URL = "https://my-proxy.workers.dev"

# قبل:
url = "https://www.instagram.com/username/"

# بعد:
url = proxy_url("https://www.instagram.com/username/")
# النتيجة: "https://my-proxy.workers.dev/username/"
```

### الطلبات المعدّلة (5 أماكن):

```python
1. async with session.get(proxy_url("https://www.instagram.com/"), ...)
2. async with session.get(proxy_url(url), ...)  # API endpoints
3. async with session.get(proxy_url("https://www.instagram.com/accounts/access_tool/current_user"), ...)
4. url = proxy_url(original_url)  # في fetch_profile_info
5. + جميع الـ URLs تستخدم proxy_url()
```

---

## إذا أردت تعطيل الـ Proxy

ببساطة، احذف أو اترك `CLOUDFLARE_PROXY_URL` فارغة في `.env`:

```bash
# سيعود البوت للعمل مباشرة مع Instagram بدون Proxy
CLOUDFLARE_PROXY_URL=
```

---

## الملفات الجديدة

| الملف | الوصف |
|------|-------|
| `CLOUDFLARE_PROXY_SETUP.md` | دليل الإعداد الشامل |
| `CLOUDFLARE_WORKER_CODE.js` | كود Cloudflare Worker جاهز |
| `PROXY_USAGE_GUIDE.md` | هذا الملف (الدليل السريع) |

---

**تم الإعداد بنجاح! ✅**

الآن يمكنك:
- 🚀 تشغيل البوت مع Proxy
- 🔄 توجيه جميع طلبات Instagram عبر Worker
- 🛡️ الاستفادة من خوادم Cloudflare
- ⚡ تحسين الأداء والموثوقية

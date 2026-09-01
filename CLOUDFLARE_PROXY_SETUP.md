# Cloudflare Worker Proxy Setup Guide

## Overview
تم تعديل البوت لتوجيه جميع طلبات Instagram عبر Cloudflare Worker Proxy. هذا يتيح:
- ✅ تجاوز القيود الجغرافية على Instagram
- ✅ تحسين الأداء عبر شبكة Cloudflare
- ✅ الحفاظ على جميع الـ Headers و Cookies بشكل صحيح
- ✅ بقاء منطق البوت والأزرار كما هي

## التعديلات المجرّاة

### 1. **دالة Proxy URL الجديدة**
```python
def proxy_url(original_url):
    """تحويل URLs Instagram لتمر عبر Cloudflare Worker Proxy"""
    if not CLOUDFLARE_PROXY_URL:
        return original_url
    
    # تحويل https://www.instagram.com/* أو https://i.instagram.com/*
    # إلى https://YOUR-WORKER-NAME.YOUR-SUBDOMAIN.workers.dev/*
```

### 2. **جميع طلبات Instagram المعدّلة:**
- ❌ `https://www.instagram.com/` → ✅ `proxy_url("https://www.instagram.com/")`
- ❌ `https://i.instagram.com/api/v1/accounts/current_user/` → ✅ `proxy_url(...)`
- ❌ `https://www.instagram.com/api/v1/accounts/current_user/` → ✅ `proxy_url(...)`
- ❌ `https://www.instagram.com/accounts/access_tool/current_user` → ✅ `proxy_url(...)`
- ❌ `https://www.instagram.com/{username}/` → ✅ `proxy_url(...)`

### 3. **الحفاظ على الوظائف الكاملة:**
- ✅ جميع الـ Headers محفوظة (User-Agent, X-IG-App-ID, إلخ)
- ✅ جميع الـ Cookies محفوظة (sessionid, ds_user_id)
- ✅ منطق البوت، أوامر التليجرام، الأزرار دون تغيير
- ✅ معالجة Turso و SQLite دون تغيير
- ✅ الترجمات والإشعارات دون تغيير

## كيفية الاستخدام

### الخطوة 1: إنشاء Cloudflare Worker
1. اذهب إلى [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. اختر `Workers & Pages` → `Create`
3. أنشئ Worker جديد
4. استخدم كود Proxy بسيط (مثال):

```javascript
// Cloudflare Worker Code
export default {
  async fetch(request) {
    const url = new URL(request.url);
    
    // تحويل الطلب إلى Instagram
    const instagramURL = new URL(url.pathname + url.search, 'https://www.instagram.com');
    
    // إعادة توجيه الطلب
    const newRequest = new Request(instagramURL, {
      method: request.method,
      headers: request.headers,
      body: request.body,
    });
    
    return fetch(newRequest);
  }
};
```

### الخطوة 2: تحديث ملف `.env`
```bash
# مثال
CLOUDFLARE_PROXY_URL=https://my-ig-proxy.mysubdomain.workers.dev
```

### الخطوة 3: إعادة تشغيل البوت
```bash
export $(cat .env | xargs) && python main.py
```

## التحقق من أن الـ Proxy يعمل

اختبر الوظيفة:
```bash
# استخدم أمر الفحص
/chk username

# أو استخدم الأزرار في البوت
```

إذا رأيت:
- ✅ **نتائج الفحص تظهر بشكل صحيح** → الـ Proxy يعمل
- ❌ **رسالة خطأ "Instagram يمنع الفحص"** → قد تحتاج تحديث Worker أو Proxy

## ملاحظات مهمة

### 1. **إذا لم تقم بتعيين CLOUDFLARE_PROXY_URL:**
- البوت سيعمل بشكل طبيعي دون Proxy
- جميع الطلبات ستذهب مباشرة إلى Instagram.com

### 2. **الـ Headers محفوظة:**
```python
'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)...'
'x-ig-app-id': '936619743392459'
'x-asbd-id': '129119'
'x-requested-with': 'XMLHttpRequest'
# إلخ...
```

### 3. **الـ Cookies محفوظة:**
```python
cookies = {
    'sessionid': 'your-session-id',
    'ds_user_id': 'your-user-id'
}
# تُمرّر تلقائياً عبر الـ Proxy
```

## استكشاف الأخطاء

| المشكلة | الحل |
|--------|------|
| الـ Proxy لا يستجيب | تحقق من URL في .env |
| 404 errors | تأكد من استخدام الـ Worker الصحيح |
| Rate limiting | قد تحتاج لإضافة delay في Worker |
| Cookies غير محفوظة | تحقق من إعدادات Worker |

## اختبار سريع

```python
# في Python
import os
os.environ['CLOUDFLARE_PROXY_URL'] = 'https://test.workers.dev'

from main import proxy_url

# سيعيد:
print(proxy_url('https://www.instagram.com/username/'))
# Output: https://test.workers.dev/username/
```

## الدعم

إذا واجهت مشاكل:
1. تحقق من logs الـ Worker
2. اختبر الـ Proxy بشكل مباشر: `curl https://YOUR-WORKER.workers.dev/`
3. تأكد من أن Headers تُمرّر بشكل صحيح

---

**آخر تحديث:** 2026-09-01
**الإصدار:** 1.0

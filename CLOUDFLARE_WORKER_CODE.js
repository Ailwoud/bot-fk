/**
 * Cloudflare Worker - Instagram Proxy
 * 
 * هذا الـ Worker يقوم بتوجيه جميع الطلبات إلى Instagram
 * مع الحفاظ على Headers و Cookies
 * 
 * كيفية الاستخدام:
 * 1. انسخ هذا الكود إلى Cloudflare Worker
 * 2. سيتم توجيه جميع الطلبات التالية:
 *    - https://your-worker.workers.dev/username/
 *    - https://your-worker.workers.dev/api/v1/accounts/current_user/
 * 3. تم نقلها إلى:
 *    - https://www.instagram.com/username/
 *    - https://i.instagram.com/api/v1/accounts/current_user/
 */

export default {
  async fetch(request) {
    const url = new URL(request.url);
    
    // استخراج المسار من Worker
    const pathname = url.pathname;
    const searchParams = url.search;
    
    // تحديد domain Instagram الصحيح
    let instagramDomain = 'https://www.instagram.com';
    
    // إذا كان الطلب يحتوي على /api/ فاستخدم i.instagram.com
    if (pathname.includes('/api/')) {
      instagramDomain = 'https://i.instagram.com';
    }
    
    // بناء الـ Instagram URL
    const instagramURL = new URL(pathname + searchParams, instagramDomain);
    
    // إنشاء طلب جديد مع الحفاظ على جميع الـ Headers
    const newRequest = new Request(instagramURL, {
      method: request.method,
      headers: request.headers,
      body: request.body,
      redirect: 'follow',
    });
    
    try {
      // إرسال الطلب إلى Instagram
      const response = await fetch(newRequest);
      
      // إعادة الرد مع الحفاظ على Headers
      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    } catch (error) {
      return new Response(`Error: ${error.message}`, { status: 500 });
    }
  },
};

/**
 * أمثلة على الطلبات:
 * 
 * 1. فحص الحساب:
 *    GET https://your-worker.workers.dev/username/
 *    → https://www.instagram.com/username/
 * 
 * 2. الحصول على معلومات المستخدم:
 *    GET https://your-worker.workers.dev/api/v1/accounts/current_user/
 *    → https://i.instagram.com/api/v1/accounts/current_user/
 * 
 * 3. Cookies و Headers:
 *    Cookie: sessionid=YOUR_SESSION_ID
 *    X-IG-App-Id: 936619743392459
 *    → يتم الحفاظ عليها جميعاً
 */

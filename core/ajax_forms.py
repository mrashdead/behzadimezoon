"""پاسخ‌دهی JSON به فرم‌های داخل مودال (AJAX).

انگیزه
------
پیش‌تر ``form_invalid`` در نمای مشتریان فقط یک پیام کلی نشان می‌داد و
صفحه را ریدایرکت می‌کرد؛ یعنی **تمام خطاهای فیلد‌به‌فیلد دور ریخته
می‌شد** و کاربر هم داده‌های واردشده‌اش را از دست می‌داد. در محصولات هم
کاربر به یک صفحهٔ کامل فرم هدایت می‌شد و مودال بسته می‌شد.

با ``AjaxFormMixin`` وقتی درخواست AJAX است، خطاها به‌شکل JSON برگردانده
می‌شوند و مودال باز می‌ماند؛ بنابراین کاربر همان‌جا خطا را می‌بیند و
مقادیرش حفظ می‌شود.

قرارداد پاسخ::

    موفق:   {"success": true,  "message": "..."}
    ناموفق: {"success": false, "errors": {"field": ["msg"], ...}}   # HTTP 400
"""

from __future__ import annotations

from django.http import JsonResponse


def is_ajax_request(request) -> bool:
    """آیا درخواست از نوع AJAX/JSON است؟"""
    if request is None:
        return False
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return True
    if request.headers.get("accept", "").startswith("application/json"):
        return True
    return request.POST.get("ajax") == "1" or request.GET.get("ajax") == "1"


class AjaxFormMixin:
    """ارسال خطاهای فرم به‌صورت JSON برای فرم‌های داخل مودال.

    این mixin را **قبل** از ``CreateView``/``UpdateView``/``FormView``
    قرار دهید و مطمئن شوید ``super().form_valid(form)`` واقعاً
    ذخیره‌سازی را انجام می‌دهد.

    نکته: ``ErrorDict`` و ``ErrorList`` در جنگو زیرکلاس ``dict``/``list``
    هستند، بنابراین ``JsonResponse`` آن‌ها را درست سریال‌سازی می‌کند.
    """

    #: پیام موفقیت که سمت کلاینت به‌صورت toast نمایش داده می‌شود.
    ajax_success_message = "اطلاعات با موفقیت ذخیره شد."

    def is_ajax_form_request(self) -> bool:
        return is_ajax_request(getattr(self, "request", None))

    # ------------------------------------------------------------------ hooks
    def form_invalid(self, form):
        if self.is_ajax_form_request():
            return JsonResponse(
                {"success": False, "errors": form.errors},
                status=400,
            )
        return super().form_invalid(form)

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.is_ajax_form_request():
            return JsonResponse(
                {"success": True, "message": self.ajax_success_message}
            )
        return response


# ---------------------------------------------------------------------------
# کمکی‌های پاسخ JSON برای نماهای تابعی (function-based)
# ---------------------------------------------------------------------------
def _as_message_list(value) -> list[str]:
    """هر مقدار خطا را به فهرستی از رشته‌ها تبدیل می‌کند."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def json_error(errors, status: int = 400, message: str | None = None) -> JsonResponse:
    """پاسخ خطای یکسان برای فرم‌های AJAX.

    ``errors`` می‌تواند یک دیکشنری ``{field: [msg, ...]}`` یا یک رشته باشد.

    علاوه بر قرارداد جدید (``success`` / ``errors``)، کلید قدیمی ``error``
    هم برگردانده می‌شود تا مصرف‌کننده‌های قدیمی که ``data.error`` را
    می‌خوانند نشکنند.
    """
    if isinstance(errors, dict):
        normalized = {key: _as_message_list(value) for key, value in errors.items()}
    else:
        normalized = {"__all__": _as_message_list(errors)}

    flat = [msg for messages in normalized.values() for msg in messages]

    return JsonResponse(
        {
            "success": False,
            "errors": normalized,
            "message": message or (flat[0] if flat else "اطلاعات ارسالی معتبر نیست."),
            # سازگاری با مصرف‌کننده‌های قدیمی
            "error": flat[0] if flat else "اطلاعات ارسالی معتبر نیست.",
        },
        status=status,
    )


def json_success(message: str, **extra) -> JsonResponse:
    """پاسخ موفقیت یکسان برای فرم‌های AJAX.

    کلید ``result='ok'`` برای سازگاری با مصرف‌کننده‌های قدیمی حفظ شده است.
    """
    payload = {"success": True, "message": message, "result": "ok"}
    payload.update(extra)
    return JsonResponse(payload)

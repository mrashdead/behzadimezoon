/*
 * Reservation Picker — انتخابگر جستجوپذیر رزرو
 * ---------------------------------------------------------------------------
 * یک ورودی متنی که با تایپ، از API جستجوی رزرو نتیجه می‌گیرد، مقدار
 * شناسهٔ رزرو را در یک ورودی مخفی می‌گذارد و اطلاعات مالی رزرو را به‌صورت
 * خودکار از دیتابیس پر می‌کند.
 *
 * چرا؟ پیش‌تر در صفحهٔ «ثبت پرداخت» کاربر باید شناسهٔ عددی رزرو را دستی
 * وارد می‌کرد و هیچ بازخوردی از وجود/عدم وجود آن رزرو نمی‌گرفت.
 *
 * نحوهٔ استفاده (کلاس‌های CSS از reservation-combobox.css قرض گرفته شده‌اند):
 *
 *   <div class="combobox-wrapper"
 *        data-reservation-picker
 *        data-search-url="{% url 'financial:api_reservation_search' %}"
 *        data-info-url="{% url 'financial:api_reservation_info' %}">
 *     <div class="combobox-field">
 *       <input type="text" class="form-control combobox-input" required
 *              autocomplete="off" data-reservation-picker-input
 *              placeholder="جستجو با نام عروس، کد لباس یا شمارهٔ رزرو…">
 *       <button type="button" class="combobox-clear d-none"
 *               data-reservation-picker-clear aria-label="پاک کردن">×</button>
 *       <span class="combobox-icon"><i class="fi fi-rr-search"></i></span>
 *     </div>
 *     <input type="hidden" name="reservation_id" data-reservation-picker-value>
 *     <div class="combobox-menu d-none" data-reservation-picker-menu role="listbox"></div>
 *     <div class="invalid-feedback d-block" data-reservation-picker-feedback></div>
 *     <div class="mt-2" data-reservation-picker-summary></div>
 *   </div>
 *
 * رویداد: هنگام انتخاب، ``reservation-picker:selected`` روی عنصر ریشه
 * با ``detail`` شامل اطلاعات کامل رزرو ارسال می‌شود.
 */
(function () {
  'use strict';

  var SEARCH_DEBOUNCE_MS = 260;

  function debounce(fn, wait) {
    var timer = null;
    return function () {
      var args = arguments;
      var self = this;
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        fn.apply(self, args);
      }, wait);
    };
  }

  function money(value) {
    var num = Number(value || 0);
    if (!isFinite(num)) return '۰';
    try {
      return num.toLocaleString('fa-IR');
    } catch (err) {
      return String(num);
    }
  }

  function escapeHtml(text) {
    return String(text == null ? '' : text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  var PAYMENT_STATUS_LABELS = {
    PAID: 'تسویه‌شده',
    PARTIAL: 'پرداخت جزئی',
    UNPAID: 'پرداخت‌نشده',
  };

  function createPicker(root) {
    var input = root.querySelector('[data-reservation-picker-input]');
    var hidden = root.querySelector('[data-reservation-picker-value]');
    var menu = root.querySelector('[data-reservation-picker-menu]');
    var clearBtn = root.querySelector('[data-reservation-picker-clear]');
    var feedback = root.querySelector('[data-reservation-picker-feedback]');
    var summary = root.querySelector('[data-reservation-picker-summary]');

    if (!input || !hidden || !menu) return null;

    var searchUrl = root.getAttribute('data-search-url') || '';
    var infoUrl = root.getAttribute('data-info-url') || '';
    var minChars = parseInt(root.getAttribute('data-min-chars') || '1', 10);

    var results = [];
    var activeIndex = -1;
    var selected = null;
    var requestToken = 0;

    // ---------------------------------------------------------------- helpers
    function clearFeedback() {
      if (feedback) {
        feedback.textContent = '';
        feedback.classList.add('d-none');
        feedback.classList.remove('d-block');
      }
      input.classList.remove('is-invalid');
    }

    function showFeedback(message) {
      if (feedback) {
        feedback.textContent = message;
        feedback.classList.remove('d-none');
        feedback.classList.add('d-block');
      }
      input.classList.add('is-invalid');
    }

    function openMenu() {
      menu.classList.remove('d-none');
      root.classList.add('combobox-open');
    }

    function closeMenu() {
      menu.classList.add('d-none');
      root.classList.remove('combobox-open');
      activeIndex = -1;
    }

    function syncClearVisibility() {
      if (!clearBtn) return;
      var show = Boolean(hidden.value) || Boolean(input.value.trim());
      clearBtn.classList.toggle('d-none', !show);
    }

    function renderMessage(message) {
      menu.innerHTML = '';
      var row = document.createElement('div');
      row.className = 'combobox-no-results';
      row.textContent = message;
      menu.appendChild(row);
      openMenu();
    }

    function renderSummary(info) {
      if (!summary) return;
      if (!info) {
        summary.innerHTML = '';
        return;
      }

      var statusKey = info.payment_status || '';
      var statusLabel = PAYMENT_STATUS_LABELS[statusKey] || info.payment_status || '—';
      var statusTone = statusKey === 'PAID'
        ? 'success'
        : (statusKey === 'PARTIAL' ? 'warning' : 'danger');

      var remaining = Number(info.remaining_amount || 0);

      summary.innerHTML =
        '<div class="card border-0 shadow-none detail-card detail-card--primary">' +
          '<div class="card-body py-3 px-3">' +
            '<div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">' +
              '<span class="detail-card__label mb-0">' +
                '<i class="fi fi-rr-file-invoice me-1"></i>' + escapeHtml(info.label || ('رزرو #' + info.id)) +
              '</span>' +
              '<span class="badge badge-sm bg-' + statusTone + '-subtle text-' + statusTone + '">' +
                escapeHtml(statusLabel) +
              '</span>' +
            '</div>' +
            '<div class="row g-2 text-2xs">' +
              '<div class="col-6 col-lg-3"><span class="text-muted d-block">مبلغ نهایی</span>' +
                '<strong>' + money(info.final_price) + ' تومان</strong></div>' +
              '<div class="col-6 col-lg-3"><span class="text-muted d-block">بیعانه پرداختی</span>' +
                '<strong>' + money(info.deposit_amount) + ' تومان</strong></div>' +
              '<div class="col-6 col-lg-3"><span class="text-muted d-block">مانده</span>' +
                '<strong class="' + (remaining > 0 ? 'text-danger' : 'text-success') + '">' +
                money(remaining) + ' تومان</strong></div>' +
              '<div class="col-6 col-lg-3"><span class="text-muted d-block">مشتری</span>' +
                '<strong>' + escapeHtml(info.customer || '—') + '</strong></div>' +
            '</div>' +
            (remaining > 0
              ? '<button type="button" class="btn btn-sm btn-outline-primary mt-2" ' +
                'data-reservation-picker-fill-remaining data-remaining="' + remaining + '">' +
                '<i class="fi fi-rr-coins me-1"></i>درج مانده (' + money(remaining) + ' تومان)</button>'
              : '') +
          '</div>' +
        '</div>';

      // دکمهٔ «درج مانده» مبلغ را در ورودی پول کپی می‌کند (اگر روی صفحه باشد).
      var fillBtn = summary.querySelector('[data-reservation-picker-fill-remaining]');
      if (fillBtn) {
        fillBtn.addEventListener('click', function () {
          var amountInput = document.querySelector(
            root.getAttribute('data-amount-target') || '.money-input'
          );
          if (!amountInput) return;
          amountInput.value = fillBtn.getAttribute('data-remaining');
          amountInput.dispatchEvent(new Event('input', { bubbles: true }));
          amountInput.focus();
        });
      }
    }

    function selectReservation(item) {
      selected = item;
      hidden.value = item.id;
      input.value = item.label;
      hidden.dispatchEvent(new Event('change', { bubbles: true }));
      clearFeedback();
      closeMenu();
      syncClearVisibility();
      loadInfo(item.id);
    }

    function clearSelection() {
      selected = null;
      hidden.value = '';
      input.value = '';
      hidden.dispatchEvent(new Event('change', { bubbles: true }));
      renderSummary(null);
      closeMenu();
      syncClearVisibility();
      clearFeedback();
    }

    function loadInfo(id) {
      if (!infoUrl) return;
      var url = infoUrl + (infoUrl.indexOf('?') === -1 ? '?' : '&') + 'id=' + encodeURIComponent(id);
      fetch(url, {
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then(function (response) { return response.json(); })
        .then(function (data) {
          if (!data || data.error) return;
          renderSummary(data);
          root.dispatchEvent(new CustomEvent('reservation-picker:selected', {
            bubbles: true,
            detail: data,
          }));
        })
        .catch(function () { /* بی‌صدا: نبود اطلاعات تکمیلی نباید مانع ثبت شود */ });
    }

    function renderResults(items) {
      results = items;
      activeIndex = -1;
      menu.innerHTML = '';

      if (!items.length) {
        renderMessage('رزروی با این عبارت یافت نشد.');
        return;
      }

      items.forEach(function (item, index) {
        var row = document.createElement('div');
        row.className = 'combobox-item';
        row.setAttribute('role', 'option');
        row.dataset.id = item.id;
        row.dataset.index = String(index);
        row.innerHTML =
          '<span>' + escapeHtml(item.label) + '</span>' +
          '<span class="text-2xs text-muted">' +
            money(item.remaining_amount) + ' مانده' +
          '</span>';

        row.addEventListener('mousedown', function (event) {
          event.preventDefault();
          selectReservation(item);
        });
        menu.appendChild(row);
      });

      openMenu();
    }

    var runSearch = debounce(function (query) {
      if (!searchUrl) return;
      var token = ++requestToken;
      var url = searchUrl + (searchUrl.indexOf('?') === -1 ? '?' : '&') + 'q=' + encodeURIComponent(query);

      fetch(url, {
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then(function (response) { return response.json(); })
        .then(function (data) {
          // پاسخ‌های قدیمی‌تر نباید نتیجهٔ جدیدتر را بازنویسی کنند.
          if (token !== requestToken) return;
          renderResults((data && data.results) || []);
        })
        .catch(function () {
          if (token !== requestToken) return;
          renderMessage('جستجوی رزرو ناموفق بود. اتصال را بررسی کنید.');
        });
    }, SEARCH_DEBOUNCE_MS);

    // ------------------------------------------------------------------ events
    input.addEventListener('input', function () {
      // تایپ دستی یعنی انتخاب قبلی دیگر معتبر نیست.
      if (selected && input.value !== selected.label) {
        selected = null;
        hidden.value = '';
        renderSummary(null);
      }
      clearFeedback();
      syncClearVisibility();

      var query = input.value.trim();
      if (query.length < minChars) {
        closeMenu();
        return;
      }
      runSearch(query);
    });

    input.addEventListener('focus', function () {
      var query = input.value.trim();
      if (query.length >= minChars && results.length) {
        renderResults(results);
      }
    });

    input.addEventListener('blur', function () {
      window.setTimeout(closeMenu, 160);
    });

    input.addEventListener('keydown', function (event) {
      var rows = Array.prototype.slice.call(menu.querySelectorAll('.combobox-item'));

      if (event.key === 'ArrowDown') {
        if (menu.classList.contains('d-none')) return;
        event.preventDefault();
        activeIndex = Math.min(activeIndex + 1, rows.length - 1);
        rows.forEach(function (row, index) {
          row.classList.toggle('active', index === activeIndex);
        });
        if (rows[activeIndex]) rows[activeIndex].scrollIntoView({ block: 'nearest' });
        return;
      }

      if (event.key === 'ArrowUp') {
        if (menu.classList.contains('d-none')) return;
        event.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
        rows.forEach(function (row, index) {
          row.classList.toggle('active', index === activeIndex);
        });
        if (rows[activeIndex]) rows[activeIndex].scrollIntoView({ block: 'nearest' });
        return;
      }

      if (event.key === 'Enter' && activeIndex >= 0) {
        event.preventDefault();
        var chosen = results[activeIndex];
        if (chosen) selectReservation(chosen);
        return;
      }

      if (event.key === 'Escape') {
        closeMenu();
      }
    });

    if (clearBtn) {
      clearBtn.addEventListener('click', function (event) {
        event.preventDefault();
        clearSelection();
        input.focus();
      });
    }

    syncClearVisibility();

    return {
      clear: clearSelection,
      getSelection: function () { return selected; },
      root: root,
    };
  }

  function initAll() {
    var created = [];
    document.querySelectorAll('[data-reservation-picker]').forEach(function (root) {
      var instance = createPicker(root);
      if (instance) created.push(instance);
    });
    return created;
  }

  document.addEventListener('DOMContentLoaded', initAll);

  window.ReservationPicker = {
    init: initAll,
    instances: [],
  };
})();

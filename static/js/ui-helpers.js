/**
 * UI Helper Functions for Money Formatting, Date Pickers, and AJAX Forms
 */

// Format number with thousand separators for display
function formatNumber(num) {
  if (!num) return '0';
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// Parse formatted number back to integer
function parseFormattedNumber(str) {
  return parseInt(str.replace(/,/g, ''), 10) || 0;
}

// Initialize money input formatters
function initMoneyInputs() {
  document.querySelectorAll('.money-input').forEach(input => {
    input.addEventListener('input', function(e) {
      let value = this.value.replace(/,/g, '');
      if (value) {
        this.value = formatNumber(value);
      }
    });

    input.addEventListener('blur', function(e) {
      if (this.value) {
        this.value = formatNumber(this.value.replace(/,/g, ''));
      }
    });

    input.addEventListener('focus', function(e) {
      this.value = this.value.replace(/,/g, '');
    });
  });
}

// Format number displays to show thousands separator
function formatNumberDisplays() {
  document.querySelectorAll('.number-display').forEach(el => {
    const value = el.getAttribute('data-value');
    if (value) {
      el.textContent = formatNumber(value);
    }
  });
}

// Initialize Persian date pickers
//
// ⚠️ نکتهٔ مهم:
// در این پروژه کتابخانهٔ تاریخ‌گزین «persian-datepicker» (نسخهٔ babakhani)
// بارگذاری می‌شود و API آن `$(el).pDatepicker(...)` است.
// پیش‌تر این تابع فقط از «flatpickr» استفاده می‌کرد؛ چون flatpickr در این
// پروژه اصلاً بارگذاری نمی‌شود، تابع در همان خط اول `return` می‌کرد و هیچ
// تاریخ‌گزینی ساخته نمی‌شد. نتیجه: هر فیلد تاریخی که «بعداً» به DOM اضافه
// می‌شد (ردیف‌های بیعانهٔ مرحله‌ای، محتوای مودال‌ها) تاریخ‌گزین نمی‌گرفت.
//
// اکنون اولویت با pDatepicker است و flatpickr تنها در صورت وجود، به‌عنوان
// جایگزین استفاده می‌شود.
function initPersianDatepickers() {
  var jq = window.jQuery;
  var hasPwt = !!(jq && typeof jq.fn.pDatepicker === 'function');
  var hasFlatpickr = typeof flatpickr !== 'undefined';

  if (!hasPwt && !hasFlatpickr) return;

  function alreadyBound(el) {
    if (el.dataset && el.dataset.pwtBound === '1') return true;
    try {
      if (jq && jq(el).data('datepicker')) return true;
    } catch (e) {
      /* ignore */
    }
    return false;
  }

  function attach(el, pwtOptions, flatpickrOptions) {
    if (alreadyBound(el)) return;
    try {
      if (hasPwt) {
        jq(el).pDatepicker(pwtOptions);
      } else {
        flatpickr(el, flatpickrOptions);
      }
      el.dataset.pwtBound = '1';
    } catch (e) {
      // یک فیلد خراب نباید بقیهٔ فیلدها را از کار بیندازد
      if (window.console && console.warn) {
        console.warn('datepicker init failed:', el, e);
      }
    }
  }

  // ۱. فقط تاریخ
  document.querySelectorAll('.p-date-only').forEach(el => {
    attach(el, {
      timePicker: { enabled: false },
      format: 'YYYY/MM/DD',
      autoClose: true,
      initialValue: false,
      initialValueType: 'persian',
      calendar: { persian: { locale: 'fa' } },
    }, { mode: 'single', dateFormat: 'Y/m/d', locale: 'fa' });
  });

  // ۲. تاریخ و زمان
  document.querySelectorAll('.p-date-time').forEach(el => {
    attach(el, {
      timePicker: { enabled: true, second: { enabled: false } },
      format: 'YYYY/MM/DD HH:mm',
      autoClose: true,
      calendar: { persian: { locale: 'fa' } },
    }, { mode: 'single', dateFormat: 'Y/m/d H:i', enableTime: true, locale: 'fa' });
  });

  // ۳. فقط زمان
  document.querySelectorAll('.p-time-only').forEach(el => {
    attach(el, {
      onlyTimePicker: true,
      timePicker: { enabled: true, second: { enabled: false } },
      format: 'HH:mm',
      autoClose: true,
    }, { mode: 'single', dateFormat: 'H:i', enableTime: true, noCalendar: true, locale: 'fa' });
  });

  // ۴. فقط ماه و سال
  document.querySelectorAll('.p-month-only').forEach(el => {
    attach(el, {
      timePicker: { enabled: false },
      format: 'MMMM YYYY',
      autoClose: true,
      viewMode: 'month',
      minViewMode: 'month',
      onlySelectOnDate: false,
    }, { mode: 'single', dateFormat: 'Y/m', locale: 'fa' });
  });

  // ۵. بازهٔ تاریخ
  document.querySelectorAll('.p-date-range').forEach(el => {
    attach(el, {
      format: 'YYYY/MM/DD',
      autoClose: true,
      initialValue: false,
      calendar: { persian: { locale: 'fa' } },
    }, { mode: 'range', dateFormat: 'Y/m/d', locale: 'fa' });
  });

  // ۶. چند تاریخ
  document.querySelectorAll('.p-multiple-date').forEach(el => {
    attach(el, {
      format: 'YYYY/MM/DD',
      autoClose: true,
      initialValue: false,
      calendar: { persian: { locale: 'fa' } },
    }, { mode: 'multiple', dateFormat: 'Y/m/d', locale: 'fa' });
  });

  // ۷. فقط هفته
  document.querySelectorAll('.p-week-only').forEach(el => {
    attach(el, {
      format: 'YYYY/MM/DD',
      autoClose: true,
      initialValue: false,
      calendar: { persian: { locale: 'fa' } },
    }, { mode: 'single', dateFormat: 'Y/W', locale: 'fa', weekNumbers: true });
  });
}

// Normalize form data before submission (strip money formatting, normalize digits)
function normalizeFormDataForSubmission(form) {
  const formData = new FormData(form);
  const normalized = new FormData();

  for (let [key, value] of formData.entries()) {
    const field = form.querySelector(`[name="${key}"]`);

    if (field && field.classList.contains('money-input')) {
      // Remove commas and normalize Persian/Arabic digits
      let cleanValue = value.toString().replace(/,/g, '');
      cleanValue = normalizeDigits(cleanValue);
      normalized.append(key, cleanValue);
    } else {
      normalized.append(key, value);
    }
  }

  return normalized;
}

// Normalize Persian/Arabic digits to ASCII
function normalizeDigits(value) {
  if (!value) return value;
  const persianArabicDigits = /[۰-۹٠-٩]/g;
  const map = {
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
    '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
    '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
  };
  return value.toString().replace(persianArabicDigits, (d) => map[d]);
}

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + '=') {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// Initialize all UI helpers on page load
document.addEventListener('DOMContentLoaded', function() {
  // Initialize money input formatting
  initMoneyInputs();

  // Initialize number displays
  formatNumberDisplays();

  // Initialize date pickers
  initPersianDatepickers();

  // Attach form submission handlers for all forms with money inputs
  document.querySelectorAll('form').forEach(form => {
    // Only attach if form has money-input fields
    if (form.querySelector('.money-input')) {
      form.addEventListener('submit', function(e) {
        // Clean money inputs before submission
        form.querySelectorAll('.money-input').forEach(input => {
          let cleanValue = input.value.toString().replace(/,/g, '');
          cleanValue = normalizeDigits(cleanValue);
          input.value = cleanValue;
        });
      });
    }
  });
});

// Backwards-compatible alias used by inline scripts
window.UIHelpers = window.UIHelpers || {};
window.UIHelpers.normalizeDigits = normalizeDigits;

// Setup AJAX form submission for modals
function setupModalForms() {
  if (document.body.dataset.uiHelpersModalSubmitBound === '1') {
    return;
  }
  document.body.dataset.uiHelpersModalSubmitBound = '1';

  document.addEventListener('submit', async function (e) {
    const form = e.target;
    if (!form || form.tagName.toLowerCase() !== 'form') {
      return;
    }

    const modal = form.closest('.modal');
    if (!modal || form.classList.contains('no-ajax')) {
      return;
    }

    // فرم‌هایی که ``data-ajax-form`` دارند توسط
    // ``templates/includes/scripts/modal_ajax_form_js.html`` مدیریت می‌شوند
    // (نمایش خطای فیلد‌به‌فیلد + خلاصهٔ خطا). برای جلوگیری از دو بار ارسال،
    // اینجا از آن‌ها صرف‌نظر می‌کنیم.
    if (form.hasAttribute('data-ajax-form')) {
      return;
    }

    if (form.dataset.isSubmitting === '1') {
      e.preventDefault();
      return;
    }

    if (form.classList.contains('needs-validation') && !form.checkValidity()) {
      e.preventDefault();
      form.classList.add('was-validated');
      form.reportValidity();
      return;
    }

    e.preventDefault();
    clearFormErrors(form);
    form.dataset.isSubmitting = '1';
    const submitButtons = Array.from(form.querySelectorAll('button[type="submit"], input[type="submit"]'));
    submitButtons.forEach(button => {
      button.disabled = true;
      button.classList.add('disabled');
    });

    const formData = normalizeFormDataForSubmission(form);
    const url = form.getAttribute('action');
    const modalInstance = bootstrap.Modal.getOrCreateInstance(modal);

    try {
      const response = await fetch(url, {
        method: 'POST',
        body: formData,
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json',
          'X-CSRFToken': getCookie('csrftoken'),
        },
      });

      const contentType = response.headers.get('content-type') || '';
      let data;

      if (contentType.includes('application/json')) {
        data = await response.json();
      } else {
        const text = await response.text();
        throw new Error('Expected JSON response from reservation edit endpoint. Response body: ' + text);
      }

      if (!response.ok && !data.success) {
        if (data.errors) {
          showFormErrors(form, data.errors);
        }
        if (data.message) {
          showNotification(data.message, 'error');
        } else {
          showNotification('خطایی در ارسال فرم رخ داده است.', 'error');
        }
        return;
      }

      if (data.success) {
        if (modalInstance) {
          modalInstance.hide();
        }
        if (data.message) {
          showNotification(data.message, 'success');
        }
        setTimeout(() => {
          location.reload();
        }, 500);
      } else {
        if (data.errors) {
          showFormErrors(form, data.errors);
        }
        if (data.message) {
          showNotification(data.message, 'error');
        } else if (!data.errors) {
          showNotification('خطایی در ارسال فرم رخ داده است.', 'error');
        }
      }
    } catch (error) {
      console.error('Error submitting modal form:', error);
      showNotification('خطا در ارسال فرم. لطفا دوباره تلاش کنید.', 'error');
    } finally {
      form.dataset.isSubmitting = '0';
      submitButtons.forEach(button => {
        button.disabled = false;
        button.classList.remove('disabled');
      });
    }
  }, true);
}

function clearFormErrors(form) {
  form.querySelectorAll('.js-error-message').forEach(el => {
    el.remove();
  });
  form.querySelectorAll('.is-invalid, .is-valid').forEach(el => {
    el.classList.remove('is-invalid', 'is-valid');
  });
  form.classList.remove('was-validated');
  form.querySelectorAll('.alert.js-form-error-summary').forEach(el => {
    el.classList.add('d-none');
    el.textContent = '';
  });
}

function showFormErrorSummary(form, messages) {
  let summary = form.querySelector('.alert.js-form-error-summary');
  if (!summary) {
    summary = document.createElement('div');
    summary.className = 'alert alert-danger js-form-error-summary';
    summary.setAttribute('role', 'alert');
    form.insertBefore(summary, form.firstChild);
  }
  summary.textContent = messages.join(' ');
  summary.classList.remove('d-none');
}

// Display form validation errors
function showFormErrors(form, errors) {
  clearFormErrors(form);

  const generalErrors = [];
  const conflictFieldNames = ['dress', 'start_date', 'rental_days'];
  const generalErrorKeys = ['__all__', 'non_field_errors', 'nonFieldErrors'];
  const conflictFieldSet = new Set();

  Object.keys(errors).forEach(fieldName => {
    const errorMessages = errors[fieldName] || [];
    const field = form.querySelector(`[name="${fieldName}"]`);

    if (field) {
      field.classList.remove('is-valid');
      field.classList.add('is-invalid');
      const errorDiv = document.createElement('div');
      errorDiv.className = 'invalid-feedback d-block js-error-message';
      errorDiv.textContent = errorMessages.join(', ');
      field.parentNode.insertBefore(errorDiv, field.nextSibling);
    } else {
      generalErrors.push(...errorMessages);
      if (generalErrorKeys.includes(fieldName)) {
        conflictFieldNames.forEach(name => conflictFieldSet.add(name));
      }
    }
  });

  if (conflictFieldSet.size) {
    conflictFieldSet.forEach(name => {
      const field = form.querySelector(`[name="${name}"]`);
      if (field) {
        field.classList.remove('is-valid');
        field.classList.add('is-invalid');
        if (!field.parentNode.querySelector('.js-error-message')) {
          const conflictDiv = document.createElement('div');
          conflictDiv.className = 'invalid-feedback d-block js-error-message';
          conflictDiv.textContent = generalErrors.join(', ');
          field.parentNode.insertBefore(conflictDiv, field.nextSibling);
        }
      }
    });
  }

  if (generalErrors.length) {
    showFormErrorSummary(form, generalErrors);
  }

  form.classList.add('was-validated');
}

// Show notification messages
// ---------------------------------------------------------------------------
// اعلان‌ها (app-toast)
// ---------------------------------------------------------------------------
// پیش‌تر این تابع یک alert بوت‌استرپ بالای <main> درج می‌کرد و بعد از ۵ ثانیه
// با ``container.querySelector('.alert')`` حذف می‌کرد — که «اولین» alert صفحه
// را پاک می‌کرد، نه لزوماً همان اعلانی که خودش ساخته بود. همچنین متن پیام با
// درج مستقیم در innerHTML نوشته می‌شد که در صورت ورودی کاربر، XSS بود.
//
// اکنون از سیستم app-toast (استایل‌های custom.css) استفاده می‌شود و متن با
// textContent درج می‌گردد.

var TOAST_PRESETS = {
  success: { tone: 'success', icon: 'fi-rr-check-circle' },
  error: { tone: 'danger', icon: 'fi-rr-exclamation' },
  danger: { tone: 'danger', icon: 'fi-rr-exclamation' },
  warning: { tone: 'warning', icon: 'fi-rr-triangle-warning' },
  info: { tone: 'info', icon: 'fi-rr-info' },
};

function ensureToastStack() {
  var stack = document.getElementById('appToastStack');
  if (!stack) {
    stack = document.createElement('div');
    stack.id = 'appToastStack';
    stack.className = 'app-toast-stack';
    stack.setAttribute('role', 'region');
    stack.setAttribute('aria-label', 'اعلان‌ها');
    document.body.appendChild(stack);
  }
  return stack;
}

function showNotification(message, type) {
  var preset = TOAST_PRESETS[type] || TOAST_PRESETS.info;
  var stack = ensureToastStack();

  var el = document.createElement('div');
  el.className = 'app-toast bg-body border';
  el.dataset.toastDelay = '6000';
  el.innerHTML =
    '<span class="app-toast__accent bg-' + preset.tone + '"></span>' +
    '<div class="app-toast__content">' +
    '<span class="app-toast__icon bg-' + preset.tone + '-subtle text-' + preset.tone + '">' +
    '<i class="fi ' + preset.icon + '"></i>' +
    '</span>' +
    '<div class="app-toast__body">' +
    '<div class="app-toast__message text-body"></div>' +
    '</div>' +
    '<button type="button" class="app-toast__close" aria-label="بستن">' +
    '<i class="fi fi-rr-cross"></i>' +
    '</button>' +
    '</div>';

  // متن پیام به‌صورت متن خام درج می‌شود (نه HTML) تا XSS نشود
  el.querySelector('.app-toast__message').textContent = message;

  stack.appendChild(el);
  window.requestAnimationFrame(function () { el.classList.add('is-visible'); });

  var dismiss = function () {
    if (el.dataset.dismissing === '1') return;
    el.dataset.dismissing = '1';
    el.classList.remove('is-visible');
    el.classList.add('is-hiding');
    window.setTimeout(function () { el.remove(); }, 340);
  };

  window.setTimeout(dismiss, 6000);
  var closeBtn = el.querySelector('.app-toast__close');
  if (closeBtn) {
    closeBtn.addEventListener('click', dismiss);
  }

  return el;
}

// Initialize all UI helpers
function initUIHelpers() {
  initMoneyInputs();
  formatNumberDisplays();
  initPersianDatepickers();
  setupModalForms();
  setupFormMoneyNormalization();
  setupBulkCustomerDelete();
  setupBulkProductDelete();
}

function setupBulkCustomerDelete() {
  const bulkDeleteForm = document.getElementById('bulkCustomerDeleteForm');
  const selectAllCustomers = document.getElementById('selectAllCustomers');
  const bulkDeleteButton = document.getElementById('bulkDeleteButton');

  if (!bulkDeleteForm || !selectAllCustomers || !bulkDeleteButton) {
    return;
  }

  const checkboxes = Array.from(bulkDeleteForm.querySelectorAll('.customer-checkbox'));

  const updateBulkDeleteButtonState = () => {
    const hasSelection = checkboxes.some((checkbox) => checkbox.checked);
    bulkDeleteButton.disabled = !hasSelection;
    selectAllCustomers.checked = checkboxes.length > 0 && checkboxes.every((checkbox) => checkbox.checked);
  };

  selectAllCustomers.addEventListener('change', function () {
    checkboxes.forEach((checkbox) => {
      checkbox.checked = selectAllCustomers.checked;
    });
    updateBulkDeleteButtonState();
  });

  checkboxes.forEach((checkbox) => {
    checkbox.addEventListener('change', updateBulkDeleteButtonState);
  });

  bulkDeleteForm.addEventListener('submit', function (event) {
    const selected = checkboxes.filter((checkbox) => checkbox.checked);
    if (!selected.length) {
      event.preventDefault();
      return false;
    }

    const confirmed = window.confirm('آیا از حذف مشتریان انتخاب‌شده مطمئن هستید؟ مشتریانی که رزرو فعال دارند حذف نمی‌شوند و پیام مناسب نمایش داده می‌شود.');
    if (!confirmed) {
      event.preventDefault();
      return false;
    }
  });

  updateBulkDeleteButtonState();
}

function setupBulkProductDelete() {
  const bulkDeleteForm = document.getElementById('bulkProductDeleteForm');
  const selectAllProducts = document.getElementById('selectAllProducts');
  const bulkDeleteButton = document.getElementById('bulkDeleteButton');

  if (!bulkDeleteForm || !selectAllProducts || !bulkDeleteButton) {
    return;
  }

  const checkboxes = Array.from(bulkDeleteForm.querySelectorAll('.product-checkbox'));

  const updateBulkDeleteButtonState = () => {
    const hasSelection = checkboxes.some((checkbox) => checkbox.checked);
    bulkDeleteButton.disabled = !hasSelection;
    selectAllProducts.checked = checkboxes.length > 0 && checkboxes.every((checkbox) => checkbox.checked);
  };

  selectAllProducts.addEventListener('change', function () {
    checkboxes.forEach((checkbox) => {
      checkbox.checked = selectAllProducts.checked;
    });
    updateBulkDeleteButtonState();
  });

  checkboxes.forEach((checkbox) => {
    checkbox.addEventListener('change', updateBulkDeleteButtonState);
  });

  bulkDeleteForm.addEventListener('submit', function (event) {
    const selected = checkboxes.filter((checkbox) => checkbox.checked);
    if (!selected.length) {
      event.preventDefault();
      return false;
    }

    const confirmed = window.confirm('آیا از حذف محصولات انتخاب‌شده مطمئن هستید؟ محصولاتی که در رزروهای فعال استفاده شده‌اند حذف نمی‌شوند و پیام مناسب نمایش داده می‌شود.');
    if (!confirmed) {
      event.preventDefault();
      return false;
    }
  });

  updateBulkDeleteButtonState();
}

// Setup money normalization for all form submissions (both AJAX and traditional)
function setupFormMoneyNormalization() {
  document.addEventListener('submit', function(e) {
    const form = e.target;
    if (!form || !form.tagName || form.tagName.toLowerCase() !== 'form') return;

    // Normalize all money inputs before submission
    form.querySelectorAll('.money-input').forEach(input => {
      if (input.value) {
        let cleanValue = input.value.toString().replace(/,/g, '');
        cleanValue = normalizeDigits(cleanValue);
        input.value = cleanValue;
      }
    });
  }, true); // Use capture phase to run before form's own handlers
}

// Run on document ready
document.addEventListener('DOMContentLoaded', initUIHelpers);

// Also run when modals are shown (for dynamically loaded content)
document.addEventListener('shown.bs.modal', function() {
  initMoneyInputs();
  initPersianDatepickers();
  setupModalForms();
});

// Export for use in other scripts
window.UIHelpers = {
  formatNumber,
  parseFormattedNumber,
  normalizeDigits,
  normalizeFormDataForSubmission,
  getCookie,
  initMoneyInputs,
  formatNumberDisplays,
  initPersianDatepickers,
  setupModalForms,
  showFormErrors,
  showNotification,
  initUIHelpers,
};

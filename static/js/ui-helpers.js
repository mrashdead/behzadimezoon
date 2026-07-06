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
function initPersianDatepickers() {
  if (typeof flatpickr === 'undefined') return;

  // Date only picker
  document.querySelectorAll('.p-date-only').forEach(el => {
    if (!el.flatpickr) {
      flatpickr(el, {
        mode: 'single',
        dateFormat: 'Y/m/d',
        locale: 'fa',
      });
    }
  });

  // Date + Time picker
  document.querySelectorAll('.p-date-time').forEach(el => {
    if (!el.flatpickr) {
      flatpickr(el, {
        mode: 'single',
        dateFormat: 'Y/m/d H:i',
        enableTime: true,
        locale: 'fa',
      });
    }
  });

  // Time only picker
  document.querySelectorAll('.p-time-only').forEach(el => {
    if (!el.flatpickr) {
      flatpickr(el, {
        mode: 'single',
        dateFormat: 'H:i',
        enableTime: true,
        noCalendar: true,
        locale: 'fa',
      });
    }
  });

  // Week only picker
  document.querySelectorAll('.p-week-only').forEach(el => {
    if (!el.flatpickr) {
      flatpickr(el, {
        mode: 'single',
        dateFormat: 'Y/W',
        locale: 'fa',
        weekNumbers: true,
      });
    }
  });

  // Month only picker
  document.querySelectorAll('.p-month-only').forEach(el => {
    if (!el.flatpickr) {
      flatpickr(el, {
        mode: 'single',
        dateFormat: 'Y/m',
        locale: 'fa',
      });
    }
  });

  // Date range picker
  document.querySelectorAll('.p-date-range').forEach(el => {
    if (!el.flatpickr) {
      flatpickr(el, {
        mode: 'range',
        dateFormat: 'Y/m/d',
        locale: 'fa',
      });
    }
  });

  // Multiple dates picker
  document.querySelectorAll('.p-multiple-date').forEach(el => {
    if (!el.flatpickr) {
      flatpickr(el, {
        mode: 'multiple',
        dateFormat: 'Y/m/d',
        locale: 'fa',
      });
    }
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
function showNotification(message, type = 'info') {
  const alertClass = `alert-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info'}`;
  const alertHtml = `
    <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
      ${message}
      <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    </div>
  `;

  const container = document.querySelector('main') || document.body;
  const alertDiv = document.createElement('div');
  alertDiv.innerHTML = alertHtml;
  container.insertBefore(alertDiv.firstElementChild, container.firstChild);

  // Auto-dismiss after 5 seconds
  setTimeout(() => {
    container.querySelector('.alert').remove();
  }, 5000);
}

// Initialize all UI helpers
function initUIHelpers() {
  initMoneyInputs();
  formatNumberDisplays();
  initPersianDatepickers();
  setupModalForms();
  setupFormMoneyNormalization();
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
  initMoneyInputs,
  formatNumberDisplays,
  initPersianDatepickers,
  setupModalForms,
  showFormErrors,
  showNotification,
  initUIHelpers,
};

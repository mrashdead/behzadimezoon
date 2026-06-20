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

// Setup AJAX form submission for modals
function setupModalForms() {
  document.querySelectorAll('.modal form').forEach(form => {
    if (form.dataset.uiHelpersSubmitBound === '1') {
      return;
    }
    form.dataset.uiHelpersSubmitBound = '1';

    form.addEventListener('submit', function (e) {
      if (form.classList.contains('no-ajax')) {
        return;
      }

      e.preventDefault();

      const formData = normalizeFormDataForSubmission(form);
      const url = form.getAttribute('action');
      const modal = form.closest('.modal');
      const modalInstance = bootstrap.Modal.getInstance(modal);

      fetch(url, {
        method: 'POST',
        body: formData,
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
        },
      })
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            // Close modal
            if (modalInstance) {
              modalInstance.hide();
            }
            // Show success message
            if (data.message) {
              showNotification(data.message, 'success');
            }
            // Reload page or table
            setTimeout(() => {
              location.reload();
            }, 500);
          } else {
            // Show error messages
            if (data.errors) {
              showFormErrors(form, data.errors);
            } else if (data.message) {
              showNotification(data.message, 'error');
            }
          }
        })
        .catch(error => {
          console.error('Error:', error);
          showNotification('خطایی در فرم به وجود آمد', 'error');
        });
    });
  });
}

// Display form validation errors
function showFormErrors(form, errors) {
  // Clear previous errors
  form.querySelectorAll('.invalid-feedback').forEach(el => {
    el.remove();
  });
  form.querySelectorAll('.form-control.is-invalid').forEach(el => {
    el.classList.remove('is-invalid');
  });

  // Show new errors
  Object.keys(errors).forEach(fieldName => {
    const errorMessages = errors[fieldName];
    const field = form.querySelector(`[name="${fieldName}"]`);

    if (field) {
      field.classList.add('is-invalid');
      const errorDiv = document.createElement('div');
      errorDiv.className = 'invalid-feedback d-block';
      errorDiv.textContent = errorMessages.join(', ');
      field.parentNode.insertBefore(errorDiv, field.nextSibling);
    }
  });
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

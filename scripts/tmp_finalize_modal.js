
(function() {
  const scriptElement = document.currentScript;

  function findAssociatedForm(scriptEl) {
    let el = scriptEl ? scriptEl.previousElementSibling : null;
    while (el) {
      if (el.matches && el.matches('form.finalize-delivery-form')) return el;
      if (el.querySelector) {
        const f = el.querySelector('form.finalize-delivery-form');
        if (f) return f;
      }
      el = el.previousElementSibling;
    }
    // fallback: try to find any finalize-delivery form nearby
    return document.querySelector('form.finalize-delivery-form[data-finalization-url]');
  }

  const form = findAssociatedForm(scriptElement);
  const formId = form ? form.id : '';
  const reservationId = form ? Number(form.getAttribute('data-reservation-id') || (form.id ? form.id.replace('finalizeDeliveryForm', '') : 0)) || 0 : 0;
  const finalizationUrl = form ? form.getAttribute('data-finalization-url') || '' : '';

  document.addEventListener('DOMContentLoaded', function() {
  const toggleBtnId = 'toggleAdditionalFeeForm' + reservationId;
  const formContainerId = 'additionalFeeFormContainer' + reservationId;
  const submitFeeBtnId = 'submitFeeBtn' + reservationId;
  const cancelFeeBtnId = 'cancelFeeBtn' + reservationId;
  const containerElementId = 'additionalFeesContainer' + reservationId;
  const feeSummaryId = 'feeSummary' + reservationId;

  const toggleBtn = document.getElementById(toggleBtnId);
  const formContainer = document.getElementById(formContainerId);
  const submitFeeBtn = document.getElementById(submitFeeBtnId);
  const cancelFeeBtn = document.getElementById(cancelFeeBtnId);
  const containerElement = document.getElementById(containerElementId);
  const feeSummary = document.getElementById(feeSummaryId);

  // Helper functions
  function normalizeDigits(value) {
    const persianDigits = '۰۱۲۳۴۵۶۷۸۹';
    const englishDigits = '0123456789';
    
    let normalized = value.toString();
    for (let i = 0; i < 10; i++) {
      normalized = normalized.replace(new RegExp(persianDigits[i], 'g'), englishDigits[i]);
    }
    normalized = normalized.replace(/,/g, '').replace(/[^\d]/g, '');
    return parseInt(normalized) || 0;
  }

  function formatCurrency(value) {
    if (!value && value !== 0) return '';
    const numericValue = normalizeDigits(value.toString());
    const num = parseInt(numericValue, 10) || 0;
    return num.toLocaleString('fa-IR');
  }

  function showToast(type, message) {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
      toastContainer = document.createElement('div');
      toastContainer.id = 'toastContainer';
      toastContainer.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; width: 300px;';
      document.body.appendChild(toastContainer);
    }

    // Create toast element
    const toastId = 'toast_' + Date.now();
    const bgClass = type === 'success' ? 'bg-success' : 'bg-danger';
    const toastHtml = '' +
      '<div id="' + toastId + '" class="toast show" role="alert" aria-live="assertive">' +
        '<div class="toast-header ' + bgClass + ' text-white">' +
          '<strong class="me-auto">' +
            (type === 'success' ? '✓ موفق' : '✕ خطا') +
          '</strong>' +
          '<button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>' +
        '</div>' +
        '<div class="toast-body">' +
          message +
        '</div>' +
      '</div>';

    toastContainer.insertAdjacentHTML('beforeend', toastHtml);

    // Auto remove after 4 seconds
    setTimeout(() => {
      const toastEl = document.getElementById(toastId);
      if (toastEl) {
        toastEl.remove();
      }
    }, 4000);
  }

  // Format all currency displays on page load
  function formatAllCurrencies() {
    // Format financial summary
    const baseRemainingElem = document.getElementById('baseRemainingAmount' + reservationId);
    if (baseRemainingElem && baseRemainingElem.textContent) {
      const text = baseRemainingElem.textContent.replace('تومان', '').trim();
      baseRemainingElem.textContent = formatCurrency(text) + ' تومان';
    }

    const finalRemainingElem = document.getElementById('finalRemainingAmount' + reservationId);
    if (finalRemainingElem && finalRemainingElem.textContent) {
      const text = finalRemainingElem.textContent.replace('تومان', '').trim();
      finalRemainingElem.textContent = formatCurrency(text) + ' تومان';
    }

    const paymentAmountElem = document.getElementById('paymentAmount' + reservationId);
    if (paymentAmountElem && paymentAmountElem.value) {
      paymentAmountElem.value = formatCurrency(paymentAmountElem.value);
    }
  }

  function syncInitialVisibility() {
    const paymentSection = document.getElementById('paymentSection' + reservationId);
    const settledNotice = document.getElementById('settledNotice' + reservationId);
    const requiredPaymentAmountElem = document.getElementById('requiredPaymentAmount' + reservationId);
    const initialRemaining = requiredPaymentAmountElem ? normalizeDigits(requiredPaymentAmountElem.textContent) : 0;

    if (paymentSection) {
      paymentSection.style.display = initialRemaining > 0 ? 'block' : 'none';
    }
    if (settledNotice) {
      settledNotice.style.display = initialRemaining > 0 ? 'none' : 'block';
    }

    if (feeSummary && containerElement) {
      feeSummary.style.display = containerElement.querySelector('.fee-item') ? 'block' : 'none';
    }
  }

  // Initialize currency formatting and visibility
  formatAllCurrencies();
  syncInitialVisibility();

  // Toggle form visibility
  if (toggleBtn) {
    toggleBtn.addEventListener('click', function() {
      formContainer.style.display = formContainer.style.display === 'none' ? 'block' : 'none';
      if (formContainer.style.display === 'block') {
        const titleInput = formContainer.querySelector('.fee-title-input');
        if (titleInput) titleInput.focus();
      }
    });
  }

  if (cancelFeeBtn) {
    cancelFeeBtn.addEventListener('click', function() {
      formContainer.style.display = 'none';
      formContainer.querySelector('.fee-title-input').value = '';
      formContainer.querySelector('.fee-amount-input').value = '';
      formContainer.querySelector('.fee-notes-input').value = '';
    });
  }

  // Submit fee form via AJAX
  if (submitFeeBtn) {
    submitFeeBtn.addEventListener('click', function() {
      const titleInput = formContainer.querySelector('.fee-title-input');
      const amountInput = formContainer.querySelector('.fee-amount-input');
      const notesInput = formContainer.querySelector('.fee-notes-input');
      const csrfTokenInput = form ? form.querySelector('input[name="csrfmiddlewaretoken"]') : null;

      if (!containerElement || !feeSummary || !formContainer || !csrfTokenInput) {
        showToast('error', 'اجزای فرم هزینه جانبی در دسترس نیستند');
        return;
      }

      if (!titleInput.value.trim()) {
        showToast('error', 'لطفاً عنوان هزینه را وارد کنید');
        return;
      }

      if (!amountInput.value.trim()) {
        showToast('error', 'لطفاً مبلغ هزینه را وارد کنید');
        return;
      }

      const normalizedAmount = normalizeDigits(amountInput.value);

      const formData = new FormData();
      formData.append('csrfmiddlewaretoken', csrfTokenInput ? csrfTokenInput.value : '');
      formData.append('action', 'add_fee');
      formData.append('title', titleInput.value.trim());
      formData.append('amount', normalizedAmount);
      formData.append('notes', notesInput.value.trim());

      // Post to the finalize-delivery endpoint which also accepts add_fee action
      const postUrl = finalizationUrl || (form ? form.action : window.location.href);

      const headers = { 'X-Requested-With': 'XMLHttpRequest' };
      const csrfVal = csrfTokenInput ? csrfTokenInput.value : (document.querySelector('[name="csrfmiddlewaretoken"]') ? document.querySelector('[name="csrfmiddlewaretoken"]').value : null);
      if (csrfVal) headers['X-CSRFToken'] = csrfVal;

      fetch(postUrl, {
        method: 'POST',
        headers: headers,
        body: formData
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          showToast('success', data.message);

          const feeHtml = '' +
            '<div class="alert alert-info mb-2 d-flex justify-content-between align-items-center fee-item" data-fee-id="' + data.fee_id + '">' +
              '<div class="flex-grow-1">' +
                '<strong>' + data.fee_title + '</strong>' +
              '</div>' +
              '<div class="text-nowrap ms-2">' +
                '<strong>' + formatCurrency(data.fee_amount) + ' تومان</strong>' +
              '</div>' +
            '</div>';
          
          const noFeesAlert = containerElement.querySelector('.alert-light');
          if (noFeesAlert) {
            noFeesAlert.remove();
          }

          containerElement.insertAdjacentHTML('beforeend', feeHtml);
          updateFinancialSummary(data.total_fees, data.new_remaining);
          feeSummary.style.display = 'block';

          titleInput.value = '';
          amountInput.value = '';
          notesInput.value = '';
          formContainer.style.display = 'none';
        } else {
          showToast('error', data.message || 'خطایی در ثبت هزینه رخ داد');
        }
      })
      .catch(error => {
        console.error('Error:', error);
        showToast('error', 'خطا در ارتباط با سرور');
      });
    });
  }

  function updateFinancialSummary(totalFees, newRemaining) {
    const totalFeesElem = document.getElementById('totalFeesAmount' + reservationId);
    if (totalFeesElem) {
      totalFeesElem.textContent = formatCurrency(totalFees) + ' تومان';
    }

    const finalRemainingElem = document.getElementById('finalRemainingAmount' + reservationId);
    if (finalRemainingElem) {
      finalRemainingElem.textContent = formatCurrency(newRemaining) + ' تومان';
    }

    const paymentSection = document.getElementById('paymentSection' + reservationId);
    const settledNotice = document.getElementById('settledNotice' + reservationId);

    if (paymentSection) {
      paymentSection.style.display = newRemaining > 0 ? 'block' : 'none';
    }
    if (settledNotice) {
      settledNotice.style.display = newRemaining > 0 ? 'none' : 'block';
    }

    const paymentAmountInput = document.getElementById('paymentAmount' + reservationId);
    if (paymentAmountInput) {
      paymentAmountInput.value = formatCurrency(newRemaining);
    }

    const requiredPaymentAmountElem = document.getElementById('requiredPaymentAmount' + reservationId);
    if (requiredPaymentAmountElem) {
      requiredPaymentAmountElem.textContent = formatCurrency(newRemaining) + ' تومان';
    }

    const alertRemainingAmountElem = document.getElementById('alertRemainingAmount' + reservationId);
    if (alertRemainingAmountElem) {
      alertRemainingAmountElem.textContent = formatCurrency(newRemaining) + ' تومان';
    }
  }

  // Handle form submission
  if (form) {
    form.addEventListener('submit', function(e) {
      e.preventDefault();
      console.log('Form submission started');
      
      // Get payment fields
      const paymentAmountInput = form.querySelector('input[name="remaining_payment_amount"]');
      const paymentMethodSelect = form.querySelector('select[name="remaining_payment_method"]');
      const paymentCodeInput = form.querySelector('input[name="remaining_payment_tracking_code"]');

      // Check if fields exist and validate
      if (!paymentAmountInput) {
        console.warn('Payment amount input not found');
        showToast('error', 'فیلد مبلغ پرداخت یافت نشد');
        return;
      }

      // If remaining amount is 0, payment fields are optional
      const requiredPaymentAmount = document.getElementById('requiredPaymentAmount' + reservationId);
      const requiredAmount = requiredPaymentAmount ? normalizeDigits(requiredPaymentAmount.textContent) : 0;

      console.log('Required amount:', requiredAmount);
      console.log('Payment amount input value:', paymentAmountInput.value);

      // Normalize payment amount if it has value
      if (paymentAmountInput.value) {
        const normalized = normalizeDigits(paymentAmountInput.value);
        console.log('Normalized payment amount:', normalized);
        paymentAmountInput.value = normalized;
      }

      // Validate payment fields if needed
      if (requiredAmount > 0) {
        if (!paymentAmountInput.value || normalizeDigits(paymentAmountInput.value) === 0) {
          showToast('error', 'لطفاً مبلغ پرداخت را وارد کنید');
          return;
        }
        if (!paymentMethodSelect || !paymentMethodSelect.value) {
          showToast('error', 'لطفاً روش پرداخت را انتخاب کنید');
          return;
        }
        if (!paymentCodeInput || !paymentCodeInput.value.trim()) {
          showToast('error', 'لطفاً کد رهگیری پرداخت را وارد کنید');
          return;
        }
      }

      // Create FormData from form
      const formData = new FormData(form);
      
      console.log('Form data keys:', Array.from(formData.keys()));
      
      fetch(finalizationUrl, {
        method: 'POST',
        body: formData
      })
      .then(response => {
        console.log('Response status:', response.status);
        if (!response.ok) {
          return response.text().then(text => {
            console.error('Response text:', text);
            throw new Error('HTTP Error: ' + response.status + ' - ' + text);
          });
        }
        return response.json();
      })
      .then(data => {
        console.log('Response data:', data);
        if (data.success) {
          showToast('success', data.message);
          // Close modal
          const modalElement = document.getElementById('finalizeDeliveryModal' + reservationId);
          if (modalElement) {
            const modal = bootstrap.Modal.getInstance(modalElement);
            if (modal) {
              modal.hide();
            }
          }
          // Reload page after 1.5 seconds
          setTimeout(() => {
            window.location.reload();
          }, 1500);
        } else {
          showToast('error', data.message || 'خطایی رخ داد');
        }
      })
      .catch(error => {
        console.error('Fetch error:', error);
        showToast('error', 'خطا در ارتباط با سرور: ' + error.message);
      });
    });
  } else {
    console.warn('Form element not found with ID:', formId);
  }
  });
})();

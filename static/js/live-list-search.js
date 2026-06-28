document.addEventListener('DOMContentLoaded', function () {
  const liveSearchForms = document.querySelectorAll('[data-live-search-form]');

  if (!liveSearchForms.length) return;

  liveSearchForms.forEach((form) => {
    const targetSelector = form.dataset.liveSearchTarget;
    const target = targetSelector ? document.querySelector(targetSelector) : null;
    const input = form.querySelector('input[name="search"]');
    const clearButton = form.querySelector('.live-search-clear');
    const statusText = form.querySelector('.live-search-status');
    let debounceTimer = null;

    if (!target || !input) return;

    function updateClearButton() {
      if (!clearButton) return;
      clearButton.classList.toggle('d-none', !input.value.trim());
    }

    function renderStatus(message) {
      if (!statusText) return;
      statusText.textContent = message;
    }

    function buildUrl(page) {
      const url = new URL(form.action || window.location.href, window.location.origin);
      url.searchParams.set('search', input.value.trim());
      if (page) {
        url.searchParams.set('page', page);
      } else {
        url.searchParams.delete('page');
      }
      url.searchParams.set('ajax', '1');
      return url;
    }

    function updateHistory(page) {
      if (!window.history.replaceState) return;
      const url = new URL(form.action || window.location.href, window.location.origin);
      url.searchParams.set('search', input.value.trim());
      if (page) {
        url.searchParams.set('page', page);
      } else {
        url.searchParams.delete('page');
      }
      window.history.replaceState({}, '', url);
    }

    function fetchResults(page) {
      const url = buildUrl(page);
      renderStatus('در حال جستجو...');
      target.classList.add('opacity-75');

      fetch(url.toString(), {
        headers: {
          'X-Requested-With': 'XMLHttpRequest'
        }
      })
        .then((response) => response.text())
        .then((html) => {
          target.innerHTML = html;
          updateHistory(page);
          renderStatus('');
        })
        .catch((error) => {
          console.error('Search request failed:', error);
          renderStatus('خطا در بارگذاری نتایج');
        })
        .finally(() => {
          target.classList.remove('opacity-75');
        });
    }

    function onInputChanged() {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        fetchResults(1);
      }, 350);
      updateClearButton();
    }

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      clearTimeout(debounceTimer);
      fetchResults(1);
    });

    input.addEventListener('input', onInputChanged);

    if (clearButton) {
      clearButton.addEventListener('click', function () {
        input.value = '';
        updateClearButton();
        fetchResults(1);
      });
    }

    target.addEventListener('click', function (event) {
      const link = event.target.closest('a.page-link');
      if (!link) return;
      event.preventDefault();
      const page = new URL(link.href, window.location.origin).searchParams.get('page');
      fetchResults(page);
    });

    updateClearButton();
  });
});

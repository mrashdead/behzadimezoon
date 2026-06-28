document.addEventListener('DOMContentLoaded', function () {
  function createCombobox(wrapper) {
    const input = wrapper.querySelector('[data-combobox-input]');
    const list = wrapper.querySelector('[data-combobox-list]');
    const select = wrapper.querySelector('[data-combobox-select]');
    if (!input || !list || !select) return;

    const options = Array.from(select.querySelectorAll('option')).slice(1).map(option => ({
      id: option.value,
      text: option.textContent.trim(),
    }));

    let activeIndex = -1;
    let selectedId = select.value || '';
    let selectedText = '';

    function updateList(filterText) {
      list.innerHTML = '';
      const normalizedFilter = filterText.trim().toLowerCase();
      const visible = options.filter(option => {
        return normalizedFilter === '' || option.text.toLowerCase().includes(normalizedFilter);
      });

      if (visible.length === 0) {
        const row = document.createElement('div');
        row.className = 'combobox-no-results';
        row.textContent = 'موردی یافت نشد.';
        list.appendChild(row);
        return;
      }

      visible.forEach((option, index) => {
        const item = document.createElement('div');
        item.className = 'combobox-item';
        item.setAttribute('role', 'option');
        item.dataset.id = option.id;
        item.dataset.index = index;
        item.textContent = option.text;
        if (option.id === selectedId) {
          item.classList.add('selected');
        }
        if (index === activeIndex) {
          item.classList.add('active');
        }
        item.addEventListener('mousedown', function (event) {
          event.preventDefault();
          selectOption(option.id, option.text);
        });
        list.appendChild(item);
      });
    }

    function openList() {
      if (list.classList.contains('d-none')) {
        list.classList.remove('d-none');
      }
      wrapper.classList.add('combobox-open');
    }

    function closeList() {
      list.classList.add('d-none');
      activeIndex = -1;
    }

    const clearBtn = wrapper.querySelector('[data-combobox-clear]');

    function setClearVisibility() {
      if (!clearBtn) return;
      const show = selectedId || input.value.trim();
      clearBtn.classList.toggle('d-none', !show);
    }

    function selectOption(id, text) {
      selectedId = id;
      selectedText = text;
      input.value = text;
      select.value = id;
      updateList(text);
      setClearVisibility();
      closeList();
    }

    function clearSelection() {
      selectedId = '';
      selectedText = '';
      select.value = '';
      input.value = '';
      updateList('');
      setClearVisibility();
    }

    if (clearBtn) {
      clearBtn.addEventListener('click', function (event) {
        event.preventDefault();
        clearSelection();
        input.focus();
      });
    }

    input.addEventListener('input', function () {
      const value = input.value;
      if (selectedId && value !== selectedText) {
        clearSelection();
      }
      updateList(value);
      openList();
    });

    input.addEventListener('focus', function () {
      updateList(input.value);
      openList();
    });

    input.addEventListener('blur', function () {
      setTimeout(closeList, 150);
    });

    input.addEventListener('keydown', function (event) {
      const items = Array.from(list.querySelectorAll('.combobox-item'));
      if (list.classList.contains('d-none') && event.key === 'ArrowDown') {
        event.preventDefault();
        updateList(input.value);
        openList();
        return;
      }

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        activeIndex = Math.min(activeIndex + 1, items.length - 1);
        items.forEach((item, index) => item.classList.toggle('active', index === activeIndex));
        if (items[activeIndex]) {
          items[activeIndex].scrollIntoView({ block: 'nearest' });
        }
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
        items.forEach((item, index) => item.classList.toggle('active', index === activeIndex));
        if (items[activeIndex]) {
          items[activeIndex].scrollIntoView({ block: 'nearest' });
        }
      }
      if (event.key === 'Enter' && activeIndex >= 0) {
        event.preventDefault();
        const item = list.querySelector('.combobox-item.active');
        if (item) {
          selectOption(item.dataset.id, item.textContent.trim());
        }
      }
    });

    if (selectedId) {
      const selectedOption = options.find(option => option.id === selectedId);
      if (selectedOption) {
        selectedText = selectedOption.text;
        input.value = selectedText;
      }
    }
    setClearVisibility();
  }

  document.querySelectorAll('.combobox-wrapper').forEach(createCombobox);
});

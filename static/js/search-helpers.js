/**
 * Search Helper Functions for Reservation Form
 * Implements real-time filtering for customer and product selection
 */

class SearchableSelect {
    constructor(containerId, dataSource, options = {}) {
        this.container = document.getElementById(containerId);
        this.dataSource = dataSource; // Array of objects with id, name properties
        this.options = {
            searchPlaceholder: 'جستجو کنید...',
            noResultsMessage: 'نتیجه‌ای پیدا نشد.',
            maxDisplayItems: 50,
            ...options
        };

        this.init();
    }

    init() {
        if (!this.container) return;

        // Create search input
        this.searchInput = document.createElement('input');
        this.searchInput.type = 'text';
        this.searchInput.className = 'form-control mb-2 search-input';
        this.searchInput.placeholder = this.options.searchPlaceholder;
        this.searchInput.setAttribute('autocomplete', 'off');

        // Create list container
        this.listContainer = document.createElement('div');
        this.listContainer.className = 'search-list-container';
        this.listContainer.style.maxHeight = '300px';
        this.listContainer.style.overflowY = 'auto';
        this.listContainer.style.border = '1px solid #e9ecef';
        this.listContainer.style.borderRadius = '4px';
        this.listContainer.style.padding = '0';

        // Create hidden select for form submission
        this.hiddenSelect = document.createElement('select');
        this.hiddenSelect.name = this.container.dataset.fieldName || 'item';
        this.hiddenSelect.className = 'd-none';
        this.hiddenSelect.required = this.container.dataset.required === 'true';

        // Add options to hidden select
        this.dataSource.forEach(item => {
            const option = document.createElement('option');
            option.value = item.id;
            option.textContent = item.name;
            this.hiddenSelect.appendChild(option);
        });

        // Append elements
        this.container.appendChild(this.searchInput);
        this.container.appendChild(this.listContainer);
        this.container.appendChild(this.hiddenSelect);

        // Setup event listeners
        this.searchInput.addEventListener('input', () => this.performSearch());
        this.searchInput.addEventListener('focus', () => this.showAllItems());

        // Initial render
        this.renderItems(this.dataSource);
    }

    performSearch() {
        const query = this.searchInput.value.toLowerCase().trim();

        if (!query) {
            this.renderItems(this.dataSource);
            return;
        }

        // Filter items
        const filtered = this.dataSource.filter(item =>
            item.name.toLowerCase().includes(query)
        );

        this.renderItems(filtered);
    }

    renderItems(items) {
        this.listContainer.innerHTML = '';

        if (items.length === 0) {
            this.listContainer.innerHTML = `
                <div class="p-3 text-center text-muted">
                    <small>${this.options.noResultsMessage}</small>
                </div>
            `;
            return;
        }

        // Limit display items
        const displayItems = items.slice(0, this.options.maxDisplayItems);

        displayItems.forEach(item => {
            const itemElement = document.createElement('div');
            itemElement.className = 'search-list-item p-2 border-bottom cursor-pointer hover-bg';
            itemElement.style.cursor = 'pointer';
            itemElement.style.paddingLeft = '12px';
            itemElement.style.paddingRight = '12px';
            itemElement.dataset.id = item.id;
            itemElement.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span>${this.highlightMatch(item.name)}</span>
                </div>
            `;

            itemElement.addEventListener('click', () => this.selectItem(item));
            itemElement.addEventListener('mouseenter', () => {
                itemElement.style.backgroundColor = '#f8f9fa';
            });
            itemElement.addEventListener('mouseleave', () => {
                itemElement.style.backgroundColor = 'transparent';
            });

            this.listContainer.appendChild(itemElement);
        });

        if (items.length > this.options.maxDisplayItems) {
            const moreElement = document.createElement('div');
            moreElement.className = 'p-2 text-center text-muted';
            moreElement.style.fontSize = '12px';
            moreElement.innerHTML = `${items.length - this.options.maxDisplayItems} نتیجه بیشتر...`;
            this.listContainer.appendChild(moreElement);
        }
    }

    highlightMatch(text) {
        const query = this.searchInput.value.toLowerCase().trim();
        if (!query) return text;

        const regex = new RegExp(`(${query})`, 'gi');
        return text.replace(regex, '<strong style="background-color: #fff3cd;">$1</strong>');
    }

    selectItem(item) {
        // Update search input
        this.searchInput.value = item.name;

        // Update hidden select
        this.hiddenSelect.value = item.id;

        // Trigger change event
        const event = new Event('change', { bubbles: true });
        this.hiddenSelect.dispatchEvent(event);

        // Collapse list (show only selected)
        this.renderSelectedOnly(item);
    }

    renderSelectedOnly(item) {
        this.listContainer.innerHTML = `
            <div class="search-list-item p-2 bg-info-subtle">
                <div class="d-flex justify-content-between align-items-center">
                    <span class="fw-semibold">${item.name}</span>
                    <button type="button" class="btn btn-sm btn-link text-danger clear-selection" style="padding: 0; font-size: 12px;">
                        <i class="fi fi-rr-delete"></i> پاک کردن
                    </button>
                </div>
            </div>
        `;

        const clearBtn = this.listContainer.querySelector('.clear-selection');
        clearBtn.addEventListener('click', () => this.clearSelection());
    }

    clearSelection() {
        this.searchInput.value = '';
        this.hiddenSelect.value = '';
        const event = new Event('change', { bubbles: true });
        this.hiddenSelect.dispatchEvent(event);
        this.renderItems(this.dataSource);
    }

    showAllItems() {
        if (this.searchInput.value === '') {
            this.renderItems(this.dataSource);
        }
    }

    getValue() {
        return this.hiddenSelect.value;
    }

    setValue(value) {
        this.hiddenSelect.value = value;
        const item = this.dataSource.find(i => i.id == value);
        if (item) {
            this.selectItem(item);
        }
    }

    getSelect() {
        return this.hiddenSelect;
    }
}

// Initialize search for customers dropdown
function initializeCustomerSearch(customers) {
    const container = document.getElementById('customerSearchContainer');
    if (!container) return;

    const customerData = customers.map(c => ({
        id: c.id,
        name: c.name || `${c.bride_first_name} ${c.bride_last_name}`
    }));

    new SearchableSelect('customerSearchContainer', customerData, {
        searchPlaceholder: 'نام عروس، نام داماد یا شماره تماس را جستجو کنید...',
        noResultsMessage: 'هیچ مشتری‌ای پیدا نشد.'
    });
}

// Initialize search for dresses dropdown
function initializeDressSearch(dresses) {
    const container = document.getElementById('dressSearchContainer');
    if (!container) return;

    const dressData = dresses.map(d => ({
        id: d.id,
        name: d.code
    }));

    new SearchableSelect('dressSearchContainer', dressData, {
        searchPlaceholder: 'کد لباس را جستجو کنید...',
        noResultsMessage: 'هیچ لباسی پیدا نشد.'
    });
}

/**
 * Add hover effect to search list items
 */
document.addEventListener('DOMContentLoaded', function() {
    const style = document.createElement('style');
    style.textContent = `
        .search-list-item {
            transition: background-color 0.2s ease;
        }

        .search-list-item:hover {
            background-color: #f8f9fa;
        }

        .search-list-container {
            border: 1px solid #dee2e6;
        }

        .search-list-container .search-list-item:last-child {
            border-bottom: none;
        }

        .search-input:focus {
            box-shadow: 0 0 0 0.2rem rgba(13, 110, 253, 0.25);
        }
    `;
    document.head.appendChild(style);
});

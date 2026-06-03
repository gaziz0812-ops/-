(function () {
    var productCache = {};

    function parseNumber(value) {
        var number = parseFloat(String(value || '').replace(',', '.'));
        return Number.isFinite(number) ? number : 0;
    }

    function formatMoney(value) {
        return value.toFixed(2);
    }

    function getBaseAdminUrl() {
        return window.location.pathname.replace(/(?:add\/|\d+\/change\/?)$/, '');
    }

    function getProductPreviewUrl(productId) {
        return getBaseAdminUrl() + 'product-preview/' + productId + '/';
    }

    function getOrderRows() {
        return Array.from(document.querySelectorAll('tr.form-row'))
            .filter(function (row) {
                return row.id.indexOf('items-') === 0 && !row.classList.contains('empty-form');
            });
    }

    function getRowFromField(field) {
        return field ? field.closest('tr.form-row') : null;
    }

    function getField(row, fieldName) {
        return row.querySelector('[name$="-' + fieldName + '"]');
    }

    function getFieldCell(row, fieldName) {
        return row.querySelector('.field-' + fieldName);
    }

    function setCalculatedCell(row, fieldName, value) {
        var cell = getFieldCell(row, fieldName);
        if (!cell) {
            return;
        }

        var paragraph = cell.querySelector('p');
        if (paragraph) {
            paragraph.textContent = value;
            return;
        }

        cell.textContent = value;
    }

    function ensurePreview(row) {
        var preview = row.querySelector('.order-item-live-preview');
        if (preview) {
            return preview;
        }

        var targetCell = getFieldCell(row, 'discount_percent') || getFieldCell(row, 'product') || row.querySelector('td');
        if (!targetCell) {
            return null;
        }

        preview = document.createElement('div');
        preview.className = 'order-item-live-preview';
        preview.style.marginTop = '6px';
        preview.style.padding = '6px 8px';
        preview.style.borderLeft = '4px solid #79aec8';
        preview.style.background = '#f8fbfd';
        preview.style.lineHeight = '1.5';
        preview.style.whiteSpace = 'nowrap';
        preview.textContent = 'Выберите товар, количество и скидку.';

        targetCell.appendChild(preview);
        return preview;
    }

    function renderPreview(row, productData) {
        var quantityField = getField(row, 'quantity');
        var discountField = getField(row, 'discount_percent');
        var preview = ensurePreview(row);

        if (!preview || !quantityField || !discountField) {
            return;
        }

        var basePrice = parseNumber(productData ? productData.sale_price : 0);
        var stockBalance = productData ? productData.stock_balance : 0;
        var quantity = parseNumber(quantityField.value);
        var discount = parseNumber(discountField.value);
        var unitPriceAfterDiscount = basePrice * (1 - discount / 100);
        var totalPrice = unitPriceAfterDiscount * quantity;

        setCalculatedCell(row, 'unit_price', formatMoney(basePrice));
        setCalculatedCell(row, 'unit_price_after_discount', formatMoney(unitPriceAfterDiscount));
        setCalculatedCell(row, 'total_price', formatMoney(totalPrice));

        preview.innerHTML = [
            '<strong>Цена:</strong> ' + formatMoney(basePrice),
            '<strong>Остаток:</strong> ' + stockBalance,
            '<strong>Скидка:</strong> ' + formatMoney(discount) + '%',
            '<strong>Цена со скидкой:</strong> ' + formatMoney(unitPriceAfterDiscount),
            '<strong>Сумма:</strong> ' + formatMoney(totalPrice)
        ].join('<br>');
    }

    function loadProduct(row) {
        var productField = getField(row, 'product');
        var productId = productField ? productField.value : '';

        ensurePreview(row);

        if (!productId) {
            renderPreview(row, null);
            return;
        }

        if (productCache[productId]) {
            renderPreview(row, productCache[productId]);
            return;
        }

        fetch(getProductPreviewUrl(productId))
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Product preview request failed');
                }

                return response.json();
            })
            .then(function (data) {
                productCache[productId] = data;
                renderPreview(row, data);
            })
            .catch(function () {
                var preview = ensurePreview(row);
                if (preview) {
                    preview.textContent = 'Не удалось загрузить данные товара.';
                }
            });
    }

    function updateRow(row) {
        if (!row || row.classList.contains('empty-form')) {
            return;
        }

        loadProduct(row);
    }

    function updateAllRows() {
        getOrderRows().forEach(updateRow);
    }

    document.addEventListener('change', function (event) {
        if (!event.target || !event.target.name || event.target.name.indexOf('items-') !== 0) {
            return;
        }

        updateRow(getRowFromField(event.target));
    });

    document.addEventListener('input', function (event) {
        if (!event.target || !event.target.name || event.target.name.indexOf('items-') !== 0) {
            return;
        }

        if (event.target.name.endsWith('-quantity') || event.target.name.endsWith('-discount_percent')) {
            updateRow(getRowFromField(event.target));
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        updateAllRows();

        if (window.django && window.django.jQuery) {
            window.django.jQuery(document).on('select2:select select2:clear', 'select[name^="items-"][name$="-product"]', function (event) {
                updateRow(getRowFromField(event.target));
            });

            window.django.jQuery(document).on('formset:added', function () {
                setTimeout(updateAllRows, 0);
            });
        }
    });
})();

(function () {
    function parseNumber(value) {
        var number = parseFloat(String(value || '').replace(',', '.'));
        return Number.isFinite(number) ? number : 0;
    }

    function formatMoney(value) {
        return value.toFixed(2);
    }

    function setReadonlyField(name, value) {
        var row = document.querySelector('.field-' + name);
        if (!row) {
            return;
        }

        var target = row.querySelector('.readonly') || row.querySelector('div') || row;
        target.textContent = value;
    }

    function ensurePreview() {
        var discountRow = document.querySelector('.field-discount_percent');
        if (!discountRow) {
            return null;
        }

        var preview = document.getElementById('sale-live-preview');
        if (preview) {
            return preview;
        }

        preview = document.createElement('div');
        preview.id = 'sale-live-preview';
        preview.style.margin = '8px 0 0 170px';
        preview.style.padding = '10px 12px';
        preview.style.borderLeft = '4px solid #79aec8';
        preview.style.background = '#f8fbfd';
        preview.style.lineHeight = '1.7';

        discountRow.appendChild(preview);
        return preview;
    }

    function setPreview(basePrice, stockBalance, discountValue, unitSalePrice, totalSaleAmount, profit) {
        var preview = ensurePreview();
        if (!preview) {
            return;
        }

        preview.innerHTML = [
            '<strong>Начальная цена:</strong> ' + formatMoney(basePrice),
            '<strong>Остаток:</strong> ' + stockBalance,
            '<strong>Скидка:</strong> ' + formatMoney(discountValue) + '%',
            '<strong>Цена с учетом скидки:</strong> ' + formatMoney(unitSalePrice),
            '<strong>Цена продажи:</strong> ' + formatMoney(totalSaleAmount),
            '<strong>Профит:</strong> ' + formatMoney(profit)
        ].join('<br>');
    }

    function calculateSale() {
        var product = document.getElementById('id_product');
        var quantity = document.getElementById('id_quantity');
        var discount = document.getElementById('id_discount_percent');
        var costPrice = document.getElementById('id_cost_price');

        if (!product || !quantity || !discount || !costPrice) {
            return;
        }

        var selectedOption = product.options[product.selectedIndex];
        var basePrice = parseNumber(selectedOption ? selectedOption.dataset.salePrice : 0);
        var stockBalance = selectedOption ? selectedOption.dataset.stockBalance || '0' : '0';
        var quantityValue = parseNumber(quantity.value);
        var discountValue = parseNumber(discount.value);
        var costPriceValue = parseNumber(costPrice.value);

        var discountMultiplier = 1 - (discountValue / 100);
        var unitSalePrice = basePrice * discountMultiplier;
        var totalSaleAmount = unitSalePrice * quantityValue;
        var profit = totalSaleAmount - (costPriceValue * quantityValue);

        setReadonlyField('unit_sale_price', formatMoney(unitSalePrice));
        setReadonlyField('total_sale_amount', formatMoney(totalSaleAmount));
        setReadonlyField('profit', formatMoney(profit));
        setPreview(basePrice, stockBalance, discountValue, unitSalePrice, totalSaleAmount, profit);
    }

    document.addEventListener('DOMContentLoaded', function () {
        ['id_product', 'id_quantity', 'id_discount_percent', 'id_cost_price'].forEach(function (id) {
            var field = document.getElementById(id);

            if (field) {
                field.addEventListener('change', calculateSale);
                field.addEventListener('input', calculateSale);
            }
        });

        calculateSale();
    });
})();

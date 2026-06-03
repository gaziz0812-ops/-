(function () {
    function ensurePreview() {
        var saleRow = document.querySelector('.field-sale');
        if (!saleRow) {
            return null;
        }

        var preview = document.getElementById('sale-return-preview');
        if (preview) {
            return preview;
        }

        preview = document.createElement('div');
        preview.id = 'sale-return-preview';
        preview.style.margin = '8px 0 0 170px';
        preview.style.padding = '10px 12px';
        preview.style.borderLeft = '4px solid #79aec8';
        preview.style.background = '#f8fbfd';
        preview.style.lineHeight = '1.7';

        saleRow.appendChild(preview);
        return preview;
    }

    function getOrderField() {
        return document.getElementById('id_order');
    }

    function getSaleField() {
        return document.getElementById('id_sale');
    }

    function getSelectedOrderId() {
        var orderField = getOrderField();
        return orderField ? orderField.value : '';
    }

    function getSelectedSaleId() {
        var saleField = getSaleField();
        return saleField ? saleField.value : '';
    }

    function getBaseAdminUrl() {
        return window.location.pathname.replace(/(?:add\/|\d+\/change\/?)$/, '');
    }

    function getSalesForOrderUrl(orderId) {
        return getBaseAdminUrl() + 'sales-for-order/' + orderId + '/';
    }

    function getSalePreviewUrl(saleId) {
        return getBaseAdminUrl() + 'sale-preview/' + saleId + '/';
    }

    function clearSaleOptions() {
        var saleField = getSaleField();
        if (!saleField) {
            return;
        }

        saleField.innerHTML = '<option value="">---------</option>';
    }

    function clearPreview(message) {
        var preview = ensurePreview();
        if (preview) {
            preview.textContent = message || '';
        }
    }

    function renderSaleOptions(sales) {
        var saleField = getSaleField();
        if (!saleField) {
            return;
        }

        clearSaleOptions();

        sales.forEach(function (sale) {
            var option = document.createElement('option');
            option.value = sale.id;
            option.textContent = sale.text;
            saleField.appendChild(option);
        });

        if (sales.length === 1) {
            saleField.value = String(sales[0].id);
            loadSalePreview();
        }
    }

    function renderSalePreview(data) {
        var preview = ensurePreview();
        if (!preview) {
            return;
        }

        preview.innerHTML = [
            '<strong>Заказ:</strong> #' + (data.order || '-'),
            '<strong>Продажа:</strong> #' + data.id,
            '<strong>Дата продажи:</strong> ' + data.created_at,
            '<strong>Товар:</strong> ' + data.product,
            '<strong>Покупатель:</strong> ' + (data.customer || '-'),
            '<strong>Количество:</strong> ' + data.quantity,
            '<strong>Скидка:</strong> ' + data.discount_percent + '%',
            '<strong>Цена за 1 шт.:</strong> ' + data.unit_sale_price,
            '<strong>Сумма продажи:</strong> ' + data.total_sale_amount
        ].join('<br>');
    }

    function loadSalesForOrder() {
        var orderId = getSelectedOrderId();

        clearSaleOptions();
        clearPreview('Выберите заказ.');

        if (!orderId) {
            return;
        }

        clearPreview('Загружаю продажи заказа...');

        fetch(getSalesForOrderUrl(orderId))
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Sales for order request failed');
                }

                return response.json();
            })
            .then(function (data) {
                if (!data.sales.length) {
                    clearPreview('У выбранного заказа нет проведенных продаж.');
                    return;
                }

                renderSaleOptions(data.sales);

                if (data.sales.length > 1) {
                    clearPreview('Выберите позицию продажи для возврата.');
                }
            })
            .catch(function () {
                clearPreview('Не удалось загрузить продажи заказа.');
            });
    }

    function loadSalePreview() {
        var saleId = getSelectedSaleId();

        if (!saleId) {
            clearPreview('Выберите позицию продажи для возврата.');
            return;
        }

        fetch(getSalePreviewUrl(saleId))
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Preview request failed');
                }

                return response.json();
            })
            .then(renderSalePreview)
            .catch(function () {
                clearPreview('Не удалось загрузить данные продажи.');
            });
    }

    document.addEventListener('change', function (event) {
        if (!event.target) {
            return;
        }

        if (event.target.id === 'id_order') {
            loadSalesForOrder();
        }

        if (event.target.id === 'id_sale') {
            loadSalePreview();
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        ensurePreview();

        if (window.django && window.django.jQuery) {
            window.django.jQuery(document).on('select2:select select2:clear', '#id_order', function () {
                setTimeout(loadSalesForOrder, 0);
            });
        }

        if (getSelectedOrderId()) {
            loadSalesForOrder();
        } else {
            clearPreview('Выберите заказ.');
        }
    });
})();

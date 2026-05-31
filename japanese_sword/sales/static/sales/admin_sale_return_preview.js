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

    function getSelectedSaleId() {
        var saleField = document.getElementById('id_sale');
        return saleField ? saleField.value : '';
    }

    function setPreview(data) {
        var preview = ensurePreview();
        if (!preview) {
            return;
        }

        preview.innerHTML = [
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

    function clearPreview() {
        var preview = ensurePreview();
        if (preview) {
            preview.textContent = '';
        }
    }

    function loadSalePreview() {
        var saleId = getSelectedSaleId();
        if (!saleId) {
            clearPreview();
            return;
        }

        fetch(getSalePreviewUrl(saleId))
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Preview request failed');
                }
                return response.json();
            })
            .then(setPreview)
            .catch(function () {
                var preview = ensurePreview();
                if (preview) {
                    preview.textContent = 'Не удалось загрузить данные продажи.';
                }
            });
    }

    function getSalePreviewUrl(saleId) {
        var path = window.location.pathname;
        var basePath = path.replace(/(?:add\/|\d+\/change\/?)$/, '');

        return basePath + 'sale-preview/' + saleId + '/';
    }

    document.addEventListener('DOMContentLoaded', function () {
        var saleField = document.getElementById('id_sale');
        if (!saleField) {
            return;
        }

        saleField.addEventListener('change', loadSalePreview);

        if (window.django && window.django.jQuery) {
            window.django.jQuery(document).on('select2:select select2:clear', '#id_sale', loadSalePreview);
        }

        loadSalePreview();
    });
})();

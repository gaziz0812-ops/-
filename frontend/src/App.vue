<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

// Легенда комментариев:
// [VUE] механизм Vue, который фреймворк понимает сам.
// [VITE] механизм Vite/dev-server.
// [TG] объект или данные Telegram Mini App.
// [OUR] наша переменная, функция или бизнес-логика.

// VITE_API_BASE_URL позволяет указать отдельный API; по умолчанию идем через Vite proxy на /api.
// [VITE] import.meta.env читает переменные окружения Vite.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

// ref хранит список товаров из Django API и обновляет экран при изменении.
// [VUE] ref делает значение реактивным; [OUR] products — наше состояние каталога.
const products = ref([])

// ref хранит локальную корзину: backend узнает о ней только при оформлении заказа.
// [VUE] ref делает значение реактивным; [OUR] cartItems — наша локальная корзина.
const cartItems = ref([])

// reactive хранит поля формы заказа как один связанный объект.
// [VUE] reactive делает объект формы реактивным; [OUR] customerForm — наша форма заказа.
const customerForm = reactive({
  customer_name: '',
  telegram_username: '',
  phone: '',
  customer_comment: '',
})

// reactive хранит фильтры каталога, которые превращаются в query params для DRF API.
// [VUE] reactive делает объект фильтров реактивным; [OUR] filters — наши параметры каталога.
const filters = reactive({
  search: '',
  ordering: 'name',
  stock: 'available',
  min_price: '',
  max_price: '',
})

const isLoading = ref(true)
const isDetailLoading = ref(false)
const isSubmitting = ref(false)
const errorMessage = ref('')
const orderResult = ref(null)
const selectedProduct = ref(null)
const cartPanel = ref(null)
const ordersPanel = ref(null)
const isBackTopVisible = ref(false)

// [OUR] Список заказов текущего Telegram-пользователя.
const customerOrders = ref([])

// [OUR] Отдельный флаг загрузки для блока "Мои заказы".
const isOrdersLoading = ref(false)

// [OUR] Отдельная ошибка для заказов, чтобы не смешивать ее с ошибками каталога.
const ordersErrorMessage = ref('')

// computed пересчитывает сумму корзины каждый раз, когда меняются товары или количество.
// [VUE] computed создает вычисляемое значение; [OUR] cartTotal — сумма корзины.
const cartTotal = computed(() => {
  return cartItems.value.reduce((total, item) => {
    return total + Number(item.product.sale_price) * item.quantity
  }, 0)
})

// [VUE] computed считает общее количество штук в корзине для мобильной кнопки.
const cartItemsCount = computed(() => {
  return cartItems.value.reduce((total, item) => total + item.quantity, 0)
})

// computed нужен для удобной проверки: можно ли отправлять заказ.
// [VUE] computed пересчитывает доступность кнопки; [OUR] canSubmitOrder — наше условие отправки.
const canSubmitOrder = computed(() => {
  return cartItems.value.length > 0 && !isSubmitting.value
})

// [VUE] onMounted запускается, когда компонент уже вставлен на страницу.
onMounted(() => {
  initializeTelegramWebApp()
  fillTelegramCustomerFields()
  loadProducts()
  loadCustomerOrders()
  updateBackTopVisibility()
  window.addEventListener('scroll', updateBackTopVisibility)
})

// [VUE] onBeforeUnmount вызывается перед удалением компонента со страницы.
onBeforeUnmount(() => {
  window.removeEventListener('scroll', updateBackTopVisibility)
})

function getTelegramWebApp() {
  if (typeof window === 'undefined') {
    return null
  }

  // [TG] window.Telegram.WebApp существует только внутри Telegram Mini App.
  return window.Telegram?.WebApp || null
}

// [OUR] Инициализируем Telegram Mini App, если страница открыта внутри Telegram.
function initializeTelegramWebApp() {
  const webApp = getTelegramWebApp()

  if (!webApp) {
    return
  }

  webApp.ready()
  webApp.expand()
}

// [OUR] Возвращает подписанную Telegram initData, которую backend проверит через bot token.
function getTelegramInitData() {
  // [TG] initData — строка user=...&auth_date=...&hash=...
  return getTelegramWebApp()?.initData || ''
}

// [OUR] Берем небезопасные данные пользователя только для автозаполнения формы.
function getTelegramUser() {
  // [TG] initDataUnsafe удобно читать на frontend, но backend ему не доверяет без initData.
  return getTelegramWebApp()?.initDataUnsafe?.user || null
}

// [OUR] Автозаполняет поля формы данными Telegram-пользователя.
function fillTelegramCustomerFields() {
  const telegramUser = getTelegramUser()

  if (!telegramUser) {
    return
  }

  const fullName = [telegramUser.first_name, telegramUser.last_name].filter(Boolean).join(' ')

  if (fullName && !customerForm.customer_name) {
    customerForm.customer_name = fullName
  }

  if (telegramUser.username && !customerForm.telegram_username) {
    customerForm.telegram_username = `@${telegramUser.username}`
  }
}

// [OUR] Загружает каталог товаров из Django API.
async function loadProducts() {
  isLoading.value = true
  errorMessage.value = ''

  try {
    // [PY/WEB] fetch делает HTTP GET-запрос из браузера к API.
    const response = await fetch(`${API_BASE_URL}/products/?${buildProductQuery()}`)

    if (!response.ok) {
      throw new Error('Не удалось загрузить каталог')
    }

    const data = await response.json()
    products.value = data.results
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    isLoading.value = false
  }
}

// [OUR] Загружает заказы текущего Telegram-пользователя.
async function loadCustomerOrders() {
  const telegramInitData = getTelegramInitData()

  // В обычном браузере initData нет, поэтому "Мои заказы" полноценно работают внутри Telegram Mini App.
  if (!telegramInitData) {
    return
  }

  isOrdersLoading.value = true
  ordersErrorMessage.value = ''

  try {
    // [WEB] GET-запрос к backend: просим вернуть только заказы текущего Telegram-пользователя.
    const response = await fetch(
      `${API_BASE_URL}/orders/my/?telegram_init_data=${encodeURIComponent(telegramInitData)}`,
    )

    const data = await response.json()

    if (!response.ok) {
      throw new Error(formatApiError(data))
    }

    // DRF pagination возвращает список внутри results.
    customerOrders.value = data.results
  } catch (error) {
    ordersErrorMessage.value = error.message
  } finally {
    isOrdersLoading.value = false
  }
}

// [OUR] Собирает query-string для фильтров каталога.
function buildProductQuery() {
  // [WEB] URLSearchParams помогает собрать параметры после знака ?.
  const params = new URLSearchParams()

  if (filters.stock !== 'all') {
    params.set('stock', filters.stock)
  }

  if (filters.search.trim()) {
    params.set('search', filters.search.trim())
  }

  if (filters.ordering) {
    params.set('ordering', filters.ordering)
  }

  if (filters.min_price) {
    params.set('min_price', filters.min_price)
  }

  if (filters.max_price) {
    params.set('max_price', filters.max_price)
  }

  return params.toString()
}

// [OUR] Сбрасывает фильтры каталога к значениям по умолчанию.
function resetFilters() {
  filters.search = ''
  filters.ordering = 'name'
  filters.stock = 'available'
  filters.min_price = ''
  filters.max_price = ''
  loadProducts()
}

// [OUR] Загружает detail-данные одного товара.
async function openProductDetail(productId) {
  isDetailLoading.value = true
  errorMessage.value = ''

  try {
    const response = await fetch(`${API_BASE_URL}/products/${productId}/`)

    if (!response.ok) {
      throw new Error('Не удалось загрузить карточку товара')
    }

    selectedProduct.value = await response.json()
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    isDetailLoading.value = false
  }
}

// [OUR] Закрывает карточку товара.
function closeProductDetail() {
  selectedProduct.value = null
}

// [OUR] Добавляет товар в локальную корзину.
function addToCart(product) {
  orderResult.value = null

  const existingItem = cartItems.value.find((item) => item.product.id === product.id)

  if (existingItem) {
    existingItem.quantity += 1
    return
  }

  cartItems.value.push({
    product,
    quantity: 1,
  })
}

// [OUR] Увеличивает количество товара в локальной корзине.
function increaseQuantity(item) {
  item.quantity += 1
}

// [OUR] Уменьшает количество товара или удаляет его из корзины.
function decreaseQuantity(item) {
  if (item.quantity === 1) {
    removeFromCart(item.product.id)
    return
  }

  item.quantity -= 1
}

// [OUR] Удаляет товар из локальной корзины.
function removeFromCart(productId) {
  cartItems.value = cartItems.value.filter((item) => item.product.id !== productId)
}

// [OUR] Скроллит пользователя к корзине, чтобы не листать весь каталог вручную.
function scrollToCart() {
  cartPanel.value?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}

// [OUR] Скроллит пользователя к истории заказов, чтобы не искать ее внизу правой панели.
function scrollToOrders() {
  ordersPanel.value?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}

// [OUR] Показываем кнопку возврата наверх только после прокрутки страницы.
function updateBackTopVisibility() {
  isBackTopVisible.value = window.scrollY > 600
}

// [OUR] Возвращает пользователя в начало каталога одной кнопкой.
function scrollToTop() {
  window.scrollTo({
    top: 0,
    behavior: 'smooth',
  })
}

// [OUR] Форматирует число как цену в рублях для интерфейса.
function formatMoney(value) {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(Number(value))
}

// [OUR] Превращает введенные цифры телефона в формат +7 (999) 000-55-55.
function formatPhoneNumber(value) {
  let digits = value.replace(/\D/g, '')

  if (digits.startsWith('8')) {
    digits = `7${digits.slice(1)}`
  }

  if (!digits.startsWith('7')) {
    digits = `7${digits}`
  }

  digits = digits.slice(0, 11)

  const country = digits.slice(0, 1)
  const operator = digits.slice(1, 4)
  const firstPart = digits.slice(4, 7)
  const secondPart = digits.slice(7, 9)
  const thirdPart = digits.slice(9, 11)

  let formattedPhone = `+${country}`

  if (operator) {
    formattedPhone += ` (${operator}`
  }

  if (operator.length === 3) {
    formattedPhone += ')'
  }

  if (firstPart) {
    formattedPhone += ` ${firstPart}`
  }

  if (secondPart) {
    formattedPhone += `-${secondPart}`
  }

  if (thirdPart) {
    formattedPhone += `-${thirdPart}`
  }

  return formattedPhone
}

// [OUR] Обрабатывает ввод телефона и сохраняет в форму уже отформатированное значение.
function updatePhone(event) {
  customerForm.phone = formatPhoneNumber(event.target.value)
}

// [OUR] Собирает JSON, который уйдет в POST /api/orders/.
function buildOrderPayload() {
  const payload = {
    ...customerForm,
    items: cartItems.value.map((item) => ({
      product: item.product.id,
      quantity: item.quantity,
    })),
  }

  const telegramInitData = getTelegramInitData()

  if (telegramInitData) {
    // [TG] Это поле backend проверит в OrderCreateSerializer через parse_telegram_init_data().
    payload.telegram_init_data = telegramInitData
  }

  return payload
}

// [OUR] Отправляет заказ в Django API.
async function submitOrder() {
  if (!canSubmitOrder.value) {
    return
  }

  errorMessage.value = ''
  orderResult.value = null
  isSubmitting.value = true

  try {
    // [WEB] fetch с method POST отправляет JSON заказа в backend.
    const response = await fetch(`${API_BASE_URL}/orders/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(buildOrderPayload()),
    })

    const data = await response.json()

    if (!response.ok) {
      throw new Error(formatApiError(data))
    }

    orderResult.value = data
    cartItems.value = []
    customerForm.customer_comment = ''
    loadCustomerOrders()
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    isSubmitting.value = false
  }
}

// [OUR] Превращает разные форматы DRF-ошибок в одну строку для интерфейса.
function formatApiError(data) {
  if (typeof data === 'string') {
    return data
  }

  if (Array.isArray(data)) {
    return data.map(formatApiError).join(' ')
  }

  if (data && typeof data === 'object') {
    return Object.values(data).map(formatApiError).join(' ')
  }

  return 'Не удалось оформить заказ'
}
</script>

<template>
  <main class="app-shell">
    <section class="catalog-panel">
      <header class="catalog-header">
        <div>
          <p class="eyebrow">Japanese Sword</p>
          <h1>Каталог</h1>
        </div>

        <div class="catalog-header-side">
          <p class="catalog-note">Товары в наличии, заказ оформляется через Telegram.</p>
          <div class="catalog-header-actions">
            <button type="button" class="secondary-button" @click="scrollToOrders">
              Мои заказы
            </button>
            <button
              v-if="cartItems.length > 0"
              type="button"
              class="primary-button"
              @click="scrollToCart"
            >
              Корзина
            </button>
          </div>
        </div>
      </header>

      <form class="filters-panel" @submit.prevent="loadProducts">
        <label>
          Поиск
          <input v-model="filters.search" type="search" placeholder="Катана, набор, артикул">
        </label>

        <label>
          Сортировка
          <select v-model="filters.ordering">
            <option value="name">По названию</option>
            <option value="sale_price">Сначала дешевле</option>
            <option value="-sale_price">Сначала дороже</option>
          </select>
        </label>

        <label>
          Наличие
          <select v-model="filters.stock">
            <option value="all">Все активные</option>
            <option value="available">В наличии</option>
            <option value="out">Нет в наличии</option>
          </select>
        </label>

        <label>
          Цена от
          <input v-model="filters.min_price" type="number" min="0" step="1">
        </label>

        <label>
          Цена до
          <input v-model="filters.max_price" type="number" min="0" step="1">
        </label>

        <div class="filter-actions">
          <button type="submit" class="primary-button">Применить</button>
          <button type="button" class="secondary-button" @click="resetFilters">Сбросить</button>
        </div>
      </form>

      <p v-if="isLoading" class="state-message">Загружаем товары...</p>
      <p v-else-if="errorMessage && products.length === 0" class="state-message error">
        {{ errorMessage }}
      </p>

      <section v-else class="product-grid" aria-label="Каталог товаров">
        <article v-for="product in products" :key="product.id" class="product-card">
          <img
            v-if="product.image"
            :src="product.image"
            :alt="product.name"
            class="product-image"
          >
          <div v-else class="product-placeholder">
            <span>Арт. {{ product.sku }}</span>
          </div>

          <div class="product-body">
            <p class="sku">Арт. {{ product.sku }}</p>
            <h2>{{ product.name }}</h2>
            <p class="stock" :class="{ 'stock-out': product.stock_status === 'Нет в наличии' }">{{ product.stock_status }}</p>
          </div>

          <div class="product-footer">
            <p class="price">{{ formatMoney(product.sale_price) }}</p>
            <div class="product-actions">
              <button type="button" class="secondary-button" @click="openProductDetail(product.id)">
                Подробнее
              </button>
              <button
                type="button"
                class="primary-button"
                :disabled="product.stock_status === 'Нет в наличии'"
                @click="addToCart(product)"
              >
                {{ product.stock_status === 'Нет в наличии' ? 'Нет в наличии' : 'В корзину' }}
              </button>
            </div>
          </div>
        </article>
      </section>
    </section>

    <aside ref="cartPanel" class="cart-panel" aria-label="Корзина">
      <header class="cart-header">
        <div>
          <p class="eyebrow">Заказ</p>
          <h2>Корзина</h2>
        </div>
        <span class="cart-counter">{{ cartItems.length }}</span>
      </header>

      <p v-if="cartItems.length === 0" class="empty-cart">
        Добавьте товары из каталога.
      </p>

      <ul v-else class="cart-list">
        <li v-for="item in cartItems" :key="item.product.id" class="cart-item">
          <div>
            <p class="cart-title">{{ item.product.name }}</p>
            <p class="cart-meta">
              Арт. {{ item.product.sku }} · {{ formatMoney(item.product.sale_price) }}
            </p>
          </div>

          <div class="quantity-control">
            <button type="button" @click="decreaseQuantity(item)">-</button>
            <span>{{ item.quantity }}</span>
            <button type="button" @click="increaseQuantity(item)">+</button>
          </div>

          <button type="button" class="ghost-button" @click="removeFromCart(item.product.id)">
            Убрать
          </button>
        </li>
      </ul>

      <div class="cart-total">
        <span>Итого</span>
        <strong>{{ formatMoney(cartTotal) }}</strong>
      </div>

      <form class="order-form" @submit.prevent="submitOrder">
        <label>
          Имя
          <input v-model="customerForm.customer_name" type="text" autocomplete="name">
        </label>

        <label>
          Telegram
          <input v-model="customerForm.telegram_username" type="text" placeholder="@username">
        </label>

        <label>
          Телефон
          <input
            :value="customerForm.phone"
            type="tel"
            autocomplete="tel"
            inputmode="tel"
            placeholder="+7 (999) 000-55-55"
            @input="updatePhone"
          >
        </label>

        <label>
          Комментарий
          <textarea v-model="customerForm.customer_comment" rows="3" />
        </label>

        <p v-if="errorMessage && products.length > 0" class="form-error">{{ errorMessage }}</p>

        <button type="submit" class="submit-button" :disabled="!canSubmitOrder">
          {{ isSubmitting ? 'Оформляем...' : 'Оформить заказ' }}
        </button>
      </form>

      <section v-if="orderResult" class="order-result">
        <p class="success-title">Заказ #{{ orderResult.id }} создан</p>
        <p>Сумма: {{ formatMoney(orderResult.total_amount) }}</p>
      </section>

      <section ref="ordersPanel" class="customer-orders">
        <header class="orders-header">
          <div>
            <p class="eyebrow">История</p>
            <h2>Мои заказы</h2>
          </div>

          <button type="button" class="ghost-button" @click="loadCustomerOrders">
            Обновить
          </button>
        </header>

        <p v-if="isOrdersLoading" class="state-message">Загружаем заказы...</p>
        <p v-else-if="ordersErrorMessage" class="form-error">{{ ordersErrorMessage }}</p>
        <p v-else-if="customerOrders.length === 0" class="empty-cart">
          Заказы появятся здесь после оформления через Telegram.
        </p>

        <ul v-else class="orders-list">
          <li v-for="order in customerOrders" :key="order.id" class="order-card">
            <div class="order-card-header">
              <strong>Заказ #{{ order.id }}</strong>
              <span>{{ order.status_display }}</span>
            </div>

            <p class="cart-meta">Сумма: {{ formatMoney(order.total_amount) }}</p>

            <p v-if="order.tracking_number" class="cart-meta">
              Трек: {{ order.tracking_number }}
            </p>

            <ul class="order-items-list">
              <li v-for="item in order.items" :key="`${order.id}-${item.product}`">
                Арт. {{ item.sku }} — {{ item.name }} x {{ item.quantity }}
              </li>
            </ul>
          </li>
        </ul>
      </section>
    </aside>

    <section v-if="selectedProduct || isDetailLoading" class="detail-backdrop" @click.self="closeProductDetail">
      <article class="detail-card">
        <p v-if="isDetailLoading" class="state-message">Загружаем карточку...</p>

        <template v-else>
          <button type="button" class="detail-close" @click="closeProductDetail">Закрыть</button>

          <div v-if="selectedProduct.images?.length" class="detail-gallery">
            <img
              v-for="image in selectedProduct.images"
              :key="image.id"
              :src="image.image"
              :alt="selectedProduct.name"
              class="detail-image"
            >
          </div>

          <img
            v-else-if="selectedProduct.image"
            :src="selectedProduct.image"
            :alt="selectedProduct.name"
            class="detail-image"
          >

          <p class="sku">Арт. {{ selectedProduct.sku }}</p>
          <h2>{{ selectedProduct.name }}</h2>
          <p class="price">{{ formatMoney(selectedProduct.sale_price) }}</p>
          <p class="stock" :class="{ 'stock-out': selectedProduct.stock_status === 'Нет в наличии' }">{{ selectedProduct.stock_status }}</p>
          <p class="detail-description">
            {{ selectedProduct.description || 'Описание пока не заполнено.' }}
          </p>

          <button
            type="button"
            class="submit-button"
            :disabled="selectedProduct.stock_status === 'Нет в наличии'"
            @click="addToCart(selectedProduct)"
          >
            {{ selectedProduct.stock_status === 'Нет в наличии' ? 'Нет в наличии' : 'Добавить в корзину' }}
          </button>
        </template>
      </article>
    </section>

    <button
      v-if="isBackTopVisible"
      type="button"
      class="back-top-button"
      aria-label="Вернуться в начало каталога"
      @click="scrollToTop"
    >
      Наверх
    </button>

    <button
      v-if="cartItems.length > 0"
      type="button"
      class="floating-cart-button"
      aria-label="Перейти к корзине"
      @click="scrollToCart"
    >
      <span>Корзина</span>
      <strong>{{ cartItemsCount }} · {{ formatMoney(cartTotal) }}</strong>
    </button>
  </main>
</template>

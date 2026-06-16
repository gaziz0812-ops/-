<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

// VITE_API_BASE_URL позволяет указать отдельный API; по умолчанию идем через Vite proxy на /api.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

// ref хранит список товаров из Django API и обновляет экран при изменении.
const products = ref([])

// ref хранит локальную корзину: backend узнает о ней только при оформлении заказа.
const cartItems = ref([])

// reactive хранит поля формы заказа как один связанный объект.
const customerForm = reactive({
  customer_name: '',
  telegram_username: '',
  phone: '',
  customer_comment: '',
})

// reactive хранит фильтры каталога, которые превращаются в query params для DRF API.
const filters = reactive({
  search: '',
  ordering: 'name',
  min_price: '',
  max_price: '',
})

const isLoading = ref(true)
const isDetailLoading = ref(false)
const isSubmitting = ref(false)
const errorMessage = ref('')
const orderResult = ref(null)
const selectedProduct = ref(null)

// computed пересчитывает сумму корзины каждый раз, когда меняются товары или количество.
const cartTotal = computed(() => {
  return cartItems.value.reduce((total, item) => {
    return total + Number(item.product.sale_price) * item.quantity
  }, 0)
})

// computed нужен для удобной проверки: можно ли отправлять заказ.
const canSubmitOrder = computed(() => {
  return cartItems.value.length > 0 && !isSubmitting.value
})

onMounted(() => {
  initializeTelegramWebApp()
  fillTelegramCustomerFields()
  loadProducts()
})

function getTelegramWebApp() {
  if (typeof window === 'undefined') {
    return null
  }

  return window.Telegram?.WebApp || null
}

function initializeTelegramWebApp() {
  const webApp = getTelegramWebApp()

  if (!webApp) {
    return
  }

  webApp.ready()
  webApp.expand()
}

function getTelegramInitData() {
  return getTelegramWebApp()?.initData || ''
}

function getTelegramUser() {
  return getTelegramWebApp()?.initDataUnsafe?.user || null
}

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

async function loadProducts() {
  isLoading.value = true
  errorMessage.value = ''

  try {
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

function buildProductQuery() {
  const params = new URLSearchParams()

  params.set('stock', 'available')

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

function resetFilters() {
  filters.search = ''
  filters.ordering = 'name'
  filters.min_price = ''
  filters.max_price = ''
  loadProducts()
}

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

function closeProductDetail() {
  selectedProduct.value = null
}

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

function increaseQuantity(item) {
  item.quantity += 1
}

function decreaseQuantity(item) {
  if (item.quantity === 1) {
    removeFromCart(item.product.id)
    return
  }

  item.quantity -= 1
}

function removeFromCart(productId) {
  cartItems.value = cartItems.value.filter((item) => item.product.id !== productId)
}

function formatMoney(value) {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(Number(value))
}

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
    payload.telegram_init_data = telegramInitData
  }

  return payload
}

async function submitOrder() {
  if (!canSubmitOrder.value) {
    return
  }

  errorMessage.value = ''
  orderResult.value = null
  isSubmitting.value = true

  try {
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
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    isSubmitting.value = false
  }
}

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
        <p class="catalog-note">Товары в наличии, заказ оформляется через Telegram.</p>
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
            <p class="stock">{{ product.stock_status }}</p>
          </div>

          <div class="product-footer">
            <p class="price">{{ formatMoney(product.sale_price) }}</p>
            <div class="product-actions">
              <button type="button" class="secondary-button" @click="openProductDetail(product.id)">
                Подробнее
              </button>
              <button type="button" class="primary-button" @click="addToCart(product)">
                В корзину
              </button>
            </div>
          </div>
        </article>
      </section>
    </section>

    <aside class="cart-panel" aria-label="Корзина">
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
          <input v-model="customerForm.phone" type="tel" autocomplete="tel">
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
    </aside>

    <section v-if="selectedProduct || isDetailLoading" class="detail-backdrop" @click.self="closeProductDetail">
      <article class="detail-card">
        <p v-if="isDetailLoading" class="state-message">Загружаем карточку...</p>

        <template v-else>
          <button type="button" class="detail-close" @click="closeProductDetail">Закрыть</button>

          <img
            v-if="selectedProduct.image"
            :src="selectedProduct.image"
            :alt="selectedProduct.name"
            class="detail-image"
          >

          <p class="sku">Арт. {{ selectedProduct.sku }}</p>
          <h2>{{ selectedProduct.name }}</h2>
          <p class="price">{{ formatMoney(selectedProduct.sale_price) }}</p>
          <p class="stock">{{ selectedProduct.stock_status }}</p>
          <p class="detail-description">
            {{ selectedProduct.description || 'Описание пока не заполнено.' }}
          </p>

          <button type="button" class="submit-button" @click="addToCart(selectedProduct)">
            Добавить в корзину
          </button>
        </template>
      </article>
    </section>
  </main>
</template>

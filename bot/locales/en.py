"""Английский перевод интерфейса (BOT_LANG=en). Ключ — русский текст из кода."""

EN = {
    # Меню и кнопки
    "🛍 Каталог": "🛍 Catalog",
    "🛒 Корзина": "🛒 Cart",
    "📦 Мои заказы": "📦 My orders",
    "✖️ Отмена": "✖️ Cancel",
    "⏭ Пропустить": "⏭ Skip",
    "📱 Отправить мой номер": "📱 Share my phone number",
    "🚶 Самовывоз": "🚶 Pickup",
    "🚚 Доставка": "🚚 Delivery",
    "⬅️ Категории": "⬅️ Categories",
    "⬅️ Каталог": "⬅️ Catalog",
    "🛒 В корзину": "🛒 Add to cart",
    "{n} шт": "{n} pcs",
    "🗑 Очистить": "🗑 Clear",
    "✅ Оформить": "✅ Checkout",
    "🗑 {name} (недоступен)": "🗑 {name} (unavailable)",
    "✅ Подтвердить заказ": "✅ Confirm order",
    "❌ Отменить заказ #{id}": "❌ Cancel order #{id}",
    "Да, отменить": "Yes, cancel",
    "Нет": "No",
    "Каталог": "Catalog",
    "Корзина": "Cart",
    "Мои заказы": "My orders",
    "Админ-панель": "Admin panel",
    "Добавить товар": "Add a product",
    "Товары": "Products",
    "Заказы": "Orders",
    "Статистика": "Statistics",
    "Магазин": "Shop",

    # Статусы
    "🆕 Новый": "🆕 New",
    "👍 Подтверждён": "👍 Confirmed",
    "📦 Отправлен": "📦 Shipped",
    "✅ Выполнен": "✅ Completed",
    "❌ Отменён": "❌ Cancelled",
    "Новый": "New",
    "Подтверждён": "Confirmed",
    "Отправлен": "Shipped",
    "Выполнен": "Completed",
    "Отменён": "Cancelled",
    "подтверждён": "has been confirmed",
    "передан в доставку": "is on its way",
    "готов к выдаче": "is ready for pickup",
    "выполнен. Спасибо за покупку!": "is completed. Thank you for your purchase!",
    "отменён": "has been cancelled",
    "Ваш заказ #{id} {status}": "Your order #{id} {status}",

    # Карточки товаров и заказов
    "❗ Нет в наличии": "❗ Out of stock",
    "🗑 удалён": "🗑 deleted",
    "🙈 скрыт": "🙈 hidden",
    "✅ в наличии": "✅ in stock",
    "❌ нет в наличии": "❌ out of stock",
    "Товары: {sum}": "Items: {sum}",
    "Доставка: {sum}": "Delivery: {sum}",
    "бесплатно": "free",
    "<b>Итого: {sum}</b>": "<b>Total: {sum}</b>",
    "🚚 Доставка: {address}": "🚚 Delivery: {address}",
    "<b>Заказ #{id}</b>": "<b>Order #{id}</b>",

    # Клиент: каталог и корзина
    "\n\n🧪 <b>Это демо-магазин</b> — оплачивать ничего не нужно. После заказа вы получите копию карточки, "
    "которую видит владелец, и сможете сами менять статус заказа.":
        "\n\n🧪 <b>This is a demo shop</b> — you don't need to pay anything. After ordering you'll get a copy "
        "of the card the owner sees, and you can change the order status yourself.",
    "🧪 Это демо-заказ — оплачивать ничего не нужно.": "🧪 This is a demo order — no payment needed.",
    "Добро пожаловать в <b>{shop}</b>!\n\n{catalog} — товары\n{cart} — ваша корзина\n{orders} — статусы заказов":
        "Welcome to <b>{shop}</b>!\n\n{catalog} — products\n{cart} — your cart\n{orders} — order status",
    "Каталог пока пуст.": "The catalog is empty for now.",
    "Выберите категорию:": "Choose a category:",
    "Товар больше недоступен": "This product is no longer available",
    "Нет в наличии": "Out of stock",
    "В корзине: {n} шт": "In cart: {n} pcs",
    "Убрано из корзины": "Removed from cart",
    "Товар недоступен": "Product unavailable",
    "🛒 Корзина пуста.": "🛒 Your cart is empty.",
    "• <s>{name}</s> — недоступен": "• <s>{name}</s> — unavailable",
    "<b>Корзина</b>": "<b>Cart</b>",
    "<b>Сумма: {sum}</b>": "<b>Subtotal: {sum}</b>",
    "Бесплатная доставка от {sum}": "Free delivery from {sum}",
    "❗ Минимальная сумма заказа — {sum}": "❗ Minimum order amount — {sum}",
    "❗ Уберите недоступные товары, чтобы оформить заказ.": "❗ Remove unavailable items to check out.",
    "У вас пока нет заказов.": "You have no orders yet.",
    "<b>Ваши заказы</b>": "<b>Your orders</b>",
    "Корзина пуста.": "Your cart is empty.",
    "В корзине есть недоступные товары — уберите их.": "Your cart has unavailable items — please remove them.",
    "Минимальная сумма заказа — {sum}.": "Minimum order amount — {sum}.",
    "Слишком много заказов за последний час. Попробуйте позже.": "Too many orders in the last hour. Please try again later.",

    # Клиент: оформление
    "<b>Оформление заказа</b>\n\nКак к вам обращаться?": "<b>Checkout</b>\n\nWhat's your name?",
    "Оформление отменено. Товары остались в корзине.": "Checkout cancelled. Your items are still in the cart.",
    "Имя должно быть от 2 до 50 символов.": "The name must be 2 to 50 characters long.",
    "Номер телефона — кнопкой ниже или текстом:": "Phone number — use the button below or type it:",
    "Не похоже на номер телефона. Пример: +7 701 123 45 67": "That doesn't look like a phone number. Example: +1 555 123 4567",
    "Как получить заказ?": "How would you like to receive your order?",
    "Выберите способ получения кнопкой ниже.": "Please choose a delivery option with the buttons below.",
    "Адрес доставки (город, улица, дом, квартира):": "Delivery address (city, street, building, apartment):",
    "Адрес должен быть от 5 до 300 символов.": "The address must be 5 to 300 characters long.",
    "Комментарий к заказу (необязательно):": "Order comment (optional):",
    "Комментарий — не длиннее 500 символов.": "The comment must be at most 500 characters.",
    "Проверьте заказ 👇": "Please check your order 👇",
    "<b>Ваш заказ</b>": "<b>Your order</b>",
    "Нажмите «✅ Подтвердить заказ» под сводкой.": "Press “✅ Confirm order” under the summary.",
    "Ответьте текстом или нажмите «✖️ Отмена».": "Please reply with text or press “✖️ Cancel”.",
    "Заказ не оформлен: {problem}": "Order not placed: {problem}",
    "❗ <b>Сумма изменилась</b> — проверьте заказ ещё раз.": "❗ <b>The total has changed</b> — please check your order again.",
    "Сумма изменилась": "The total has changed",
    "✅ <b>Заказ #{id} оформлен!</b>": "✅ <b>Order #{id} placed!</b>",
    "Мы свяжемся с вами для подтверждения.": "We'll contact you to confirm it.",
    "👀 <b>Так заказ увидит владелец</b> — кнопки статуса работают:":
        "👀 <b>This is what the owner sees</b> — the status buttons work:",
    "Заказ уже нельзя отменить — напишите нам": "This order can no longer be cancelled — please contact us",
    "Отменить заказ #{id}?": "Cancel order #{id}?",
    "Заказ #{id} отменён.": "Order #{id} has been cancelled.",
    "❌ Клиент отменил заказ #{id}": "❌ The client cancelled order #{id}",
    "Кнопка устарела. Откройте /catalog": "This button is outdated. Open /catalog",

    # Админ: каталог
    "<b>Админ-панель</b>\n\n"
    "<b>Каталог</b>\n"
    "/add — добавить товар\n"
    "/products — все товары\n"
    "/p ID — управление товаром (цена, наличие, скрыть, удалить)\n\n"
    "<b>Заказы</b>\n"
    "/orders — последние 10\n"
    "/orders new|confirmed|shipped|done|cancelled — по статусу\n"
    "/order ID — карточка заказа\n"
    "/export — все заказы в CSV (Excel)\n"
    "/stats — продажи и топ товаров":
        "<b>Admin panel</b>\n\n"
        "<b>Catalog</b>\n"
        "/add — add a product\n"
        "/products — all products\n"
        "/p ID — manage a product (price, stock, hide, delete)\n\n"
        "<b>Orders</b>\n"
        "/orders — last 10\n"
        "/orders new|confirmed|shipped|done|cancelled — by status\n"
        "/order ID — order card\n"
        "/export — all orders as CSV (Excel)\n"
        "/stats — sales and top products",
    "Отменено.": "Cancelled.",
    "Сначала закончите добавление или нажмите «✖️ Отмена».": "Finish adding the product first or press “✖️ Cancel”.",
    "<b>Новый товар</b>": "<b>New product</b>",
    "➕ Новая категория": "➕ New category",
    "Название новой категории:": "New category name:",
    "Категория не найдена, выберите снова.": "Category not found, please choose again.",
    "Категория: <b>{name}</b>": "Category: <b>{name}</b>",
    "Название категории — от 1 до 40 символов.": "The category name must be 1 to 40 characters long.",
    "Название товара:": "Product name:",
    "Название — от 1 до 64 символов.": "The name must be 1 to 64 characters long.",
    "Описание товара:": "Product description:",
    "Описание — не длиннее 700 символов.": "The description must be at most 700 characters.",
    "Цена (целое число):": "Price (whole number):",
    "Введите цену целым числом больше нуля, например 4990.": "Enter the price as a whole number above zero, e.g. 49.",
    "Фото товара:": "Product photo:",
    "Пришлите фото или нажмите «⏭ Пропустить».": "Send a photo or press “⏭ Skip”.",
    "Выберите категорию кнопкой выше.": "Choose a category with the buttons above.",
    "Ответьте текстом.": "Please reply with text.",
    "✅ Товар добавлен.": "✅ Product added.",
    "Товаров нет. Добавьте: /add": "No products yet. Add one: /add",
    "🙈 скрыт · ❌ нет в наличии": "🙈 hidden · ❌ out of stock",
    "Формат: /p 12 или /p12": "Format: /p 12 or /p12",
    "Товар не найден.": "Product not found.",
    "Товар удалён": "Product deleted",
    "💰 Цена": "💰 Price",
    "❌ Нет в наличии": "❌ Out of stock",
    "✅ В наличии": "✅ In stock",
    "👁 Показать": "👁 Show",
    "🙈 Скрыть": "🙈 Hide",
    "🗑 Удалить": "🗑 Delete",
    "Да, удалить": "Yes, delete",
    "Новая цена для «{name}» (сейчас {price}):": "New price for “{name}” (now {price}):",
    "Введите цену целым числом больше нуля.": "Enter the price as a whole number above zero.",
    "Цена обновлена: {price}": "Price updated: {price}",
    "Готово": "Done",

    # Админ: заказы и статистика
    "Статусы: {list}": "Statuses: {list}",
    "Заказов нет.": "No orders.",
    "Подробнее: /order ID": "Details: /order ID",
    "Формат: /order 12 (заказ должен существовать)": "Format: /order 12 (the order must exist)",
    "Заказов: {n}": "Orders: {n}",
    "Создан": "Created",
    "Статус": "Status",
    "Клиент": "Client",
    "Телефон": "Phone",
    "Получение": "Fulfilment",
    "Адрес": "Address",
    "Комментарий": "Comment",
    "Состав": "Items",
    "Доставка": "Delivery",
    "Самовывоз": "Pickup",
    "Итого": "Total",
    "<b>Продажи</b> (без отменённых)": "<b>Sales</b> (excluding cancelled)",
    "Сегодня": "Today",
    "7 дней": "7 days",
    "30 дней": "30 days",
    "{period}: {count} зак. · {revenue}": "{period}: {count} orders · {revenue}",
    "<b>Топ товаров за 30 дней</b>": "<b>Top products, last 30 days</b>",
    "{n}. {name} — {qty} шт · {revenue}": "{n}. {name} — {qty} pcs · {revenue}",
    "Нет доступа": "Access denied",
    "Статус уже установлен": "This status is already set",
    "Заказ не найден": "Order not found",
    "Статус: {status}": "Status: {status}",
}

from aiogram.fsm.state import State, StatesGroup


class Checkout(StatesGroup):
    name = State()
    phone = State()
    delivery = State()
    address = State()
    comment = State()
    confirm = State()


class AddProduct(StatesGroup):
    category = State()
    new_category = State()
    name = State()
    description = State()
    price = State()
    photo = State()


class EditPrice(StatesGroup):
    price = State()

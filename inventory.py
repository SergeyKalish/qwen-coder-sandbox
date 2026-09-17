"""Учёт товаров на складе. В коде закладено РОВНО 3 логических бага."""


class Warehouse:
    def __init__(self):
        self.stock = {}      # sku -> qty
        self.reserved = {}   # sku -> qty

    def add(self, sku, qty):
        """Поступление товара."""
        if qty < 0:
            raise ValueError("qty must be positive")
        self.stock[sku] = self.stock.get(sku, 0) + qty

    def reserve(self, sku, qty):
        """Зарезервировать товар под заказ. Возвращает True/False."""
        if self.stock.get(sku, 0) < qty:
            return False
        self.reserved[sku] = self.reserved.get(sku, 0) + qty
        self.stock[sku] = self.stock.get(sku, 0) - qty
        return True

    def cancel_reserve(self, sku, qty):
        """Отмена резерва — товар возвращается на склад."""
        if qty == 0:
            return  # Nothing to cancel
        if self.reserved.get(sku, 0) < qty:
            raise ValueError("not reserved enough")
        self.reserved[sku] -= qty
        self.stock[sku] = self.stock.get(sku, 0) + qty

    def ship(self, sku, qty):
        """Отгрузка со склада (уменьшает доступный остаток)."""
        if qty <= 0:
            raise ValueError("qty must be positive")
        if self.stock.get(sku, 0) < qty:
            raise ValueError("not enough stock")
        self.stock[sku] -= qty

    def available(self, sku):
        """Доступный остаток = только склад (резерв уже вычтен)."""
        return self.stock.get(sku, 0)

"""Phiên bản v1 (ban đầu) - CHỨA LỖI CÀI SẴN phục vụ nghiên cứu kiểm thử.

Các lỗi được đánh dấu BUG-xx. Đây là lỗi mô phỏng (seeded defects) theo kiểu
những sai sót thường gặp của lập trình viên, dùng để đo khả năng phát hiện lỗi
của bộ test. Bản đã sửa nằm ở sales.py.
"""
from __future__ import annotations

from dataclasses import dataclass

TAX_PERCENT = 8
FREE_SHIPPING_THRESHOLD = 500_000
SHIPPING_FEE = 30_000
MAX_QTY_PER_LINE = 1000
TIER_DISCOUNTS = ((1_000_000, 10), (500_000, 5))
COUPONS = {"SALE10": 10, "VIP20": 20}


class SalesError(Exception):
    pass


class InvalidProductError(SalesError):
    pass


class InvalidQuantityError(SalesError):
    pass


class OutOfStockError(SalesError):
    pass


class InvalidDiscountError(SalesError):
    pass


class InvalidOrderError(SalesError):
    pass


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass
class Product:
    sku: str
    name: str
    price: int
    stock: int

    def __post_init__(self):
        if not isinstance(self.sku, str) or not self.sku.strip():
            raise InvalidProductError("SKU phải là chuỗi không rỗng")
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidProductError("Tên sản phẩm phải là chuỗi không rỗng")
        if not _is_int(self.price) or self.price <= 0:
            raise InvalidProductError("Giá phải là số nguyên dương")
        if not _is_int(self.stock) or self.stock < 0:
            raise InvalidProductError("Tồn kho phải là số nguyên không âm")


def validate_quantity(qty) -> int:
    # BUG-09: không kiểm tra kiểu dữ liệu -> chấp nhận float (2.5), bool (True)
    # BUG-01: dùng "qty < 0" thay vì "qty <= 0" -> chấp nhận số lượng bằng 0
    if qty < 0:
        raise InvalidQuantityError(f"Số lượng phải > 0: {qty}")
    if qty > MAX_QTY_PER_LINE:
        raise InvalidQuantityError(f"Số lượng vượt tối đa {MAX_QTY_PER_LINE}: {qty}")
    return qty


class Inventory:
    def __init__(self):
        self._products: dict[str, Product] = {}

    def add_product(self, product: Product) -> None:
        if not isinstance(product, Product):
            raise InvalidProductError("Đối tượng không phải Product")
        if product.sku in self._products:
            raise InvalidProductError(f"SKU đã tồn tại: {product.sku}")
        self._products[product.sku] = product

    def get(self, sku) -> Product:
        try:
            return self._products[sku]
        except (KeyError, TypeError):
            raise InvalidProductError(f"Không tìm thấy sản phẩm: {sku!r}") from None

    def stock_of(self, sku) -> int:
        return self.get(sku).stock

    def check_availability(self, sku, qty) -> None:
        validate_quantity(qty)
        product = self.get(sku)
        # BUG-02: dùng ">=" -> mua đúng bằng số tồn bị từ chối nhầm
        if qty >= product.stock:
            raise OutOfStockError(f"{sku}: cần {qty}, chỉ còn {product.stock}")

    def deduct(self, sku, qty) -> None:
        self.check_availability(sku, qty)
        self._products[sku].stock -= qty

    def restock(self, sku, qty) -> None:
        validate_quantity(qty)
        self.get(sku).stock += qty


def normalize_items(items) -> list[tuple[str, int]]:
    if not isinstance(items, (list, tuple)) or len(items) == 0:
        raise InvalidOrderError("Đơn hàng phải có ít nhất một dòng hàng")
    result = []
    for line in items:
        if not isinstance(line, (list, tuple)) or len(line) != 2:
            raise InvalidOrderError(f"Dòng hàng sai định dạng: {line!r}")
        sku, qty = line
        if not isinstance(sku, str):
            raise InvalidOrderError(f"SKU phải là chuỗi: {sku!r}")
        validate_quantity(qty)
        # BUG-10: không gộp các dòng trùng SKU -> kiểm tồn từng dòng riêng lẻ
        result.append((sku, qty))
    return result


def calculate_subtotal(inventory: Inventory, items) -> int:
    total = 0
    for sku, qty in normalize_items(items):
        total += inventory.get(sku).price * qty
    return total


def get_discount_percent(subtotal: int, coupon=None) -> int:
    if not _is_int(subtotal) or subtotal < 0:
        raise InvalidOrderError("Tạm tính phải là số nguyên không âm")
    tier = 0
    for threshold, percent in TIER_DISCOUNTS:
        # BUG-03: dùng ">" thay vì ">=" tại biên bậc giảm giá
        if subtotal > threshold:
            tier = percent
            break
    coupon_percent = 0
    if coupon is not None:
        if not isinstance(coupon, str):
            raise InvalidDiscountError(f"Mã giảm giá phải là chuỗi: {coupon!r}")
        # BUG-07: không strip()/upper() -> phân biệt hoa thường, vướng khoảng trắng
        code = coupon
        if code:
            if code not in COUPONS:
                raise InvalidDiscountError(f"Mã giảm giá không hợp lệ: {coupon!r}")
            coupon_percent = COUPONS[code]
    return max(tier, coupon_percent)


def apply_discount(subtotal: int, percent: int) -> int:
    if not _is_int(subtotal) or subtotal < 0:
        raise InvalidOrderError("Tạm tính phải là số nguyên không âm")
    # BUG-04: thiếu chặn trên (percent > 100) -> số tiền giảm lớn hơn tạm tính
    if not _is_int(percent) or percent < 0:
        raise InvalidDiscountError(f"% giảm giá không hợp lệ: {percent!r}")
    return subtotal * percent // 100


def calculate_shipping(amount: int) -> int:
    if not _is_int(amount) or amount < 0:
        raise InvalidOrderError("Giá trị đơn hàng phải là số nguyên không âm")
    # BUG-08: dùng ">" thay vì ">=" -> đúng 500.000 vẫn bị tính phí ship
    if amount == 0 or amount > FREE_SHIPPING_THRESHOLD:
        return 0
    return SHIPPING_FEE


def calculate_tax(amount: int) -> int:
    if not _is_int(amount) or amount < 0:
        raise InvalidOrderError("Giá trị tính thuế phải là số nguyên không âm")
    return (amount * TAX_PERCENT + 50) // 100


def process_order(inventory: Inventory, items, coupon=None) -> dict:
    lines = normalize_items(items)
    # BUG-06: vừa kiểm tra vừa trừ kho từng dòng -> lỗi ở dòng sau để lại
    # trạng thái trừ kho dở dang (không nguyên tử)
    for sku, qty in lines:
        inventory.deduct(sku, qty)

    subtotal = calculate_subtotal(inventory, lines)
    percent = get_discount_percent(subtotal, coupon)
    discount = apply_discount(subtotal, percent)
    net = subtotal - discount
    shipping = calculate_shipping(net)
    # BUG-05: tính thuế trên tạm tính (trước giảm giá) thay vì trên "net"
    tax = calculate_tax(subtotal)
    total = net + shipping + tax

    detail = []
    for sku, qty in lines:
        p = inventory.get(sku)
        detail.append({"sku": sku, "name": p.name, "qty": qty,
                       "unit_price": p.price, "line_total": p.price * qty})

    return {"lines": detail, "subtotal": subtotal, "discount_percent": percent,
            "discount": discount, "net": net, "shipping": shipping,
            "tax": tax, "total": total}

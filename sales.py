"""Logic nghiệp vụ quản lý bán hàng (phiên bản đã sửa lỗi - "fixed").

Phạm vi: quản lý sản phẩm/tồn kho, tính tổng tiền, giảm giá, phí vận chuyển,
thuế và xử lý đơn hàng không hợp lệ. Toàn bộ tiền tệ là số nguyên (VND) để
tránh sai số dấu phẩy động.
"""
from __future__ import annotations

from dataclasses import dataclass

# ----------------------------------------------------------------------------
# Hằng số nghiệp vụ
# ----------------------------------------------------------------------------
TAX_PERCENT = 8                       # VAT 8% tính trên tiền hàng sau giảm giá
FREE_SHIPPING_THRESHOLD = 500_000     # >= ngưỡng này thì miễn phí vận chuyển
SHIPPING_FEE = 30_000
MAX_QTY_PER_LINE = 1000
# (ngưỡng tạm tính, % giảm) - sắp xếp giảm dần
TIER_DISCOUNTS = ((1_000_000, 10), (500_000, 5))
COUPONS = {"SALE10": 10, "VIP20": 20}


# ----------------------------------------------------------------------------
# Ngoại lệ
# ----------------------------------------------------------------------------
class SalesError(Exception):
    """Lỗi gốc của module bán hàng."""


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
    """int thật sự (loại bool vì bool là lớp con của int)."""
    return isinstance(value, int) and not isinstance(value, bool)


# ----------------------------------------------------------------------------
# Sản phẩm & tồn kho
# ----------------------------------------------------------------------------
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
    """Số lượng hợp lệ: số nguyên, 1 <= qty <= MAX_QTY_PER_LINE."""
    if not _is_int(qty):
        raise InvalidQuantityError(f"Số lượng phải là số nguyên: {qty!r}")
    if qty <= 0:
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
        if qty > product.stock:
            raise OutOfStockError(
                f"{sku}: cần {qty}, chỉ còn {product.stock}"
            )

    def deduct(self, sku, qty) -> None:
        self.check_availability(sku, qty)
        self._products[sku].stock -= qty

    def restock(self, sku, qty) -> None:
        validate_quantity(qty)
        self.get(sku).stock += qty


# ----------------------------------------------------------------------------
# Tính toán đơn hàng
# ----------------------------------------------------------------------------
def normalize_items(items) -> list[tuple[str, int]]:
    """Kiểm tra cấu trúc đơn hàng và gộp các dòng trùng SKU."""
    if not isinstance(items, (list, tuple)) or len(items) == 0:
        raise InvalidOrderError("Đơn hàng phải có ít nhất một dòng hàng")
    merged: dict[str, int] = {}
    for line in items:
        if not isinstance(line, (list, tuple)) or len(line) != 2:
            raise InvalidOrderError(f"Dòng hàng sai định dạng: {line!r}")
        sku, qty = line
        if not isinstance(sku, str):
            raise InvalidOrderError(f"SKU phải là chuỗi: {sku!r}")
        validate_quantity(qty)
        merged[sku] = merged.get(sku, 0) + qty
    return list(merged.items())


def calculate_subtotal(inventory: Inventory, items) -> int:
    total = 0
    for sku, qty in normalize_items(items):
        total += inventory.get(sku).price * qty
    return total


def get_discount_percent(subtotal: int, coupon=None) -> int:
    """% giảm giá = max(giảm theo bậc, giảm theo coupon); không cộng dồn."""
    if not _is_int(subtotal) or subtotal < 0:
        raise InvalidOrderError("Tạm tính phải là số nguyên không âm")
    tier = 0
    for threshold, percent in TIER_DISCOUNTS:
        if subtotal >= threshold:
            tier = percent
            break
    coupon_percent = 0
    if coupon is not None:
        if not isinstance(coupon, str):
            raise InvalidDiscountError(f"Mã giảm giá phải là chuỗi: {coupon!r}")
        code = coupon.strip().upper()
        if code:  # chuỗi rỗng/khoảng trắng = không dùng coupon
            if code not in COUPONS:
                raise InvalidDiscountError(f"Mã giảm giá không hợp lệ: {coupon!r}")
            coupon_percent = COUPONS[code]
    return max(tier, coupon_percent)


def apply_discount(subtotal: int, percent: int) -> int:
    """Trả về SỐ TIỀN được giảm (làm tròn xuống)."""
    if not _is_int(subtotal) or subtotal < 0:
        raise InvalidOrderError("Tạm tính phải là số nguyên không âm")
    if not _is_int(percent) or percent < 0 or percent > 100:
        raise InvalidDiscountError(f"% giảm giá phải trong [0, 100]: {percent!r}")
    return subtotal * percent // 100


def calculate_shipping(amount: int) -> int:
    if not _is_int(amount) or amount < 0:
        raise InvalidOrderError("Giá trị đơn hàng phải là số nguyên không âm")
    if amount == 0 or amount >= FREE_SHIPPING_THRESHOLD:
        return 0
    return SHIPPING_FEE


def calculate_tax(amount: int) -> int:
    """Thuế = amount * TAX_PERCENT%, làm tròn half-up đến 1 VND."""
    if not _is_int(amount) or amount < 0:
        raise InvalidOrderError("Giá trị tính thuế phải là số nguyên không âm")
    return (amount * TAX_PERCENT + 50) // 100


def process_order(inventory: Inventory, items, coupon=None) -> dict:
    """Xử lý đơn hàng một cách nguyên tử: lỗi thì không trừ kho."""
    lines = normalize_items(items)
    for sku, qty in lines:                       # 1) kiểm tra toàn bộ trước
        inventory.check_availability(sku, qty)

    subtotal = calculate_subtotal(inventory, lines)
    percent = get_discount_percent(subtotal, coupon)
    discount = apply_discount(subtotal, percent)
    net = subtotal - discount
    shipping = calculate_shipping(net)
    tax = calculate_tax(net)
    total = net + shipping + tax

    detail = []
    for sku, qty in lines:
        p = inventory.get(sku)
        detail.append({"sku": sku, "name": p.name, "qty": qty,
                       "unit_price": p.price, "line_total": p.price * qty})

    for sku, qty in lines:                       # 2) chỉ trừ kho khi mọi thứ hợp lệ
        inventory.deduct(sku, qty)

    return {"lines": detail, "subtotal": subtotal, "discount_percent": percent,
            "discount": discount, "net": net, "shipping": shipping,
            "tax": tax, "total": total}

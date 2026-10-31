"""Bộ kiểm thử đơn vị cho module quản lý bán hàng.

Chạy trên bản đã sửa:   pytest
Chạy trên bản có lỗi:   SALES_MODULE=sales_v1 pytest

Quy ước tên lớp test -> kỹ thuật kiểm thử:
  TestProduct*, TestInventory*  : Equivalence Partitioning / Unit
  TestQuantity*, TestAvailability*, TestDiscount*, TestShipping*, TestTax* : Boundary Value Analysis
  TestNegative*                 : Negative Testing
  TestProcessOrder*             : Unit/Integration (nghiệp vụ end-to-end)
  TestRegression*               : Regression (mỗi lỗi đã phát hiện có 1 test khóa)
"""
import importlib
import os

import pytest

S = importlib.import_module(os.environ.get("SALES_MODULE", "sales"))


# ----------------------------------------------------------------------------
# Fixture
# ----------------------------------------------------------------------------
@pytest.fixture
def inv():
    i = S.Inventory()
    i.add_product(S.Product("A001", "Bút bi", 10_000, 100))
    i.add_product(S.Product("B002", "Vở", 25_000, 50))
    i.add_product(S.Product("C003", "Balo", 300_000, 5))
    i.add_product(S.Product("D004", "Tai nghe", 1_200_000, 2))
    i.add_product(S.Product("E005", "Ghim", 5_000, 0))
    return i


def snapshot(i):
    return {s: i.stock_of(s) for s in ("A001", "B002", "C003", "D004", "E005")}


# ----------------------------------------------------------------------------
# 1. Sản phẩm - Equivalence Partitioning
# ----------------------------------------------------------------------------
class TestProduct:
    def test_valid_product(self):
        p = S.Product("X1", "Tên", 1000, 0)
        assert (p.sku, p.name, p.price, p.stock) == ("X1", "Tên", 1000, 0)

    @pytest.mark.parametrize("sku,name,price,stock", [
        ("", "n", 1, 1),          # sku rỗng
        ("   ", "n", 1, 1),       # sku toàn khoảng trắng
        (None, "n", 1, 1),        # sku None
        ("s", "", 1, 1),          # tên rỗng
        ("s", None, 1, 1),        # tên None
        ("s", "n", 0, 1),         # giá = 0 (biên)
        ("s", "n", -5, 1),        # giá âm
        ("s", "n", 10.5, 1),      # giá không nguyên
        ("s", "n", True, 1),      # giá là bool
        ("s", "n", "100", 1),     # giá là chuỗi
        ("s", "n", 1, -1),        # tồn âm (biên)
        ("s", "n", 1, 1.5),       # tồn không nguyên
        ("s", "n", 1, True),      # tồn là bool
    ])
    def test_invalid_product_rejected(self, sku, name, price, stock):
        with pytest.raises(S.InvalidProductError):
            S.Product(sku, name, price, stock)


# ----------------------------------------------------------------------------
# 2. Tồn kho
# ----------------------------------------------------------------------------
class TestInventory:
    def test_add_and_get(self, inv):
        assert inv.get("A001").name == "Bút bi"

    def test_add_duplicate_sku_rejected(self, inv):
        with pytest.raises(S.InvalidProductError):
            inv.add_product(S.Product("A001", "Khác", 1, 1))

    def test_add_non_product_rejected(self, inv):
        with pytest.raises(S.InvalidProductError):
            inv.add_product({"sku": "Z"})

    @pytest.mark.parametrize("sku", ["NOPE", "", None, 123, ["A001"]])
    def test_get_unknown_sku(self, inv, sku):
        with pytest.raises(S.InvalidProductError):
            inv.get(sku)

    def test_deduct_reduces_stock(self, inv):
        inv.deduct("A001", 30)
        assert inv.stock_of("A001") == 70

    def test_restock_increases_stock(self, inv):
        inv.restock("E005", 10)
        assert inv.stock_of("E005") == 10

    @pytest.mark.parametrize("qty", [0, -1])
    def test_restock_invalid_quantity(self, inv, qty):
        with pytest.raises(S.InvalidQuantityError):
            inv.restock("A001", qty)

    def test_deduct_all_stock_leaves_zero(self, inv):
        inv.deduct("C003", 5)
        assert inv.stock_of("C003") == 0


# ----------------------------------------------------------------------------
# 3. Số lượng mua - Boundary Value Analysis
# ----------------------------------------------------------------------------
class TestQuantityBoundary:
    @pytest.mark.parametrize("qty", [1, 2, 999, 1000])
    def test_valid_quantities(self, qty):
        assert S.validate_quantity(qty) == qty

    @pytest.mark.parametrize("qty", [0, -1, -100, 1001])
    def test_out_of_range_quantities(self, qty):
        with pytest.raises(S.InvalidQuantityError):
            S.validate_quantity(qty)

    @pytest.mark.parametrize("qty", [2.5, 1.0, "3", None, True, False, [1]])
    def test_wrong_type_quantities(self, qty):
        with pytest.raises(S.InvalidQuantityError):
            S.validate_quantity(qty)


class TestAvailabilityBoundary:
    """Tồn kho C003 = 5: kiểm tra stock-1, stock, stock+1."""

    def test_below_stock(self, inv):
        inv.check_availability("C003", 4)

    def test_exactly_stock(self, inv):
        inv.check_availability("C003", 5)

    def test_above_stock(self, inv):
        with pytest.raises(S.OutOfStockError):
            inv.check_availability("C003", 6)

    def test_zero_stock_product(self, inv):
        with pytest.raises(S.OutOfStockError):
            inv.check_availability("E005", 1)

    def test_unknown_sku(self, inv):
        with pytest.raises(S.InvalidProductError):
            inv.check_availability("NOPE", 1)


# ----------------------------------------------------------------------------
# 4. Giảm giá
# ----------------------------------------------------------------------------
class TestDiscountBoundary:
    @pytest.mark.parametrize("subtotal,coupon,expected", [
        (0, None, 0),
        (1, None, 0),
        (499_999, None, 0),            # sát dưới ngưỡng 5%
        (500_000, None, 5),            # đúng ngưỡng 5%
        (500_001, None, 5),
        (999_999, None, 5),            # sát dưới ngưỡng 10%
        (1_000_000, None, 10),         # đúng ngưỡng 10%
        (1_000_001, None, 10),
        (100_000, "", 0),              # chuỗi rỗng = không dùng coupon
        (100_000, "   ", 0),
        (100_000, "SALE10", 10),
        (100_000, "VIP20", 20),
        (100_000, "sale10", 10),       # không phân biệt hoa thường
        (100_000, "  VIP20  ", 20),    # bỏ khoảng trắng thừa
        (500_000, "SALE10", 10),       # coupon > bậc: lấy coupon
        (1_000_000, "SALE10", 10),     # bằng nhau: không cộng dồn
        (1_000_000, "VIP20", 20),
        (600_000, "SALE10", 10),
    ])
    def test_discount_percent(self, subtotal, coupon, expected):
        assert S.get_discount_percent(subtotal, coupon) == expected

    @pytest.mark.parametrize("subtotal,percent,expected", [
        (100_000, 10, 10_000),
        (999, 10, 99),                 # làm tròn xuống
        (100, 0, 0),
        (100, 100, 100),               # biên trên
        (0, 50, 0),
    ])
    def test_apply_discount_amount(self, subtotal, percent, expected):
        assert S.apply_discount(subtotal, percent) == expected

    @pytest.mark.parametrize("percent", [101, 1000, -1])
    def test_apply_discount_percent_out_of_range(self, percent):
        with pytest.raises(S.InvalidDiscountError):
            S.apply_discount(100, percent)

    @pytest.mark.parametrize("percent", [10.5, True, "10", None])
    def test_apply_discount_percent_wrong_type(self, percent):
        with pytest.raises(S.InvalidDiscountError):
            S.apply_discount(100, percent)

    def test_apply_discount_negative_subtotal(self):
        with pytest.raises(S.InvalidOrderError):
            S.apply_discount(-1, 10)

    @pytest.mark.parametrize("coupon", ["FAKE", "SALE11", 123, ["SALE10"]])
    def test_invalid_coupon(self, coupon):
        with pytest.raises(S.InvalidDiscountError):
            S.get_discount_percent(100_000, coupon)

    @pytest.mark.parametrize("subtotal", [-1, 1.5, "100", None, True])
    def test_discount_percent_invalid_subtotal(self, subtotal):
        with pytest.raises(S.InvalidOrderError):
            S.get_discount_percent(subtotal)


# ----------------------------------------------------------------------------
# 5. Phí vận chuyển & thuế
# ----------------------------------------------------------------------------
class TestShippingBoundary:
    @pytest.mark.parametrize("amount,expected", [
        (0, 0),
        (1, 30_000),
        (499_999, 30_000),
        (500_000, 0),                  # đúng ngưỡng: miễn phí
        (500_001, 0),
    ])
    def test_shipping_fee(self, amount, expected):
        assert S.calculate_shipping(amount) == expected

    @pytest.mark.parametrize("amount", [-1, 1.5, "1", None])
    def test_shipping_invalid_amount(self, amount):
        with pytest.raises(S.InvalidOrderError):
            S.calculate_shipping(amount)


class TestTaxBoundary:
    @pytest.mark.parametrize("amount,expected", [
        (0, 0),
        (6, 0),                        # 0.48 -> 0
        (7, 1),                        # 0.56 -> 1 (half-up)
        (100, 8),
        (125, 10),                     # 10.0
        (1_000_000, 80_000),
    ])
    def test_tax_amount(self, amount, expected):
        assert S.calculate_tax(amount) == expected

    @pytest.mark.parametrize("amount", [-1, 2.5, "10", None])
    def test_tax_invalid_amount(self, amount):
        with pytest.raises(S.InvalidOrderError):
            S.calculate_tax(amount)


# ----------------------------------------------------------------------------
# 6. Tính tổng tiền & chuẩn hóa đơn hàng
# ----------------------------------------------------------------------------
class TestSubtotal:
    def test_single_line(self, inv):
        assert S.calculate_subtotal(inv, [("A001", 3)]) == 30_000

    def test_multiple_lines(self, inv):
        assert S.calculate_subtotal(inv, [("A001", 3), ("B002", 2)]) == 80_000

    def test_accepts_tuple_and_list_lines(self, inv):
        assert S.calculate_subtotal(inv, (["A001", 1], ("B002", 1))) == 35_000

    def test_duplicate_lines_are_merged(self):
        assert S.normalize_items([("A", 1), ("A", 2), ("B", 1)]) == [("A", 3), ("B", 1)]

    def test_unknown_sku(self, inv):
        with pytest.raises(S.InvalidProductError):
            S.calculate_subtotal(inv, [("NOPE", 1)])


# ----------------------------------------------------------------------------
# 7. Negative testing - dữ liệu sai định dạng / thiếu
# ----------------------------------------------------------------------------
class TestNegativeOrderInput:
    @pytest.mark.parametrize("items", [[], (), None, "A001", 5, {"A001": 1}])
    def test_empty_or_wrong_container(self, inv, items):
        with pytest.raises(S.InvalidOrderError):
            S.process_order(inv, items)

    @pytest.mark.parametrize("line", [
        ("A001",), ("A001", 1, 2), "A001", None, 5, (),
    ])
    def test_malformed_line(self, inv, line):
        with pytest.raises(S.InvalidOrderError):
            S.process_order(inv, [line])

    @pytest.mark.parametrize("sku", [123, None, 1.5, ("A001",)])
    def test_non_string_sku(self, inv, sku):
        with pytest.raises(S.InvalidOrderError):
            S.process_order(inv, [(sku, 1)])

    @pytest.mark.parametrize("qty", [0, -3, 1001, 2.5, "2", None, True])
    def test_invalid_quantity_in_order(self, inv, qty):
        before = snapshot(inv)
        with pytest.raises(S.InvalidQuantityError):
            S.process_order(inv, [("A001", qty)])
        assert snapshot(inv) == before

    def test_unknown_product_in_order(self, inv):
        with pytest.raises(S.InvalidProductError):
            S.process_order(inv, [("NOPE", 1)])

    def test_invalid_coupon_does_not_change_stock(self, inv):
        before = snapshot(inv)
        with pytest.raises(S.InvalidDiscountError):
            S.process_order(inv, [("A001", 5)], coupon="FAKE")
        assert snapshot(inv) == before

    def test_out_of_stock_product(self, inv):
        with pytest.raises(S.OutOfStockError):
            S.process_order(inv, [("E005", 1)])


# ----------------------------------------------------------------------------
# 8. Xử lý đơn hàng - giá trị tính tay
# ----------------------------------------------------------------------------
class TestProcessOrder:
    def test_small_order_pays_shipping(self, inv):
        # 3 x 10.000 = 30.000; không giảm; ship 30.000; thuế 2.400
        r = S.process_order(inv, [("A001", 3)])
        assert r["subtotal"] == 30_000
        assert r["discount"] == 0
        assert r["shipping"] == 30_000
        assert r["tax"] == 2_400
        assert r["total"] == 62_400
        assert inv.stock_of("A001") == 97

    def test_tier5_order(self, inv):
        # 2 x 300.000 = 600.000; giảm 5% = 30.000; net 570.000; ship 0; thuế 45.600
        r = S.process_order(inv, [("C003", 2)])
        assert (r["discount_percent"], r["discount"], r["net"]) == (5, 30_000, 570_000)
        assert r["shipping"] == 0
        assert r["tax"] == 45_600
        assert r["total"] == 615_600

    def test_tier10_order(self, inv):
        # 1.200.000; giảm 10% = 120.000; net 1.080.000; thuế 86.400
        r = S.process_order(inv, [("D004", 1)])
        assert r["discount"] == 120_000
        assert r["tax"] == 86_400
        assert r["total"] == 1_166_400

    def test_boundary_exactly_1m_gets_10_percent(self, inv):
        # 40 x 25.000 = 1.000.000 -> 10%
        r = S.process_order(inv, [("B002", 40)])
        assert r["discount_percent"] == 10
        assert r["total"] == 972_000

    def test_boundary_exactly_500k_gets_5_percent(self, inv):
        # 20 x 25.000 = 500.000 -> 5% = 25.000; net 475.000 < 500k nên còn ship
        r = S.process_order(inv, [("B002", 20)])
        assert r["discount_percent"] == 5
        assert r["shipping"] == 30_000
        assert r["tax"] == 38_000
        assert r["total"] == 543_000

    def test_coupon_case_insensitive(self, inv):
        # 5 x 10.000 = 50.000; SALE10 -> 5.000; net 45.000; ship 30.000; thuế 3.600
        r = S.process_order(inv, [("A001", 5)], coupon="sale10")
        assert r["discount"] == 5_000
        assert r["total"] == 78_600

    def test_better_coupon_beats_tier(self, inv):
        # 600.000; VIP20 -> 120.000; net 480.000; ship 30.000; thuế 38.400
        r = S.process_order(inv, [("C003", 2)], coupon="VIP20")
        assert r["discount_percent"] == 20
        assert r["total"] == 548_400

    def test_buy_exactly_all_stock(self, inv):
        # 5 x 300.000 = 1.500.000; giảm 10%; net 1.350.000; thuế 108.000
        r = S.process_order(inv, [("C003", 5)])
        assert r["total"] == 1_458_000
        assert inv.stock_of("C003") == 0

    def test_multi_line_order_deducts_each(self, inv):
        S.process_order(inv, [("A001", 10), ("B002", 4)])
        assert inv.stock_of("A001") == 90
        assert inv.stock_of("B002") == 46

    def test_restock_then_order(self, inv):
        inv.restock("E005", 3)
        S.process_order(inv, [("E005", 3)])
        assert inv.stock_of("E005") == 0

    @pytest.mark.parametrize("items,coupon", [
        ([("A001", 1)], None),
        ([("A001", 50), ("B002", 10)], None),
        ([("B002", 20)], None),
        ([("B002", 40)], "VIP20"),
        ([("C003", 5), ("D004", 2)], "SALE10"),
    ])
    def test_total_invariant(self, inv, items, coupon):
        """Bất biến: total = subtotal - discount + shipping + tax."""
        r = S.process_order(inv, items, coupon)
        assert r["net"] == r["subtotal"] - r["discount"]
        assert r["total"] == r["net"] + r["shipping"] + r["tax"]
        assert 0 <= r["discount"] <= r["subtotal"]
        assert r["tax"] == S.calculate_tax(r["net"])

    def test_result_contains_line_details(self, inv):
        r = S.process_order(inv, [("A001", 2)])
        assert r["lines"] == [{"sku": "A001", "name": "Bút bi", "qty": 2,
                               "unit_price": 10_000, "line_total": 20_000}]


# ----------------------------------------------------------------------------
# 9. Regression - khóa lại từng lỗi đã phát hiện (BUG-xx)
# ----------------------------------------------------------------------------
class TestRegression:
    def test_bug06_failed_order_is_atomic(self, inv):
        """Dòng 2 hết hàng thì dòng 1 KHÔNG được bị trừ kho."""
        before = snapshot(inv)
        with pytest.raises(S.OutOfStockError):
            S.process_order(inv, [("A001", 5), ("C003", 10)])
        assert snapshot(inv) == before

    def test_bug10_duplicate_lines_checked_together(self, inv):
        """2 dòng C003 x3 (tổng 6) vượt tồn 5 phải bị từ chối."""
        before = snapshot(inv)
        with pytest.raises(S.OutOfStockError):
            S.process_order(inv, [("C003", 3), ("C003", 3)])
        assert snapshot(inv) == before

    def test_bug05_tax_uses_discounted_amount(self, inv):
        r = S.process_order(inv, [("D004", 1)])
        assert r["tax"] == S.calculate_tax(r["net"])
        assert r["tax"] != S.calculate_tax(r["subtotal"])

    def test_bug04_discount_never_exceeds_subtotal(self):
        with pytest.raises(S.InvalidDiscountError):
            S.apply_discount(1_000, 150)

    def test_bug01_zero_quantity_rejected_in_order(self, inv):
        with pytest.raises(S.InvalidQuantityError):
            S.process_order(inv, [("A001", 0)])

    def test_bug07_coupon_with_spaces_and_lowercase(self):
        assert S.get_discount_percent(100_000, " vip20 ") == 20

    def test_bug08_free_shipping_at_threshold(self):
        assert S.calculate_shipping(500_000) == 0

    def test_bug02_exact_stock_is_allowed(self, inv):
        S.process_order(inv, [("D004", 2)])
        assert inv.stock_of("D004") == 0

    def test_bug03_discount_tier_thresholds_are_inclusive(self, inv):
        """Đúng mốc 500.000 -> 5% và đúng mốc 1.000.000 -> 10% (không phải mức thấp hơn)."""
        assert S.get_discount_percent(500_000) == 5
        assert S.get_discount_percent(1_000_000) == 10
        r = S.process_order(inv, [("B002", 40)])      # 40 x 25.000 = 1.000.000
        assert r["discount_percent"] == 10

    @pytest.mark.parametrize("qty", [2.5, True, "3", None])
    def test_bug09_non_integer_quantity_rejected_everywhere(self, inv, qty):
        """Số lượng sai kiểu phải ném InvalidQuantityError ở mọi điểm vào, không TypeError/lọt qua."""
        with pytest.raises(S.InvalidQuantityError):
            S.validate_quantity(qty)
        with pytest.raises(S.InvalidQuantityError):
            inv.restock("A001", qty)
        with pytest.raises(S.InvalidQuantityError):
            S.process_order(inv, [("A001", qty)])

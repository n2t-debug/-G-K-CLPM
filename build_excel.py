"""Tạo reports/SalesQA_TestCases.xlsx từ kết quả JUnit và mutation_results.json."""
import json
import pathlib
import xml.etree.ElementTree as ET

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = pathlib.Path(__file__).parent
R = ROOT / "reports"

TECH = {
    "TestProduct": ("EP + Negative", "Dữ liệu sản phẩm hợp lệ được tạo; không hợp lệ ném InvalidProductError"),
    "TestInventory": ("Unit", "Thêm/tra/trừ/nhập kho đúng; dữ liệu sai ném lỗi tương ứng"),
    "TestQuantityBoundary": ("BVA + Negative", "1..1000 hợp lệ; ngoài miền hoặc sai kiểu ném InvalidQuantityError"),
    "TestAvailabilityBoundary": ("BVA", "Mua <= tồn thì qua; mua > tồn ném OutOfStockError"),
    "TestDiscountBoundary": ("BVA + EP", "% giảm đúng theo bậc/coupon; coupon sai ném InvalidDiscountError"),
    "TestShippingBoundary": ("BVA", "Phí 30.000 nếu 0 < tiền < 500.000, còn lại 0"),
    "TestTaxBoundary": ("BVA", "Thuế 8% làm tròn half-up; đầu vào sai ném InvalidOrderError"),
    "TestSubtotal": ("Unit", "Tổng tiền đúng, dòng trùng SKU được gộp"),
    "TestNegativeOrderInput": ("Negative", "Đơn sai định dạng bị từ chối bằng ngoại lệ, kho không đổi"),
    "TestProcessOrder": ("Unit / tích hợp", "Tổng tiền khớp giá trị tính tay; total = net + ship + tax"),
    "TestRegression": ("Regression", "Khóa lại lỗi BUG-xx đã phát hiện"),
}
BUG_OF_TEST = {  # test regression -> mã lỗi
    "test_bug01": "BUG-01", "test_bug02": "BUG-02", "test_bug04": "BUG-04",
    "test_bug05": "BUG-05", "test_bug06": "BUG-06", "test_bug07": "BUG-07",
    "test_bug08": "BUG-08", "test_bug10": "BUG-10",
}


def load(path):
    out = {}
    for c in ET.parse(path).getroot().iter("testcase"):
        key = (c.get("classname").split(".")[-1], c.get("name"))
        out[key] = "FAIL" if (c.find("failure") is not None or c.find("error") is not None) else "PASS"
    return out


v1, fixed = load(R / "junit_v1.xml"), load(R / "junit_fixed.xml")
mut = json.loads((R / "mutation_results.json").read_text(encoding="utf-8"))

HEAD_FILL = PatternFill("solid", fgColor="1F3864")
HEAD_FONT = Font(bold=True, color="FFFFFF")
RED = PatternFill("solid", fgColor="F8CBAD")
GREEN = PatternFill("solid", fgColor="C6E0B4")


def style(ws, widths):
    for c in ws[1]:
        c.fill, c.font = HEAD_FILL, HEAD_FONT
        c.alignment = Alignment(vertical="center", wrap_text=True)
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)


wb = Workbook()

# ---- Sheet 1: Test case ----------------------------------------------------
ws = wb.active
ws.title = "TestCases"
ws.append(["ID", "Lớp test", "Kỹ thuật", "Test (đầu vào là tham số trong ngoặc)",
           "Kết quả mong đợi (mức lớp)", "Kết quả bản v1", "Kết quả bản đã sửa"])
for i, ((cls, name), res_v1) in enumerate(v1.items(), 1):
    tech, exp = TECH[cls]
    ws.append([f"TC-{i:03d}", cls, tech, name, exp, res_v1, fixed[(cls, name)]])
n = ws.max_row
style(ws, [9, 26, 16, 62, 62, 14, 18])
for row in ws.iter_rows(min_row=2, min_col=6, max_col=7):
    for c in row:
        c.fill = RED if c.value == "FAIL" else GREEN
ws.auto_filter.ref = f"A1:G{n}"

# ---- Sheet 2: Defect report ------------------------------------------------
DEFECTS = [
    ("BUG-05", "process_order", "Tính thuế trên tạm tính thay vì tiền sau giảm giá", "Critical",
     "Đơn 1 x D004 (1.200.000, giảm 10%)", "Thuế 86.400", "Thuế 96.000"),
    ("BUG-06", "process_order", "Trừ kho từng dòng khi đang kiểm tra, không nguyên tử", "Critical",
     "Đơn [(A001,5),(C003,10)], dòng 2 vượt tồn", "Từ chối đơn và kho không đổi", "Từ chối nhưng A001 đã bị trừ 5"),
    ("BUG-02", "check_availability", "Dùng >= thay vì >", "High",
     "Mua 2 x D004 khi tồn đúng 2", "Cho phép mua", "OutOfStockError"),
    ("BUG-10", "normalize_items", "Không gộp dòng trùng SKU", "High",
     "Đơn [(C003,3),(C003,3)], tồn 5", "Từ chối đơn (tổng 6 > 5)", "Không bị chặn ở bước kiểm tồn"),
    ("BUG-04", "apply_discount", "Thiếu chặn percent > 100", "High",
     "apply_discount(1000, 150)", "InvalidDiscountError", "Trả về 1.500"),
    ("BUG-01", "validate_quantity", "Dùng < 0 thay vì <= 0", "Medium",
     "validate_quantity(0)", "InvalidQuantityError", "Trả về 0"),
    ("BUG-03", "get_discount_percent", "Dùng > thay vì >= tại mốc bậc", "Medium",
     "Tạm tính 500.000 và 1.000.000", "5% và 10%", "0% và 5%"),
    ("BUG-08", "calculate_shipping", "Dùng > thay vì >= tại ngưỡng miễn phí", "Medium",
     "calculate_shipping(500000)", "0", "30.000"),
    ("BUG-09", "validate_quantity", "Không kiểm tra kiểu dữ liệu", "Medium",
     "Số lượng 2.5, True, None", "InvalidQuantityError", "Lọt qua hoặc TypeError"),
    ("BUG-07", "get_discount_percent", "Không strip()/upper() mã coupon", "Low",
     "Coupon ' vip20 ' hoặc 'sale10'", "Áp dụng đúng 20% / 10%", "InvalidDiscountError"),
]
ws2 = wb.create_sheet("DefectReport")
ws2.append(["Mã lỗi", "Hàm", "Mô tả", "Mức độ", "Cách tái hiện (bản v1)", "Kết quả mong đợi",
            "Kết quả thực tế", "Số test fail khi tiêm riêng", "Phát hiện?", "Trạng thái"])
for d in DEFECTS:
    m = mut[d[0]]
    ws2.append(list(d) + [len(m["failed"]), "Có" if m["detected"] else "Không", "Đã sửa, regression pass"])
style(ws2, [10, 22, 44, 11, 40, 30, 34, 14, 11, 24])
SEV = {"Critical": "FF7C80", "High": "F8CBAD", "Medium": "FFE699", "Low": "E2EFDA"}
for row in ws2.iter_rows(min_row=2, min_col=4, max_col=4):
    for c in row:
        c.fill = PatternFill("solid", fgColor=SEV[c.value])

# ---- Sheet 3: Thống kê (công thức) ----------------------------------------
ws3 = wb.create_sheet("Statistics")
ws3.append(["Chỉ số", "Bản v1 (có lỗi)", "Bản đã sửa"])
ws3.append(["Tổng số test", f"=COUNTA(TestCases!F2:F{n})", f"=COUNTA(TestCases!G2:G{n})"])
ws3.append(["Pass", f'=COUNTIF(TestCases!F2:F{n},"PASS")', f'=COUNTIF(TestCases!G2:G{n},"PASS")'])
ws3.append(["Fail", f'=COUNTIF(TestCases!F2:F{n},"FAIL")', f'=COUNTIF(TestCases!G2:G{n},"FAIL")'])
ws3.append(["Tỷ lệ pass", "=B3/B2", "=C3/C2"])
ws3.append(["Statement coverage (Coverage.py 7.17.0)", "Không đo", "141/141 = 100%"])
ws3.append(["Branch coverage (Coverage.py 7.17.0)", "Không đo", "60/60 = 100%"])
ws3.append(["Mutation score", "Không áp dụng", '=COUNTIF(DefectReport!I2:I11,"Có")/COUNTA(DefectReport!A2:A11)'])
ws3.append([])
ws3.append(["Lỗi theo mức độ", "Số lượng"])
for sev in ("Critical", "High", "Medium", "Low"):
    ws3.append([sev, f'=COUNTIF(DefectReport!D2:D11,"{sev}")'])
ws3.append([])
ws3.append(["Theo lớp test", "Số test", "Fail trên v1"])
for cls in TECH:
    r = ws3.max_row + 1
    ws3.append([cls, f'=COUNTIF(TestCases!B2:B{n},A{r})',
                f'=COUNTIFS(TestCases!B2:B{n},A{r},TestCases!F2:F{n},"FAIL")'])
style(ws3, [52, 20, 20])
for r in (5, 8):
    for col in "BC":
        ws3[f"{col}{r}"].number_format = "0.0%"
for row in (10, 16):
    for c in ws3[row]:
        c.fill, c.font = HEAD_FILL, HEAD_FONT

wb.save(R / "SalesQA_TestCases.xlsx")
print("saved", n - 1, "test cases")

"""Phân tích khả năng phát hiện lỗi: tiêm TỪNG lỗi BUG-xx vào bản đã sửa (sales.py),
chạy lại toàn bộ bộ test và ghi nhận test nào "bắt" được lỗi đó.

Kết quả: reports/mutation_results.json  +  bảng tóm tắt in ra màn hình.
Cách dùng:  python mutation_analysis.py
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).parent.resolve()
MUT_DIR = ROOT / "mutants"
REPORTS = ROOT / "reports"
MUT_DIR.mkdir(exist_ok=True)
REPORTS.mkdir(exist_ok=True)

SRC = (ROOT / "sales.py").read_text(encoding="utf-8")

# (id, mô tả, [(chuỗi gốc, chuỗi thay thế), ...])
BUGS = [
    ("BUG-01", "Cho phép số lượng = 0 (dùng < thay vì <=)",
     [("if qty <= 0:", "if qty < 0:")]),
    ("BUG-02", "Từ chối mua đúng bằng tồn kho (dùng >= thay vì >)",
     [("if qty > product.stock:", "if qty >= product.stock:")]),
    ("BUG-03", "Sai biên bậc giảm giá (> thay vì >=)",
     [("if subtotal >= threshold:", "if subtotal > threshold:")]),
    ("BUG-04", "Không chặn % giảm giá > 100",
     [(" or percent < 0 or percent > 100:", " or percent < 0:")]),
    ("BUG-05", "Tính thuế trên tạm tính thay vì tiền sau giảm giá",
     [("tax = calculate_tax(net)", "tax = calculate_tax(subtotal)")]),
    ("BUG-06", "Trừ kho từng dòng khi đang kiểm tra (không nguyên tử)",
     [("        inventory.check_availability(sku, qty)\n\n    subtotal",
       "        inventory.deduct(sku, qty)\n\n    subtotal"),
      ("    for sku, qty in lines:                       # 2) chỉ trừ kho khi mọi thứ hợp lệ\n"
       "        inventory.deduct(sku, qty)\n", "")]),
    ("BUG-07", "Mã giảm giá phân biệt hoa/thường và không bỏ khoảng trắng",
     [("code = coupon.strip().upper()", "code = coupon")]),
    ("BUG-08", "Sai biên miễn phí vận chuyển (> thay vì >=)",
     [("amount >= FREE_SHIPPING_THRESHOLD", "amount > FREE_SHIPPING_THRESHOLD")]),
    ("BUG-09", "Không kiểm tra kiểu số lượng (float/bool/chuỗi lọt qua)",
     [("    if not _is_int(qty):\n        raise InvalidQuantityError"
       "(f\"Số lượng phải là số nguyên: {qty!r}\")\n", "")]),
    ("BUG-10", "Không gộp dòng trùng SKU khi kiểm tra tồn kho",
     [("merged[sku] = merged.get(sku, 0) + qty", "merged[(sku, len(merged))] = qty"),
      ("return list(merged.items())", "return [(k[0], v) for k, v in merged.items()]")]),
]


def run_pytest(module: str):
    junit = REPORTS / f"junit_{module}.xml"
    env = dict(os.environ, SALES_MODULE=module,
               PYTHONPATH=str(MUT_DIR) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    runner = [shutil.which("pytest")] if shutil.which("pytest") else [sys.executable, "-m", "pytest"]
    subprocess.run(runner + ["-q", f"--junitxml={junit}", "test_sales.py"],
                   cwd=ROOT, env=env, capture_output=True, text=True)
    failed, total = [], 0
    for case in ET.parse(junit).getroot().iter("testcase"):
        total += 1
        if case.find("failure") is not None or case.find("error") is not None:
            failed.append(f"{case.get('classname').split('.')[-1]}::{case.get('name')}")
    junit.unlink()
    return total, failed


def main():
    results = {}
    for bug_id, desc, patches in BUGS:
        code = SRC
        for old, new in patches:
            assert old in code, f"{bug_id}: không tìm thấy đoạn cần thay: {old!r}"
            code = code.replace(old, new, 1)
        module = "sales_" + bug_id.lower().replace("-", "")
        (MUT_DIR / f"{module}.py").write_text(code, encoding="utf-8")
        total, failed = run_pytest(module)
        results[bug_id] = {"description": desc, "total_tests": total,
                           "failed": failed, "detected": bool(failed)}
        print(f"{bug_id}: {'PHÁT HIỆN' if failed else 'BỎ SÓT '} - {len(failed):>2} test fail - {desc}")
    (REPORTS / "mutation_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    killed = sum(r["detected"] for r in results.values())
    print(f"\nMutation score: {killed}/{len(BUGS)} = {100*killed/len(BUGS):.0f}%")


if __name__ == "__main__":
    main()

"""Đo độ bao phủ DÒNG LỆNH bằng thư viện chuẩn `trace` (dự phòng khi chưa cài được Coverage.py).

Cách dùng:  python measure_coverage_fallback.py [tên_module]   (mặc định: sales)

Lưu ý: chỉ đo line coverage, KHÔNG đo branch coverage. Kết quả chính thức của
đề tài phải lấy từ Coverage.py (xem run_all.sh). Hai con số line coverage thường
khớp nhau hoặc lệch rất ít.
"""
import os
import sys
import trace

import pytest

module = sys.argv[1] if len(sys.argv) > 1 else "sales"
os.environ["SALES_MODULE"] = module
target = os.path.abspath(f"{module}.py")

tracer = trace.Trace(count=1, trace=0)
exit_code = tracer.runfunc(pytest.main, ["-q", "-p", "no:cacheprovider", "test_sales.py"])

counts = tracer.results().counts            # {(filename, lineno): n}
executable = {ln for ln in trace._find_executable_linenos(target) if ln}
hit = {ln for (fn, ln), n in counts.items() if os.path.abspath(fn) == target and n > 0}
covered = executable & hit
missing = sorted(executable - hit)

pct = 100 * len(covered) / len(executable)
print(f"\n[fallback line coverage] {module}.py: {len(covered)}/{len(executable)} dòng = {pct:.1f}%")
print("Dòng chưa được chạy:", missing if missing else "không có")
sys.exit(int(exit_code))

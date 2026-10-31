# Đánh giá chất lượng phần mềm quản lý bán hàng bằng kiểm thử tự động

Kiểm thử đơn vị tự động và đo độ bao phủ mã nguồn với **Pytest** và **Coverage.py**.

> Thành viên nhóm: 22
> Nguyễn Trọng Thái - 23010457
> Nguyễn Minh Quang - 23010419
> Giảng viên hướng dẫn: Trịnh Thanh Bình

## 1. Giới thiệu

Đề tài đánh giá chất lượng một module logic nghiệp vụ quản lý bán hàng viết bằng Python: sản phẩm và tồn kho, tính tổng tiền, giảm giá, phí vận chuyển, thuế và xử lý đơn hàng không hợp lệ. Không có giao diện web hay thanh toán thực tế.

Repo có hai phiên bản của chương trình:

| File | Mô tả |
| --- | --- |
| `sales.py` | Phiên bản đã sửa lỗi |
| `sales_v1.py` | Phiên bản ban đầu, chứa **10 lỗi do nhóm cài sẵn** (`BUG-01` đến `BUG-10`) để kiểm tra khả năng phát hiện lỗi của bộ test. Đây là lỗi mô phỏng, không phải lỗi tự nhiên |

## 2. Kết quả chính

| Chỉ số | Kết quả |
| --- | --- |
| Số test | 166 |
| Bản đã sửa (`sales.py`) | 166/166 pass |
| Bản có lỗi (`sales_v1.py`) | 50 fail, 116 pass (tỷ lệ pass 69,9%) |
| Mutation score (phát hiện lỗi cài sẵn) | 10/10 = 100% |
| Statement coverage (Coverage.py 7.17.0) | 141/141 = 100% |
| Branch coverage (Coverage.py 7.17.0) | 60/60 = 100% |
| Lỗi theo mức độ | 2 Critical, 3 High, 4 Medium, 1 Low |

Số coverage đo lúc bộ test còn 161 test, trước khi thêm 5 test regression. Nên chạy lại lệnh ở mục 4 để có số cuối.

## 3. Cài đặt

Yêu cầu Python 3.9 trở lên.

**Windows (PowerShell):**

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 4. Chạy kiểm thử

| Mục đích | Lệnh | Kết quả mong đợi |
| --- | --- | --- |
| Test bản đã sửa | `pytest` | 166 passed |
| Test bản có lỗi (Windows) | `set SALES_MODULE=sales_v1` rồi `pytest` | 50 failed, 116 passed |
| Test bản có lỗi (macOS/Linux) | `SALES_MODULE=sales_v1 pytest` | 50 failed, 116 passed |
| Đo coverage (câu lệnh + nhánh) | `coverage run --branch --include=sales.py -m pytest` rồi `coverage report -m` | 100% |
| Báo cáo coverage HTML | `coverage html` rồi mở `htmlcov/index.html` | trang chi tiết |
| Phân tích khả năng phát hiện lỗi | `python mutation_analysis.py` | `Mutation score: 10/10 = 100%` |
| Tạo lại file Excel thống kê | `python build_excel.py` | `reports/SalesQA_TestCases.xlsx` |

Trên Windows, sau khi test bản có lỗi, gõ `set SALES_MODULE=` để quay lại bản đã sửa. Trên macOS/Linux có thể chạy cả quy trình bằng `bash run_all.sh`.

## 5. Cấu trúc thư mục

```
.
|-- sales.py                       # Chương trình (bản đã sửa)
|-- sales_v1.py                    # Chương trình (bản có 10 lỗi cài sẵn)
|-- test_sales.py                  # 166 test; biến SALES_MODULE chọn bản cần test
|-- pytest.ini                     # Cấu hình Pytest
|-- requirements.txt               # Thư viện cần cài
|-- run_all.sh                     # Chạy toàn bộ quy trình với Coverage.py
|-- mutation_analysis.py           # Tiêm từng lỗi vào bản đã sửa, tính mutation score
|-- measure_coverage_fallback.py   # Đo line coverage dự phòng bằng module trace
|-- build_excel.py                 # Tạo file Excel test case / defect / thống kê
`-- reports/                       # Kết quả chạy (JUnit XML, coverage, mutation, Excel)
```

## 6. Phương pháp kiểm thử

Mỗi lớp test trong `test_sales.py` ứng với một kỹ thuật:

| Kỹ thuật | Lớp test tiêu biểu |
| --- | --- |
| Unit Testing | `TestInventory`, `TestSubtotal`, `TestProcessOrder` |
| Boundary Value Analysis | `TestQuantityBoundary`, `TestAvailabilityBoundary`, `TestDiscountBoundary`, `TestShippingBoundary`, `TestTaxBoundary` |
| Equivalence Partitioning | `TestProduct`, `TestDiscountBoundary` |
| Negative Testing | `TestNegativeOrderInput`, `TestProduct` |
| Regression Testing | `TestRegression` (mỗi lỗi trong 10 lỗi có ít nhất một test khóa) |
| Coverage Analysis | Coverage.py với `--branch` |

## 7. Quy tắc nghiệp vụ chính

- Số lượng mỗi dòng là số nguyên từ 1 đến 1.000.
- Mua tối đa bằng số tồn; dòng trùng SKU được gộp trước khi kiểm tồn.
- Giảm giá theo bậc: từ 500.000 giảm 5%, từ 1.000.000 giảm 10%. Mã `SALE10` (10%) và `VIP20` (20%); lấy mức cao hơn, không cộng dồn.
- Phí vận chuyển 30.000, miễn phí khi tiền sau giảm từ 500.000.
- Thuế 8% tính trên tiền sau giảm, làm tròn half-up.
- Đơn lỗi phải bị từ chối bằng ngoại lệ và không làm thay đổi tồn kho.

## 8. Hạn chế

- 10 lỗi do nhóm tự cài cùng lúc với bộ test, nên mutation score 10/10 có thể cao hơn thực tế.
- Module nhỏ, không có cơ sở dữ liệu, đa luồng hay thanh toán thật.
- Các ngưỡng đánh giá (90% coverage, 0 lỗi Critical/High) do nhóm tự đặt.

## 9. Công cụ

Python, Pytest, Coverage.py, openpyxl, Git và GitHub.

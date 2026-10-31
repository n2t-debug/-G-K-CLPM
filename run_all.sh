#!/usr/bin/env bash
# Chạy toàn bộ quy trình kiểm thử + đo độ bao phủ bằng Pytest và Coverage.py.
# Yêu cầu:  pip install -r requirements.txt
set -u
mkdir -p reports

echo "== 1) Bản v1 (có lỗi cài sẵn): kỳ vọng nhiều test FAIL =="
SALES_MODULE=sales_v1 python -m pytest -q --junitxml=reports/junit_v1.xml \
  | tee reports/pytest_v1.txt
SALES_MODULE=sales_v1 python -m coverage run --branch --include=sales_v1.py -m pytest -q >/dev/null
python -m coverage report -m | tee reports/coverage_v1.txt
python -m coverage erase

echo "== 2) Bản đã sửa lỗi (regression): kỳ vọng tất cả PASS =="
python -m pytest -q --junitxml=reports/junit_fixed.xml | tee reports/pytest_fixed.txt
python -m coverage run --branch --include=sales.py -m pytest -q >/dev/null
python -m coverage report -m | tee reports/coverage_fixed.txt
python -m coverage html -d reports/htmlcov
python -m coverage xml -o reports/coverage.xml
echo "Xong. Xem reports/htmlcov/index.html"

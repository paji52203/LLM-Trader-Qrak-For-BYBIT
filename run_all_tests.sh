source venv/bin/activate
echo "Checking dev dependencies..."
pip install -r requirements-dev.txt > /dev/null 2>&1

echo "Starting tests..."
pytest --timeout=30 tests/

python_output=$(xvfb-run --server-args="-screen 0 1892x880x24 -dpi 96" python3 test.py)
echo "Detected: $python_output"

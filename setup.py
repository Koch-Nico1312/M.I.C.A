import subprocess
import sys

print("Installing requirements...")
subprocess.run(
    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True, encoding="utf-8"
)

print("Installing PI requirements...")
subprocess.run(
    [sys.executable, "-m", "pip", "install", "-r", "requirements.mica-pi.txt"], check=True, encoding="utf-8"
)

print("Installing Playwright browsers...")
subprocess.run([sys.executable, "-m", "playwright", "install"], check=True, encoding="utf-8")

print("Installing pre-commit...")
subprocess.run([sys.executable, "-m", "pip", "install", "pre-commit"], check=True, encoding="utf-8")

print("Setting up pre-commit hooks...")
subprocess.run([sys.executable, "-m", "pre_commit", "install"], check=True, encoding="utf-8")

print(
    "\n✅ Setup complete! Run '.\\venv\\Scripts\\python.exe .\\main.py' on Windows or 'python3 main.py' on macOS/Linux."
)
print("📝 Pre-commit hooks are installed. They will run automatically on git commit.")

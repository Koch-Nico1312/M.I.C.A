import subprocess
import sys

print("Installing requirements...")
subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True, encoding='utf-8')

print("Installing Playwright browsers...")
subprocess.run([sys.executable, "-m", "playwright", "install"], check=True, encoding='utf-8')

print("\n✅ Setup complete! Run 'python main.py' to start MARK XXV.")


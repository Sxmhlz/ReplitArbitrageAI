import subprocess
import sys

def install_requirements():
    print("Installing required packages...")
    try:
        subprocess.check_call([
            sys.executable, 
            "-m", 
            "pip", 
            "install", 
            "-r", 
            "requirements.txt"
        ])
        print("All requirements installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error installing requirements: {e}")
        return False

if __name__ == "__main__":
    if not install_requirements():
        sys.exit(1)

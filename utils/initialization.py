import sys
from pathlib import Path
from typing import List

def setup_environment():
    """Konfiguriert die Projektumgebung."""
    PROJECT_ROOT = Path(__file__).parent.parent
    directories = ['data', 'logs', 'models', 'config']
    
    for directory in directories:
        Path(PROJECT_ROOT / directory).mkdir(parents=True, exist_ok=True)

def check_dependencies() -> bool:
    """Überprüft ob alle benötigten Dependencies installiert sind."""
    required_modules: List[str] = [
        'torch',
        'aiohttp',
        'asyncio',
        'sqlalchemy',
        'redis'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
            print(f"Fehlendes Modul: {module}")
    
    if missing_modules:
        print("Bitte installiere die fehlenden Module mit:")
        print("pip install " + " ".join(missing_modules))
        return False
        
    return True

import asyncio
import signal
import sys
import logging
import platform
from pathlib import Path
from typing import Optional
from functools import partial

logger = logging.getLogger('Environment')

class SignalHandler:
    def __init__(self, bot):
        self.bot = bot
        self.shutdown_event = asyncio.Event()
        self.is_windows = platform.system() == 'Windows'
        self.loop = asyncio.get_event_loop()
        self._shutdown_complete = False

    async def handle_shutdown(self, sig: signal.Signals):
        """Behandelt den Shutdown-Prozess für verschiedene Signale."""
        if self._shutdown_complete:
            return

        sig_name = sig.name if hasattr(sig, 'name') else str(sig)
        logger.info(f"Signal {sig_name} empfangen, initiiere graceful shutdown...")

        try:
            self._shutdown_complete = True
            self.shutdown_event.set()
            
            # Stoppe Bot-Operationen
            if hasattr(self.bot, 'running'):
                self.bot.running = False

            # Warte auf Bot-Shutdown
            if hasattr(self.bot, 'shutdown'):
                await self.bot.shutdown()

            logger.info("Graceful shutdown abgeschlossen")

        except Exception as e:
            logger.error(f"Fehler während Shutdown: {e}")
            raise

    def setup_signal_handlers(self):
        """Registriert Signal-Handler basierend auf Plattform."""
        try:
            if self.is_windows:
                # Windows-spezifisches Signal-Handling
                for sig in (signal.SIGINT, signal.SIGTERM):
                    self.loop.add_signal_handler(
                        sig,
                        lambda s=sig: asyncio.create_task(self.handle_shutdown(s))
                    )
            else:
                # Unix-spezifisches Signal-Handling
                for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                    self.loop.add_signal_handler(
                        sig,
                        lambda s=sig: asyncio.create_task(self.handle_shutdown(s))
                    )

            logger.info(f"Signal-Handler für {platform.system()} registriert")
            
        except NotImplementedError:
            # Fallback für Systeme ohne Signal-Support
            logger.warning("Signal-Handling nicht verfügbar auf diesem System")
            
        except Exception as e:
            logger.error(f"Fehler bei Signal-Handler Setup: {e}")
            raise

    def cleanup_handlers(self):
        """Entfernt alle registrierten Signal-Handler."""
        try:
            signals = (signal.SIGINT, signal.SIGTERM)
            if not self.is_windows:
                signals += (signal.SIGHUP,)

            for sig in signals:
                self.loop.remove_signal_handler(sig)
                
            logger.info("Signal-Handler erfolgreich entfernt")
            
        except Exception as e:
            logger.error(f"Fehler beim Entfernen der Signal-Handler: {e}")

class EnvironmentManager:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.signal_handler: Optional[SignalHandler] = None

    def setup_environment(self):
        """Konfiguriert die Projektumgebung."""
        directories = ['data', 'logs', 'models', 'config']
        
        for directory in directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Verzeichnis erstellt/überprüft: {directory}")

    def register_bot(self, bot):
        """Registriert den Bot und initialisiert Signal-Handling."""
        self.signal_handler = SignalHandler(bot)
        self.signal_handler.setup_signal_handlers()
        return self.signal_handler

    async def cleanup(self):
        """Bereinigt die Umgebung beim Shutdown."""
        if self.signal_handler:
            self.signal_handler.cleanup_handlers()

def handle_signals(bot):
    """Hauptfunktion für Signal-Handling Setup."""
    try:
        env_manager = EnvironmentManager(Path(__file__).parent.parent)
        env_manager.setup_environment()
        signal_handler = env_manager.register_bot(bot)
        return signal_handler
    except Exception as e:
        logger.error(f"Fehler beim Signal-Handler Setup: {e}")
        raise

import torch
from ml.model import RestockPredictor
import os

# Sicherstellen dass der models Ordner existiert
os.makedirs('models', exist_ok=True)

# Restock-Vorhersage-Modell initialisieren
restock_model = RestockPredictor(
    input_size=10,  # Anzahl der Features für Restock-Vorhersage
    hidden_size=128,
    dropout=0.3
)

# Dummy-Input für initialen Forward-Pass
dummy_input = torch.randn(1, 10)  # Batch_size=1, features=10

# Forward-Pass durchführen
with torch.no_grad():
    restock_model(dummy_input)

# Modell speichern
torch.save({
    'model_state_dict': restock_model.state_dict(),
    'model_config': {
        'input_size': 10,
        'hidden_size': 128
    }
}, 'models/restock_prediction.pt')

print("Restock-Vorhersagemodell erfolgreich erstellt und gespeichert.")

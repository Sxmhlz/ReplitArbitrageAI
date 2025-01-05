from typing import Dict, Optional
import logging

class SizeConverter:
    # Größentabellen für verschiedene Marken
    ADIDAS_SIZES = {
        'EU': {
            '38': 'US 5.5', '38.5': 'US 6', '39': 'US 6.5',
            '40': 'US 7', '40.5': 'US 7.5', '41': 'US 8',
            '42': 'US 8.5', '42.5': 'US 9', '43': 'US 9.5',
            '44': 'US 10', '44.5': 'US 10.5', '45': 'US 11'
        }
    }
    
    NIKE_SIZES = {
        'EU': {
            '38': 'US 5.5', '38.5': 'US 6', '39': 'US 6.5',
            '40': 'US 7', '40.5': 'US 7.5', '41': 'US 8',
            '42': 'US 8.5', '42.5': 'US 9', '43': 'US 9.5',
            '44': 'US 10', '44.5': 'US 10.5', '45': 'US 11'
        }
    }
    
    ASICS_SIZES = {
        'EU': {
            '38': 'US 6', '38.5': 'US 6.5', '39': 'US 7',
            '40': 'US 7.5', '40.5': 'US 8', '41.5': 'US 8.5',
            '42': 'US 9', '42.5': 'US 9.5', '43.5': 'US 10',
            '44': 'US 10.5', '44.5': 'US 11', '45': 'US 11.5'
        }
    }
    
    NEW_BALANCE_SIZES = {
        'EU': {
            '38': 'US 5.5', '38.5': 'US 6', '39': 'US 6.5',
            '40': 'US 7', '40.5': 'US 7.5', '41': 'US 8',
            '42': 'US 8.5', '42.5': 'US 9', '43': 'US 9.5',
            '44': 'US 10', '44.5': 'US 10.5', '45': 'US 11'
        }
    }

    def __init__(self):
        self.logger = logging.getLogger("SizeConverter")
        self.brand_mappings = {
            'ADIDAS': self.ADIDAS_SIZES,
            'NIKE': self.NIKE_SIZES,
            'ASICS': self.ASICS_SIZES,
            'NEW_BALANCE': self.NEW_BALANCE_SIZES
        }

    def eu_to_us(
        self,
        eu_size: str,
        brand: str
    ) -> Optional[str]:
        """Konvertiert EU zu US Größe."""
        try:
            brand = brand.upper()
            if brand not in self.brand_mappings:
                raise ValueError(f"Unsupported brand: {brand}")
                
            return self.brand_mappings[brand]['EU'].get(eu_size)
        except Exception as e:
            self.logger.error(f"Error converting EU to US size: {e}")
            return None

    def us_to_eu(
        self,
        us_size: str,
        brand: str
    ) -> Optional[str]:
        """Konvertiert US zu EU Größe."""
        try:
            brand = brand.upper()
            if brand not in self.brand_mappings:
                raise ValueError(f"Unsupported brand: {brand}")
                
            size_mapping = self.brand_mappings[brand]['EU']
            for eu_size, mapped_us_size in size_mapping.items():
                if mapped_us_size == us_size:
                    return eu_size
            return None
        except Exception as e:
            self.logger.error(f"Error converting US to EU size: {e}")
            return None

    def get_all_sizes(
        self,
        brand: str
    ) -> Dict[str, str]:
        """Gibt alle verfügbaren Größen für eine Marke zurück."""
        try:
            brand = brand.upper()
            if brand not in self.brand_mappings:
                raise ValueError(f"Unsupported brand: {brand}")
                
            return self.brand_mappings[brand]['EU']
        except Exception as e:
            self.logger.error(f"Error getting sizes for brand {brand}: {e}")
            return {}
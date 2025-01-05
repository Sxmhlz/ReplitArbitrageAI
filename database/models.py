from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class ProductStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MONITORING = "monitoring"

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    sku = Column(String, unique=True, index=True)
    name = Column(String)
    brand = Column(String)
    model = Column(String)
    size = Column(String)
    
    # Preise und Profitabilität
    hhv_price = Column(Float)
    alias_price = Column(Float)
    profit_margin = Column(Float)
    roi = Column(Float)
    
    # Verkaufsstatistiken
    monthly_sales = Column(Integer, default=0)
    total_sales = Column(Integer, default=0)
    sales_velocity = Column(Float, default=0.0)
    
    # Restock-Informationen
    last_restock = Column(DateTime)
    restock_probability = Column(Float, default=0.0)
    restock_frequency = Column(Integer, default=0)
    is_discountable = Column(Boolean, default=False)
    
    # Status und Tracking
    status = Column(Enum(ProductStatus), default=ProductStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_checked = Column(DateTime)
    
    # Beziehungen
    prices = relationship("Price", back_populates="product", cascade="all, delete-orphan")
    restock_history = relationship("RestockHistory", back_populates="product", cascade="all, delete-orphan")
    deals = relationship("Deal", back_populates="product", cascade="all, delete-orphan")

class Price(Base):
    __tablename__ = 'price_history'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), index=True)
    hhv_price = Column(Float)
    alias_price = Column(Float)
    profit_margin = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    source = Column(String)  # 'hhv' oder 'alias'
    
    product = relationship("Product", back_populates="prices")

class RestockHistory(Base):
    __tablename__ = 'restock_history'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), index=True)
    available_stock = Column(Integer)
    restock_amount = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    detected_by = Column(String)  # 'scanner' oder 'monitor'
    
    product = relationship("Product", back_populates="restock_history")

class Deal(Base):
    __tablename__ = 'deals'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), index=True)
    hhv_price = Column(Float)
    alias_price = Column(Float)
    profit_margin = Column(Float)
    roi = Column(Float)
    found_at = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String)  # 'new', 'processed', 'expired'
    notification_sent = Column(Boolean, default=False)
    
    product = relationship("Product", back_populates="deals")

class MLData(Base):
    __tablename__ = 'ml_data'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), index=True)
    features = Column(String)  # JSON-String der Feature-Daten
    target = Column(Float)
    prediction = Column(Float)
    accuracy = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    product = relationship("Product")

# Export der Klassen
__all__ = ['Base', 'Product', 'Price', 'RestockHistory', 'Deal', 'MLData', 'ProductStatus']

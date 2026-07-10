from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

Base = declarative_base()

# --- Table 1: Sales transactions ---
class Sale(Base):
    __tablename__ = "sales"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    date          = Column(Date, nullable=False)
    region        = Column(String(50), nullable=False)   # e.g. Odisha, Maharashtra
    city          = Column(String(50), nullable=False)
    product       = Column(String(100), nullable=False)
    category      = Column(String(50), nullable=False)   # Electronics, Clothing, etc.
    quantity      = Column(Integer, nullable=False)
    unit_price    = Column(Float, nullable=False)
    revenue       = Column(Float, nullable=False)
    discount_pct  = Column(Float, default=0.0)
    sales_rep     = Column(String(50))
    channel       = Column(String(30))                   # Online, Retail, Wholesale

# --- Table 2: Customers ---
class Customer(Base):
    __tablename__ = "customers"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    name          = Column(String(100), nullable=False)
    city          = Column(String(50))
    region        = Column(String(50))
    segment       = Column(String(30))                   # Retail, Corporate, SMB
    join_date     = Column(Date)
    total_orders  = Column(Integer, default=0)
    total_spent   = Column(Float, default=0.0)

# --- Table 3: Products ---
class Product(Base):
    __tablename__ = "products"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    name          = Column(String(100), nullable=False)
    category      = Column(String(50))
    sub_category  = Column(String(50))
    cost_price    = Column(Float)
    selling_price = Column(Float)
    stock_qty     = Column(Integer, default=0)
    supplier      = Column(String(100))

# --- Table 4: Returns ---
class Return(Base):
    __tablename__ = "returns"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    sale_id       = Column(Integer, nullable=False)
    return_date   = Column(Date)
    reason        = Column(String(200))
    refund_amount = Column(Float)
    region        = Column(String(50))


def get_engine(db_path="sample_data/sales.db"):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return engine


def create_all_tables(db_path="sample_data/sales.db"):
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    print(f"✅ Tables created at {db_path}")
    return engine


def get_session(db_path="sample_data/sales.db"):
    engine = get_engine(db_path)
    Session = sessionmaker(bind=engine)
    return Session()
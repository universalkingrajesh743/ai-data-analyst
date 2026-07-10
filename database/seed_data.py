import random
from datetime import date, timedelta
from database.schema import Sale, Customer, Product, Return, create_all_tables, get_session

random.seed(42)

REGIONS = {
    "Odisha":       ["Bhubaneswar", "Cuttack", "Brahmapur", "Rourkela", "Sambalpur"],
    "Maharashtra":  ["Mumbai", "Pune", "Nagpur", "Nashik"],
    "Karnataka":    ["Bengaluru", "Mysuru", "Hubli"],
    "Delhi":        ["New Delhi", "Noida", "Gurugram"],
    "Tamil Nadu":   ["Chennai", "Coimbatore", "Madurai"],
}

PRODUCTS = [
    ("Laptop Pro 15",      "Electronics",  "Computers",    38000, 52000),
    ("Wireless Earbuds",   "Electronics",  "Audio",         1800,  2999),
    ("Smart Watch",        "Electronics",  "Wearables",     4500,  7499),
    ("Office Chair",       "Furniture",    "Seating",       5200,  8999),
    ("Standing Desk",      "Furniture",    "Desks",        12000, 18500),
    ("Cotton Kurta",       "Clothing",     "Ethnic",          450,   899),
    ("Running Shoes",      "Clothing",     "Footwear",       1800,  3299),
    ("Whey Protein 1kg",   "Health",       "Supplements",   1200,  1999),
    ("Air Purifier",       "Appliances",   "Home",          6500,  9999),
    ("Rice Cooker 3L",     "Appliances",   "Kitchen",       1100,  1799),
    ("Python Book",        "Books",        "Tech",           400,   699),
    ("Yoga Mat",           "Health",       "Fitness",        600,   999),
]

CHANNELS    = ["Online", "Retail", "Wholesale"]
SEGMENTS    = ["Retail", "Corporate", "SMB"]
RETURN_REASONS = [
    "Defective product", "Wrong item delivered",
    "Changed mind", "Better price elsewhere", "Packaging damaged"
]

SALES_REPS = ["Arjun Patel", "Priya Sharma", "Ravi Kumar",
              "Sunita Das", "Mohan Singh", "Anita Roy"]


def random_date(start: date, end: date) -> date:
    return start + timedelta(days=random.randint(0, (end - start).days))


def seed_products(session):
    products = []
    for name, cat, sub, cost, sell in PRODUCTS:
        p = Product(
            name=name, category=cat, sub_category=sub,
            cost_price=cost, selling_price=sell,
            stock_qty=random.randint(20, 500),
            supplier=f"{cat} Supplies Ltd"
        )
        session.add(p)
        products.append(p)
    session.commit()
    print(f"  ✅ {len(products)} products inserted")
    return products


def seed_customers(session, n=200):
    customers = []
    for i in range(n):
        region = random.choice(list(REGIONS.keys()))
        city   = random.choice(REGIONS[region])
        c = Customer(
            name=f"Customer_{i+1:03d}",
            city=city, region=region,
            segment=random.choice(SEGMENTS),
            join_date=random_date(date(2021, 1, 1), date(2023, 6, 1)),
            total_orders=0, total_spent=0.0
        )
        session.add(c)
        customers.append(c)
    session.commit()
    print(f"  ✅ {len(customers)} customers inserted")
    return customers


def seed_sales(session, n=2000):
    """
    Simulate a realistic sales drop in Odisha in Q3 2024 (Jul–Sep)
    so queries like 'sales drop in Odisha last quarter' work nicely.
    """
    sales = []
    start = date(2023, 1, 1)
    end   = date(2024, 12, 31)

    for _ in range(n):
        region  = random.choice(list(REGIONS.keys()))
        city    = random.choice(REGIONS[region])
        prod    = random.choice(PRODUCTS)
        txn_date = random_date(start, end)

        # Simulate Odisha Q3 2024 sales drop (60% volume reduction)
        is_odisha_q3 = (
            region == "Odisha" and
            txn_date.year == 2024 and
            7 <= txn_date.month <= 9
        )
        if is_odisha_q3 and random.random() < 0.60:
            continue  # drop this transaction

        qty      = random.randint(1, 15)
        discount = random.choice([0, 0, 0, 5, 10, 15, 20])
        price    = prod[4]
        revenue  = round(qty * price * (1 - discount / 100), 2)

        s = Sale(
            date=txn_date,
            region=region,
            city=city,
            product=prod[0],
            category=prod[1],
            quantity=qty,
            unit_price=price,
            revenue=revenue,
            discount_pct=discount,
            sales_rep=random.choice(SALES_REPS),
            channel=random.choice(CHANNELS)
        )
        session.add(s)
        sales.append(s)

    session.commit()
    print(f"  ✅ {len(sales)} sales records inserted (with Odisha Q3 2024 drop)")
    return sales


def seed_returns(session, sales, n=120):
    sampled = random.sample(sales, min(n, len(sales)))
    for s in sampled:
        r = Return(
            sale_id=s.id,
            return_date=s.date + timedelta(days=random.randint(1, 14)),
            reason=random.choice(RETURN_REASONS),
            refund_amount=round(s.revenue * random.uniform(0.5, 1.0), 2),
            region=s.region
        )
        session.add(r)
    session.commit()
    print(f"  ✅ {len(sampled)} returns inserted")


if __name__ == "__main__":
    print("🌱 Seeding database...")
    engine  = create_all_tables()
    session = get_session()

    products  = seed_products(session)
    customers = seed_customers(session)
    sales     = seed_sales(session)
    seed_returns(session, sales)

    session.close()
    print("\n🎉 Database ready at sample_data/sales.db")
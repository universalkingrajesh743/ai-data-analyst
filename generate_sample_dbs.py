import sqlite3
import random
from datetime import date, timedelta
import os

random.seed(42)
os.makedirs("sample_data/practice_dbs", exist_ok=True)

def random_date(start, end):
    return start + timedelta(days=random.randint(0, (end-start).days))

# ══════════════════════════════════════════════════════════════════════════════
# DB 1 — E-Commerce Store
# ══════════════════════════════════════════════════════════════════════════════
def create_ecommerce_db():
    conn = sqlite3.connect("sample_data/practice_dbs/ecommerce.db")
    c    = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY, name TEXT, email TEXT,
            city TEXT, state TEXT, signup_date TEXT, tier TEXT
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY, name TEXT, category TEXT,
            brand TEXT, price REAL, cost REAL, stock INTEGER
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY, customer_id INTEGER, order_date TEXT,
            status TEXT, total_amount REAL, payment_method TEXT,
            shipping_city TEXT, shipping_state TEXT
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY, order_id INTEGER, product_id INTEGER,
            quantity INTEGER, unit_price REAL, discount_pct REAL
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY, product_id INTEGER, customer_id INTEGER,
            rating INTEGER, review_date TEXT, helpful_votes INTEGER
        );
    """)

    states    = ["Maharashtra","Karnataka","Delhi","Tamil Nadu","Odisha","Gujarat","Rajasthan"]
    cities    = {"Maharashtra":["Mumbai","Pune","Nagpur"],"Karnataka":["Bengaluru","Mysuru"],
                 "Delhi":["New Delhi","Noida","Gurugram"],"Tamil Nadu":["Chennai","Coimbatore"],
                 "Odisha":["Bhubaneswar","Cuttack","Brahmapur"],"Gujarat":["Ahmedabad","Surat"],
                 "Rajasthan":["Jaipur","Jodhpur"]}
    tiers     = ["Bronze","Silver","Gold","Platinum"]
    payments  = ["UPI","Credit Card","Debit Card","Net Banking","COD","Wallet"]
    statuses  = ["Delivered","Shipped","Processing","Cancelled","Returned"]
    products  = [
        ("iPhone 15",     "Electronics","Apple",  89999, 72000),
        ("Samsung TV 55", "Electronics","Samsung",65000, 48000),
        ("Nike Air Max",  "Footwear",   "Nike",    8999,  4500),
        ("Levi Jeans",    "Clothing",   "Levi's",  2499,  1200),
        ("Instant Pot",   "Kitchen",    "Prestige",5999,  3200),
        ("Harry Potter",  "Books",      "Penguin",   499,   150),
        ("Yoga Mat",      "Sports",     "Decathlon",999,   450),
        ("Face Cream",    "Beauty",     "Lakme",    799,   320),
        ("Bluetooth Speaker","Electronics","boAt",  2999,  1400),
        ("Dining Table",  "Furniture",  "Nilkamal",18999, 12000),
    ]

    for i, p in enumerate(products, 1):
        c.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?)",
                  (i, p[0], p[1], p[2], p[3], p[4], random.randint(10,500)))

    for i in range(1, 301):
        state = random.choice(states)
        city  = random.choice(cities[state])
        c.execute("INSERT INTO customers VALUES (?,?,?,?,?,?,?)",
                  (i, f"Customer_{i:03d}", f"user{i}@email.com",
                   city, state,
                   random_date(date(2020,1,1), date(2023,1,1)).isoformat(),
                   random.choice(tiers)))

    order_id = 1
    for i in range(1, 1501):
        cust_id = random.randint(1, 300)
        state   = random.choice(states)
        city    = random.choice(cities[state])
        od      = random_date(date(2022,1,1), date(2024,12,31))
        total   = round(random.uniform(500, 50000), 2)
        c.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)",
                  (i, cust_id, od.isoformat(), random.choice(statuses),
                   total, random.choice(payments), city, state))

        for _ in range(random.randint(1, 4)):
            prod  = random.randint(1, 10)
            qty   = random.randint(1, 3)
            price = products[prod-1][3]
            disc  = random.choice([0,0,5,10,15,20])
            c.execute("INSERT INTO order_items VALUES (?,?,?,?,?,?)",
                      (order_id, i, prod, qty, price, disc))
            order_id += 1

    for i in range(1, 401):
        c.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?)",
                  (i, random.randint(1,10), random.randint(1,300),
                   random.randint(1,5),
                   random_date(date(2022,1,1), date(2024,12,31)).isoformat(),
                   random.randint(0, 50)))

    conn.commit()
    conn.close()
    print("✅ ecommerce.db created")


# ══════════════════════════════════════════════════════════════════════════════
# DB 2 — Hospital / Healthcare
# ══════════════════════════════════════════════════════════════════════════════
def create_hospital_db():
    conn = sqlite3.connect("sample_data/practice_dbs/hospital.db")
    c    = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY, name TEXT, age INTEGER,
            gender TEXT, blood_group TEXT, city TEXT, state TEXT,
            registration_date TEXT
        );
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY, name TEXT, specialization TEXT,
            department TEXT, experience_years INTEGER, fee REAL
        );
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY, patient_id INTEGER, doctor_id INTEGER,
            appointment_date TEXT, status TEXT, diagnosis TEXT,
            treatment TEXT, bill_amount REAL
        );
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY, name TEXT, category TEXT,
            manufacturer TEXT, price REAL, stock INTEGER
        );
        CREATE TABLE IF NOT EXISTS prescriptions (
            id INTEGER PRIMARY KEY, appointment_id INTEGER,
            medicine_id INTEGER, dosage TEXT, days INTEGER, quantity INTEGER
        );
    """)

    specializations = ["Cardiology","Neurology","Orthopedics","Pediatrics",
                       "Dermatology","General Medicine","ENT","Oncology"]
    departments     = {"Cardiology":"Heart","Neurology":"Brain","Orthopedics":"Bones",
                       "Pediatrics":"Children","Dermatology":"Skin",
                       "General Medicine":"General","ENT":"ENT","Oncology":"Cancer"}
    diagnoses       = ["Hypertension","Diabetes Type 2","Fracture","Common Cold",
                       "Pneumonia","Migraine","Arthritis","Asthma","Anemia","Dengue"]
    treatments      = ["Medication","Surgery","Physiotherapy","Observation",
                       "Chemotherapy","Lifestyle change"]
    cities          = ["Mumbai","Delhi","Bengaluru","Chennai","Hyderabad",
                       "Pune","Kolkata","Ahmedabad","Bhubaneswar","Jaipur"]
    medicines_list  = [
        ("Paracetamol","Analgesic","Sun Pharma",20,10000),
        ("Metformin","Antidiabetic","Cipla",45,5000),
        ("Amlodipine","Antihypertensive","Dr Reddy",55,3000),
        ("Azithromycin","Antibiotic","Lupin",120,2000),
        ("Omeprazole","Antacid","Torrent",38,4000),
        ("Cetirizine","Antihistamine","GSK",25,6000),
        ("Ibuprofen","NSAID","Abbott",30,8000),
        ("Vitamin D3","Supplement","Mankind",180,3500),
    ]

    for i, m in enumerate(medicines_list, 1):
        c.execute("INSERT INTO medicines VALUES (?,?,?,?,?,?)",
                  (i, m[0], m[1], m[2], m[3], m[4]))

    for i in range(1, len(specializations)+1):
        spec = specializations[i-1]
        c.execute("INSERT INTO doctors VALUES (?,?,?,?,?,?)",
                  (i, f"Dr. {['Sharma','Patel','Kumar','Singh','Reddy','Nair','Das','Iyer'][i-1]}",
                   spec, departments[spec],
                   random.randint(5, 30), random.choice([500,700,1000,1500,2000])))

    for i in range(1, 501):
        c.execute("INSERT INTO patients VALUES (?,?,?,?,?,?,?,?)",
                  (i, f"Patient_{i:03d}",
                   random.randint(5, 85),
                   random.choice(["Male","Female"]),
                   random.choice(["A+","A-","B+","B-","O+","O-","AB+","AB-"]),
                   random.choice(cities), "India",
                   random_date(date(2020,1,1), date(2023,1,1)).isoformat()))

    for i in range(1, 2001):
        c.execute("INSERT INTO appointments VALUES (?,?,?,?,?,?,?,?)",
                  (i, random.randint(1,500), random.randint(1,8),
                   random_date(date(2022,1,1), date(2024,12,31)).isoformat(),
                   random.choice(["Completed","Scheduled","Cancelled","No-show"]),
                   random.choice(diagnoses), random.choice(treatments),
                   round(random.uniform(500, 25000), 2)))

    for i in range(1, 1001):
        c.execute("INSERT INTO prescriptions VALUES (?,?,?,?,?,?)",
                  (i, random.randint(1,2000), random.randint(1,8),
                   random.choice(["1-0-1","0-0-1","1-1-1","1-0-0"]),
                   random.randint(3,30), random.randint(1,5)))

    conn.commit()
    conn.close()
    print("✅ hospital.db created")


# ══════════════════════════════════════════════════════════════════════════════
# DB 3 — School / Education
# ══════════════════════════════════════════════════════════════════════════════
def create_school_db():
    conn = sqlite3.connect("sample_data/practice_dbs/school.db")
    c    = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY, name TEXT, age INTEGER,
            gender TEXT, class_grade TEXT, section TEXT,
            city TEXT, admission_date TEXT, fee_paid REAL
        );
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY, name TEXT, subject TEXT,
            qualification TEXT, experience_years INTEGER, salary REAL
        );
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY, name TEXT, class_grade TEXT,
            max_marks INTEGER, passing_marks INTEGER
        );
        CREATE TABLE IF NOT EXISTS exam_results (
            id INTEGER PRIMARY KEY, student_id INTEGER,
            subject_id INTEGER, exam_type TEXT,
            marks_obtained INTEGER, exam_date TEXT, grade TEXT
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY, student_id INTEGER,
            attendance_date TEXT, status TEXT, reason TEXT
        );
        CREATE TABLE IF NOT EXISTS fees (
            id INTEGER PRIMARY KEY, student_id INTEGER,
            amount REAL, fee_type TEXT, payment_date TEXT, status TEXT
        );
    """)

    grades   = ["6","7","8","9","10","11","12"]
    sections = ["A","B","C"]
    subjects_list = [
        ("Mathematics","10",100,35), ("Science","10",100,35),
        ("English","10",100,35),     ("Hindi","10",100,35),
        ("Social Science","10",100,35), ("Physics","12",100,35),
        ("Chemistry","12",100,35),   ("Biology","12",100,35),
        ("Mathematics","12",100,35), ("Computer Science","12",100,35),
    ]
    teachers_list = [
        ("Mr. Sharma",    "Mathematics",   "M.Sc",  15, 55000),
        ("Mrs. Patel",    "Science",       "M.Sc",  10, 50000),
        ("Ms. Verma",     "English",       "M.A",   8,  45000),
        ("Mr. Kumar",     "Hindi",         "M.A",   12, 48000),
        ("Mrs. Singh",    "Social Science","M.A",   6,  42000),
        ("Mr. Reddy",     "Physics",       "M.Tech",20, 65000),
        ("Ms. Nair",      "Chemistry",     "M.Sc",  14, 58000),
        ("Dr. Iyer",      "Biology",       "Ph.D",  18, 70000),
        ("Mr. Das",       "Computer Sci",  "MCA",   9,  52000),
    ]
    fee_types    = ["Tuition","Transport","Library","Sports","Exam"]
    exam_types   = ["Unit Test 1","Unit Test 2","Mid Term","Final Exam"]
    att_statuses = ["Present","Absent","Late"]

    for i, s in enumerate(subjects_list, 1):
        c.execute("INSERT INTO subjects VALUES (?,?,?,?,?)", (i,)+s)

    for i, t in enumerate(teachers_list, 1):
        c.execute("INSERT INTO teachers VALUES (?,?,?,?,?,?)", (i,)+t)

    for i in range(1, 401):
        grade = random.choice(grades)
        c.execute("INSERT INTO students VALUES (?,?,?,?,?,?,?,?,?)",
                  (i, f"Student_{i:03d}", random.randint(11,18),
                   random.choice(["Male","Female"]),
                   grade, random.choice(sections),
                   random.choice(["Delhi","Mumbai","Chennai","Bengaluru","Hyderabad"]),
                   random_date(date(2018,4,1), date(2023,4,1)).isoformat(),
                   random.choice([40000,50000,60000,75000])))

    for i in range(1, 3001):
        c.execute("INSERT INTO exam_results VALUES (?,?,?,?,?,?,?)",
                  (i, random.randint(1,400), random.randint(1,10),
                   random.choice(exam_types),
                   random.randint(25,100),
                   random_date(date(2023,4,1), date(2024,3,31)).isoformat(),
                   random.choice(["A+","A","B+","B","C","D","F"])))

    for i in range(1, 5001):
        c.execute("INSERT INTO attendance VALUES (?,?,?,?,?)",
                  (i, random.randint(1,400),
                   random_date(date(2024,1,1), date(2024,12,31)).isoformat(),
                   random.choice(att_statuses),
                   random.choice(["","","","Sick","Family function","Holiday"])))

    for i in range(1, 1201):
        c.execute("INSERT INTO fees VALUES (?,?,?,?,?,?)",
                  (i, random.randint(1,400),
                   random.choice([5000,8000,10000,15000,20000]),
                   random.choice(fee_types),
                   random_date(date(2024,1,1), date(2024,12,31)).isoformat(),
                   random.choice(["Paid","Paid","Paid","Pending","Overdue"])))

    conn.commit()
    conn.close()
    print("✅ school.db created")


# ══════════════════════════════════════════════════════════════════════════════
# DB 4 — Restaurant Chain
# ══════════════════════════════════════════════════════════════════════════════
def create_restaurant_db():
    conn = sqlite3.connect("sample_data/practice_dbs/restaurant.db")
    c    = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS branches (
            id INTEGER PRIMARY KEY, name TEXT, city TEXT,
            state TEXT, opening_date TEXT, seating_capacity INTEGER,
            manager TEXT
        );
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY, name TEXT, category TEXT,
            cuisine TEXT, price REAL, cost REAL, is_veg INTEGER,
            is_available INTEGER
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY, branch_id INTEGER,
            order_date TEXT, order_time TEXT, order_type TEXT,
            total_amount REAL, payment_method TEXT,
            table_number INTEGER, waiter TEXT
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY, order_id INTEGER,
            item_id INTEGER, quantity INTEGER,
            unit_price REAL, special_request TEXT
        );
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY, name TEXT, role TEXT,
            branch_id INTEGER, join_date TEXT, salary REAL
        );
        CREATE TABLE IF NOT EXISTS customer_feedback (
            id INTEGER PRIMARY KEY, branch_id INTEGER,
            order_id INTEGER, food_rating INTEGER,
            service_rating INTEGER, ambience_rating INTEGER,
            feedback_date TEXT, comment TEXT
        );
    """)

    branches_list = [
        ("Spice Garden Connaught Place","New Delhi","Delhi","2018-03-15",120,"Rajesh Sharma"),
        ("Spice Garden Bandra","Mumbai","Maharashtra","2019-06-20",90,"Priya Patel"),
        ("Spice Garden Koramangala","Bengaluru","Karnataka","2020-01-10",100,"Suresh Kumar"),
        ("Spice Garden T Nagar","Chennai","Tamil Nadu","2021-04-05",80,"Meena Iyer"),
        ("Spice Garden Salt Lake","Kolkata","West Bengal","2022-02-14",70,"Arnab Das"),
    ]
    menu_list = [
        ("Butter Chicken",  "Main Course","North Indian",380,120,0,1),
        ("Paneer Tikka",    "Starter",    "North Indian",280, 80,1,1),
        ("Masala Dosa",     "Breakfast",  "South Indian",180, 50,1,1),
        ("Biryani Chicken", "Main Course","Hyderabadi",  420,130,0,1),
        ("Gulab Jamun",     "Dessert",    "Indian",       90, 25,1,1),
        ("Veg Fried Rice",  "Main Course","Chinese",     220, 65,1,1),
        ("Chicken Noodles", "Main Course","Chinese",     280, 85,0,1),
        ("Caesar Salad",    "Starter",    "Continental", 240, 70,1,1),
        ("Mango Lassi",     "Beverages",  "Indian",      120, 30,1,1),
        ("Cold Coffee",     "Beverages",  "Continental", 150, 40,1,1),
        ("Fish Curry",      "Main Course","Coastal",     360,110,0,1),
        ("Palak Paneer",    "Main Course","North Indian",320, 90,1,1),
    ]
    order_types  = ["Dine-in","Takeaway","Delivery","Online"]
    payments     = ["Cash","Card","UPI","Wallet","Online"]
    roles        = ["Chef","Waiter","Manager","Cashier","Cleaner","Security"]
    waiters      = ["Amit","Priya","Ravi","Sunita","Mohit","Kavya","Deepak"]

    for i, b in enumerate(branches_list, 1):
        c.execute("INSERT INTO branches VALUES (?,?,?,?,?,?,?)", (i,)+b)

    for i, m in enumerate(menu_list, 1):
        c.execute("INSERT INTO menu_items VALUES (?,?,?,?,?,?,?,?)", (i,)+m)

    for i in range(1, 61):
        c.execute("INSERT INTO staff VALUES (?,?,?,?,?,?)",
                  (i, f"Staff_{i:02d}", random.choice(roles),
                   random.randint(1,5),
                   random_date(date(2018,1,1), date(2023,1,1)).isoformat(),
                   random.choice([18000,22000,28000,35000,45000,55000])))

    item_id = 1
    for i in range(1, 3001):
        branch = random.randint(1,5)
        od     = random_date(date(2022,1,1), date(2024,12,31))
        total  = round(random.uniform(200, 3000), 2)
        c.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)",
                  (i, branch, od.isoformat(),
                   f"{random.randint(11,23):02d}:{random.randint(0,59):02d}",
                   random.choice(order_types), total,
                   random.choice(payments),
                   random.randint(1,20), random.choice(waiters)))

        for _ in range(random.randint(1,5)):
            menu_item = random.randint(1,12)
            qty       = random.randint(1,3)
            price     = menu_list[menu_item-1][4]
            c.execute("INSERT INTO order_items VALUES (?,?,?,?,?,?)",
                      (item_id, i, menu_item, qty, price,
                       random.choice(["","","Extra spicy","Less oil","No onion"])))
            item_id += 1

    for i in range(1, 1001):
        c.execute("INSERT INTO customer_feedback VALUES (?,?,?,?,?,?,?,?)",
                  (i, random.randint(1,5), random.randint(1,3000),
                   random.randint(1,5), random.randint(1,5), random.randint(1,5),
                   random_date(date(2022,1,1), date(2024,12,31)).isoformat(),
                   random.choice(["Great food!","Average service","Will come again",
                                  "Too spicy","Loved it","Long wait time","Excellent!",""])))

    conn.commit()
    conn.close()
    print("✅ restaurant.db created")


# ══════════════════════════════════════════════════════════════════════════════
# DB 5 — HR / Employee Management
# ══════════════════════════════════════════════════════════════════════════════
def create_hr_db():
    conn = sqlite3.connect("sample_data/practice_dbs/hr.db")
    c    = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY, name TEXT, email TEXT,
            department TEXT, designation TEXT, level TEXT,
            city TEXT, join_date TEXT, salary REAL,
            manager_id INTEGER, status TEXT
        );
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY, name TEXT, head_id INTEGER,
            budget REAL, location TEXT
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY, employee_id INTEGER,
            attendance_date TEXT, check_in TEXT,
            check_out TEXT, status TEXT, hours_worked REAL
        );
        CREATE TABLE IF NOT EXISTS performance (
            id INTEGER PRIMARY KEY, employee_id INTEGER,
            review_year INTEGER, review_quarter INTEGER,
            rating REAL, kpi_score REAL, reviewer_id INTEGER,
            promotion_recommended INTEGER
        );
        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY, employee_id INTEGER,
            leave_type TEXT, start_date TEXT, end_date TEXT,
            days_taken INTEGER, status TEXT, reason TEXT
        );
        CREATE TABLE IF NOT EXISTS payroll (
            id INTEGER PRIMARY KEY, employee_id INTEGER,
            month TEXT, basic_salary REAL, hra REAL,
            allowances REAL, deductions REAL, net_salary REAL
        );
    """)

    depts = [
        (1,"Engineering",   None, 5000000,"Bengaluru"),
        (2,"Sales",         None, 3000000,"Mumbai"),
        (3,"Marketing",     None, 2000000,"Delhi"),
        (4,"HR",            None, 1500000,"Bengaluru"),
        (5,"Finance",       None, 2500000,"Mumbai"),
        (6,"Operations",    None, 2000000,"Hyderabad"),
        (7,"Data Science",  None, 3500000,"Bengaluru"),
    ]
    for d in depts:
        c.execute("INSERT INTO departments VALUES (?,?,?,?,?)", d)

    designations = {
        "Engineering":  ["Junior Dev","Senior Dev","Lead Dev","Architect","VP Engineering"],
        "Sales":        ["Sales Exec","Senior Sales","Sales Manager","Regional Head","VP Sales"],
        "Marketing":    ["Marketing Exec","Senior Marketer","Manager","Director","VP Marketing"],
        "HR":           ["HR Exec","Senior HR","HR Manager","HR Director","CHRO"],
        "Finance":      ["Finance Analyst","Senior Analyst","Manager","Director","CFO"],
        "Operations":   ["Ops Exec","Senior Ops","Ops Manager","Director","COO"],
        "Data Science": ["Data Analyst","Senior Analyst","Data Scientist","Lead DS","VP Data"],
    }
    levels       = ["L1","L2","L3","L4","L5"]
    cities       = ["Bengaluru","Mumbai","Delhi","Hyderabad","Chennai","Pune"]
    leave_types  = ["Sick Leave","Casual Leave","Earned Leave","Maternity","Paternity"]
    statuses_att = ["Present","Absent","Half Day","Work From Home","Holiday"]

    dept_names = [d[1] for d in depts]
    for i in range(1, 201):
        dept  = random.choice(dept_names)
        level = random.randint(0,4)
        desig = designations[dept][level]
        sal   = [400000,700000,1200000,2000000,4000000][level] * random.uniform(0.9,1.1)
        c.execute("INSERT INTO employees VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (i, f"Employee_{i:03d}", f"emp{i}@company.com",
                   dept, desig, levels[level],
                   random.choice(cities),
                   random_date(date(2015,1,1), date(2023,6,1)).isoformat(),
                   round(sal/12, 2),
                   random.randint(1, min(i, 50)) if i > 1 else None,
                   random.choice(["Active","Active","Active","Resigned","On Leave"])))

    for i in range(1, 3001):
        emp_id = random.randint(1,200)
        sal    = random.uniform(30000, 350000)
        hra    = sal * 0.4
        allow  = sal * 0.2
        deduct = sal * 0.12
        c.execute("INSERT INTO attendance VALUES (?,?,?,?,?,?,?)",
                  (i, emp_id,
                   random_date(date(2024,1,1), date(2024,12,31)).isoformat(),
                   f"{random.randint(8,10):02d}:{random.randint(0,59):02d}",
                   f"{random.randint(17,20):02d}:{random.randint(0,59):02d}",
                   random.choice(statuses_att),
                   round(random.uniform(6,10), 1)))

        c.execute("INSERT INTO payroll VALUES (?,?,?,?,?,?,?,?)",
                  (i, emp_id,
                   f"2024-{random.randint(1,12):02d}",
                   round(sal,2), round(hra,2),
                   round(allow,2), round(deduct,2),
                   round(sal+hra+allow-deduct, 2)))

    for i in range(1, 801):
        c.execute("INSERT INTO performance VALUES (?,?,?,?,?,?,?,?)",
                  (i, random.randint(1,200),
                   random.randint(2021,2024), random.randint(1,4),
                   round(random.uniform(1,5), 1),
                   round(random.uniform(50,100), 1),
                   random.randint(1,50),
                   random.randint(0,1)))

    for i in range(1, 601):
        start = random_date(date(2024,1,1), date(2024,11,1))
        days  = random.randint(1,15)
        end   = start + timedelta(days=days)
        c.execute("INSERT INTO leaves VALUES (?,?,?,?,?,?,?,?)",
                  (i, random.randint(1,200),
                   random.choice(leave_types),
                   start.isoformat(), end.isoformat(), days,
                   random.choice(["Approved","Approved","Approved","Pending","Rejected"]),
                   random.choice(["Medical","Personal","Vacation","Family","Other"])))

    conn.commit()
    conn.close()
    print("✅ hr.db created")


# ══════════════════════════════════════════════════════════════════════════════
# DB 6 — Stock Market / Finance
# ══════════════════════════════════════════════════════════════════════════════
def create_stockmarket_db():
    conn = sqlite3.connect("sample_data/practice_dbs/stockmarket.db")
    c    = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY, symbol TEXT, name TEXT,
            sector TEXT, market_cap_cr REAL, exchange TEXT,
            founded_year INTEGER
        );
        CREATE TABLE IF NOT EXISTS stock_prices (
            id INTEGER PRIMARY KEY, company_id INTEGER,
            trade_date TEXT, open_price REAL, high_price REAL,
            low_price REAL, close_price REAL, volume INTEGER,
            adj_close REAL
        );
        CREATE TABLE IF NOT EXISTS portfolios (
            id INTEGER PRIMARY KEY, investor_name TEXT,
            risk_profile TEXT, created_date TEXT, total_invested REAL
        );
        CREATE TABLE IF NOT EXISTS holdings (
            id INTEGER PRIMARY KEY, portfolio_id INTEGER,
            company_id INTEGER, quantity INTEGER,
            avg_buy_price REAL, buy_date TEXT
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY, portfolio_id INTEGER,
            company_id INTEGER, transaction_type TEXT,
            quantity INTEGER, price REAL,
            transaction_date TEXT, brokerage REAL
        );
        CREATE TABLE IF NOT EXISTS dividends (
            id INTEGER PRIMARY KEY, company_id INTEGER,
            dividend_date TEXT, amount_per_share REAL,
            dividend_type TEXT
        );
    """)

    companies_list = [
        ("RELIANCE","Reliance Industries","Energy",           1800000,"NSE",1966),
        ("TCS",     "Tata Consultancy",   "IT",               1500000,"NSE",1968),
        ("HDFCBANK","HDFC Bank",          "Banking",          1100000,"NSE",1994),
        ("INFY",    "Infosys",            "IT",                700000,"NSE",1981),
        ("HINDUNILVR","Hindustan Unilever","FMCG",             600000,"NSE",1933),
        ("ICICIBANK","ICICI Bank",        "Banking",           750000,"NSE",1994),
        ("KOTAKBANK","Kotak Mahindra",    "Banking",           380000,"NSE",1985),
        ("WIPRO",   "Wipro Ltd",          "IT",                280000,"NSE",1945),
        ("AXISBANK","Axis Bank",          "Banking",           320000,"NSE",1993),
        ("BAJFINANCE","Bajaj Finance",    "NBFC",              450000,"NSE",1987),
    ]
    risk_profiles = ["Conservative","Moderate","Aggressive"]
    txn_types     = ["BUY","SELL"]
    div_types     = ["Interim","Final","Special"]

    for i, co in enumerate(companies_list, 1):
        c.execute("INSERT INTO companies VALUES (?,?,?,?,?,?,?)", (i,)+co)

    price_id = 1
    base_prices = [2400, 3500, 1600, 1400, 2600, 950, 1750, 450, 1050, 6800]
    for company_id in range(1, 11):
        price = base_prices[company_id-1]
        start = date(2022, 1, 1)
        for d in range(0, 730, 1):
            trade_date = start + timedelta(days=d)
            if trade_date.weekday() >= 5:
                continue
            change = price * random.uniform(-0.03, 0.03)
            price  = max(100, price + change)
            high   = price * random.uniform(1.0, 1.02)
            low    = price * random.uniform(0.98, 1.0)
            c.execute("INSERT INTO stock_prices VALUES (?,?,?,?,?,?,?,?,?)",
                      (price_id, company_id, trade_date.isoformat(),
                       round(price*0.99,2), round(high,2), round(low,2),
                       round(price,2), random.randint(100000,5000000),
                       round(price,2)))
            price_id += 1

    for i in range(1, 101):
        c.execute("INSERT INTO portfolios VALUES (?,?,?,?,?)",
                  (i, f"Investor_{i:03d}", random.choice(risk_profiles),
                   random_date(date(2020,1,1), date(2023,1,1)).isoformat(),
                   round(random.uniform(100000, 5000000), 2)))

    for i in range(1, 501):
        c.execute("INSERT INTO holdings VALUES (?,?,?,?,?,?)",
                  (i, random.randint(1,100), random.randint(1,10),
                   random.randint(1,500),
                   round(random.uniform(500,5000),2),
                   random_date(date(2020,1,1), date(2023,12,31)).isoformat()))

    for i in range(1, 2001):
        price = round(random.uniform(400, 7000), 2)
        c.execute("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)",
                  (i, random.randint(1,100), random.randint(1,10),
                   random.choice(txn_types),
                   random.randint(1,200), price,
                   random_date(date(2022,1,1), date(2024,12,31)).isoformat(),
                   round(price * random.randint(1,200) * 0.0003, 2)))

    for i in range(1, 81):
        c.execute("INSERT INTO dividends VALUES (?,?,?,?,?)",
                  (i, random.randint(1,10),
                   random_date(date(2022,1,1), date(2024,12,31)).isoformat(),
                   round(random.uniform(2,50), 2),
                   random.choice(div_types)))

    conn.commit()
    conn.close()
    print("✅ stockmarket.db created")


# ══════════════════════════════════════════════════════════════════════════════
# Run all
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("🔨 Generating sample databases...\n")
    create_ecommerce_db()
    create_hospital_db()
    create_school_db()
    create_restaurant_db()
    create_hr_db()
    create_stockmarket_db()
    print(f"\n✅ All 6 databases created in sample_data/practice_dbs/")
    print("\nDatabases ready to upload in your AI BI Copilot:")
    print("  1. ecommerce.db    — Orders, products, customers, reviews")
    print("  2. hospital.db     — Patients, doctors, appointments, prescriptions")
    print("  3. school.db       — Students, teachers, exams, attendance, fees")
    print("  4. restaurant.db   — Branches, menu, orders, staff, feedback")
    print("  5. hr.db           — Employees, payroll, performance, leaves")
    print("  6. stockmarket.db  — Companies, prices, portfolios, transactions")
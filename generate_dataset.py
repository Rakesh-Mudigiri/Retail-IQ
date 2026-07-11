"""
Generates a realistic retail sales dataset (sales.csv) for RetailIQ.
Includes intentional missing values and duplicates for ETL pipeline testing.
"""

import pandas as pd
import numpy as np
from faker import Faker
import random
import os

fake = Faker()

def generate_retail_data(num_records=1050): # 1050 to allow some duplicates
    data = []
    
    categories = ['Electronics', 'Clothing', 'Home & Kitchen', 'Beauty', 'Sports']
    payments = ['Credit Card', 'Debit Card', 'UPI', 'Net Banking', 'Cash']
    
    # Pre-generate some products
    products = []
    for _ in range(50):
        cat = random.choice(categories)
        products.append({
            'Product ID': f"PROD-{fake.unique.random_int(min=1000, max=9999)}",
            'Product Name': fake.word().capitalize() + " " + cat.split()[0],
            'Category': cat,
            'Unit Price': round(random.uniform(10.0, 500.0), 2)
        })

    # Pre-generate some customers
    customers = []
    for _ in range(200):
        customers.append({
            'Customer ID': f"CUST-{fake.unique.random_int(min=10000, max=99999)}",
            'Customer Name': fake.name(),
            'City': fake.city(),
            'State': fake.state()
        })

    for i in range(num_records):
        cust = random.choice(customers)
        prod = random.choice(products)
        
        order_id = f"ORD-{fake.unique.random_int(min=100000, max=999999)}"
        order_date = fake.date_between(start_date='-2y', end_date='today')
        quantity = random.randint(1, 10)
        discount = round(random.uniform(0, 0.3), 2)  # up to 30% discount
        
        # Calculate derived metrics
        gross_total = quantity * prod['Unit Price']
        total_price = round(gross_total * (1 - discount), 2)
        profit = round(total_price * random.uniform(0.1, 0.4), 2) # 10-40% margin
        
        record = {
            'Order ID': order_id,
            'Order Date': order_date,
            'Customer ID': cust['Customer ID'],
            'Customer Name': cust['Customer Name'],
            'Product ID': prod['Product ID'],
            'Product Name': prod['Product Name'],
            'Category': prod['Category'],
            'Quantity': quantity,
            'Unit Price': prod['Unit Price'],
            'Discount': discount,
            'Total Price': total_price,
            'Payment Method': random.choice(payments),
            'City': cust['City'],
            'State': cust['State'],
            'Profit': profit
        }
        
        # Introduce some missing data intentionally for ETL validation
        if random.random() < 0.02:
            record['Quantity'] = np.nan
        if random.random() < 0.02:
            record['Payment Method'] = np.nan
            
        data.append(record)

    df = pd.DataFrame(data)
    
    # Introduce duplicates (approx 50)
    duplicates = df.sample(n=50)
    df = pd.concat([df, duplicates], ignore_index=True)
    
    # Shuffle dataset
    df = df.sample(frac=1).reset_index(drop=True)
    
    # Save to CSV
    os.makedirs('dataset', exist_ok=True)
    file_path = os.path.join('dataset', 'sales.csv')
    df.to_csv(file_path, index=False)
    print(f"Dataset generated successfully at {file_path} with {len(df)} records.")

if __name__ == '__main__':
    generate_retail_data()

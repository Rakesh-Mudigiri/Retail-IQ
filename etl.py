"""
ETL Pipeline for RetailIQ.
Extracts data from CSV, transforms/cleans it, and loads into MySQL.
Now fully isolated via admin_id for Multi-Tenant SaaS.
"""

import pandas as pd
import numpy as np
import os
from database import Database
from utils import logger, handle_exception
import datetime

class ETLPipeline:
    def __init__(self, file_path, admin_id):
        self.file_path = file_path
        self.admin_id = admin_id
        self.df = None

    def extract(self):
        """Reads CSV file into Pandas DataFrame."""
        try:
            logger.info(f"Extracting data from {self.file_path}")
            self.df = pd.read_csv(self.file_path)
            return True
        except Exception as e:
            handle_exception(e, "Extraction Failed")
            return False

    def transform(self):
        """Cleans and processes the data."""
        try:
            logger.info("Starting Data Transformation")
            
            initial_rows = len(self.df)
            
            # 1. Remove duplicates based on Order ID
            self.df.drop_duplicates(subset=['Order ID'], keep='first', inplace=True)
            logger.info(f"Removed duplicates. Row count: {len(self.df)}")
            
            # 2. Handle missing values
            # Fill missing Payment Methods with 'Unknown'
            self.df['Payment Method'].fillna('Unknown', inplace=True)
            
            # Fill missing Quantities with 1 (default)
            self.df['Quantity'].fillna(1, inplace=True)
            
            # 3. Remove rows with critical missing values
            self.df.dropna(subset=['Order ID', 'Customer ID', 'Product ID'], inplace=True)
            
            # 4. Convert Date Formats
            self.df['Order Date'] = pd.to_datetime(self.df['Order Date']).dt.strftime('%Y-%m-%d')
            
            # 5. Clean / Validate Numeric fields
            numeric_cols = ['Quantity', 'Unit Price', 'Discount', 'Total Price', 'Profit']
            for col in numeric_cols:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
                
            # Filter out negative quantities or prices
            self.df = self.df[(self.df['Quantity'] > 0) & (self.df['Unit Price'] >= 0)]
            
            # 6. Generate Total Price
            self.df['Total Price'] = round((self.df['Quantity'] * self.df['Unit Price']) * (1 - self.df['Discount']), 2)
            
            # 7. Standardize Strings
            string_cols = ['Customer Name', 'City', 'State', 'Product Name', 'Category', 'Payment Method']
            for col in string_cols:
                self.df[col] = self.df[col].astype(str).str.strip()

            logger.info(f"Transformation complete. Rows retained: {len(self.df)} / {initial_rows}")
            return True
            
        except Exception as e:
            handle_exception(e, "Transformation Failed")
            return False

    def _load_categories(self):
        """Loads unique categories into DB scoped by admin_id."""
        categories = self.df['Category'].unique()
        for cat in categories:
            query = "INSERT IGNORE INTO categories (admin_id, category_name) VALUES (%s, %s)"
            Database.execute_query(query, (self.admin_id, cat))
        
        # Fetch mappings
        db_cats = Database.execute_query("SELECT category_id, category_name FROM categories WHERE admin_id = %s", (self.admin_id,), fetch=True)
        return {row['category_name']: row['category_id'] for row in db_cats} if db_cats else {}

    def _load_payments(self):
        """Loads unique payments into DB scoped by admin_id."""
        payments = self.df['Payment Method'].unique()
        for pay in payments:
            query = "INSERT IGNORE INTO payments (admin_id, payment_method) VALUES (%s, %s)"
            Database.execute_query(query, (self.admin_id, pay))
            
        db_pays = Database.execute_query("SELECT payment_id, payment_method FROM payments WHERE admin_id = %s", (self.admin_id,), fetch=True)
        return {row['payment_method']: row['payment_id'] for row in db_pays} if db_pays else {}

    def _load_customers(self):
        """Loads customers scoped by admin_id."""
        cust_df = self.df[['Customer ID', 'Customer Name', 'City', 'State']].drop_duplicates().copy()
        cust_df.insert(0, 'admin_id', self.admin_id)
        
        query = """
            INSERT IGNORE INTO customers (admin_id, customer_id, customer_name, city, state)
            VALUES (%s, %s, %s, %s, %s)
        """
        params = list(cust_df.itertuples(index=False, name=None))
        Database.insert_many(query, params)

    def _load_products(self, category_map):
        """Loads products scoped by admin_id."""
        prod_df = self.df[['Product ID', 'Product Name', 'Category', 'Unit Price']].drop_duplicates().copy()
        prod_df['category_id'] = prod_df['Category'].map(category_map)
        
        prod_df = prod_df[['Product ID', 'Product Name', 'category_id', 'Unit Price']]
        prod_df.insert(0, 'admin_id', self.admin_id)
        
        query = """
            INSERT IGNORE INTO products (admin_id, product_id, product_name, category_id, unit_price)
            VALUES (%s, %s, %s, %s, %s)
        """
        params = list(prod_df.itertuples(index=False, name=None))
        Database.insert_many(query, params)

    def _load_sales(self, payment_map):
        """Loads sales records scoped by admin_id."""
        self.df['payment_id'] = self.df['Payment Method'].map(payment_map)
        
        sales_df = self.df[[
            'Order ID', 'Order Date', 'Customer ID', 'Product ID', 'payment_id',
            'Quantity', 'Discount', 'Total Price', 'Profit'
        ]].copy()
        
        sales_df.insert(0, 'admin_id', self.admin_id)
        
        query = """
            INSERT IGNORE INTO sales 
            (admin_id, order_id, order_date, customer_id, product_id, payment_id, quantity, discount, total_price, profit)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = list(sales_df.itertuples(index=False, name=None))
        
        chunk_size = 500
        total_inserted = 0
        for i in range(0, len(params), chunk_size):
            chunk = params[i:i+chunk_size]
            inserted = Database.insert_many(query, chunk)
            total_inserted += inserted
            
        logger.info(f"Loaded {total_inserted} sales records into database for Admin {self.admin_id}.")

    def load(self):
        """Loads transformed data into MySQL Database."""
        try:
            logger.info(f"Starting Data Load for Admin ID {self.admin_id}")
            
            # Delete ONLY the data belonging to this specific admin!
            logger.info("Clearing old data for this user...")
            Database.execute_query("DELETE FROM sales WHERE admin_id = %s", (self.admin_id,))
            Database.execute_query("DELETE FROM products WHERE admin_id = %s", (self.admin_id,))
            Database.execute_query("DELETE FROM customers WHERE admin_id = %s", (self.admin_id,))
            Database.execute_query("DELETE FROM categories WHERE admin_id = %s", (self.admin_id,))
            Database.execute_query("DELETE FROM payments WHERE admin_id = %s", (self.admin_id,))
            
            # Load dimension tables
            cat_map = self._load_categories()
            pay_map = self._load_payments()
            self._load_customers()
            self._load_products(cat_map)
            
            # Load fact table
            self._load_sales(pay_map)
            
            logger.info("Data Load completed successfully.")
            return True
        except Exception as e:
            handle_exception(e, "Load Failed")
            return False

    def run_pipeline(self):
        """Executes the full ETL pipeline."""
        if self.extract():
            if self.transform():
                if self.load():
                    return True
        return False

if __name__ == '__main__':
    # Test script: Requires a dummy admin_id for testing
    pipeline = ETLPipeline(os.path.join('dataset', 'sales.csv'), admin_id=1)
    pipeline.run_pipeline()

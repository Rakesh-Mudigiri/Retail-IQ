"""
RetailIQ - Main Flask Application.
Contains routes for Dashboard, Analytics, Uploads, and Predictions.
Upgraded to Multi-Tenant SaaS Architecture.
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, abort
import os
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import traceback
from config import Config
from database import Database
from etl import ETLPipeline
from utils import setup_logger, validate_csv_extension, format_currency, get_currency_symbol

# Initialize Flask App
app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = 'super_secret_retailiq_key_123'

# Register Jinja Filter
app.jinja_env.filters['currency'] = format_currency

@app.context_processor
def inject_currency():
    return dict(currency_symbol=get_currency_symbol())

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Initialize Logger
logger = setup_logger()

# Initialize Database Pool on startup
Database.initialize_pool()

@app.route('/')
def home():
    """Renders the Home page."""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles User Login."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = Database.execute_query("SELECT * FROM admins WHERE username = %s", (email,), fetch=True, fetch_all=False)
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['admin_id']
            session['email'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    """Handles User Registration."""
    email = request.form.get('email')
    password = request.form.get('password')
    
    existing = Database.execute_query("SELECT * FROM admins WHERE username = %s", (email,), fetch=True, fetch_all=False)
    if existing:
        flash('Email already registered. Please log in.', 'warning')
        return redirect(url_for('login'))
        
    hashed_pw = generate_password_hash(password)
    Database.execute_query("INSERT INTO admins (username, password_hash) VALUES (%s, %s)", (email, hashed_pw))
    flash('Registration successful! You can now log in.', 'success')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    """Handles User Logout."""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Renders the Dashboard with high-level metrics scoped by admin_id."""
    admin_id = session['user_id']
    try:
        revenue = Database.execute_query("SELECT COALESCE(SUM(total_price), 0) as total FROM sales WHERE admin_id=%s", (admin_id,), fetch=True, fetch_all=False)
        orders = Database.execute_query("SELECT COUNT(order_id) as total FROM sales WHERE admin_id=%s", (admin_id,), fetch=True, fetch_all=False)
        customers = Database.execute_query("SELECT COUNT(DISTINCT customer_id) as total FROM customers WHERE admin_id=%s", (admin_id,), fetch=True, fetch_all=False)
        products = Database.execute_query("SELECT COUNT(DISTINCT product_id) as total FROM products WHERE admin_id=%s", (admin_id,), fetch=True, fetch_all=False)
        profit = Database.execute_query("SELECT COALESCE(SUM(profit), 0) as total FROM sales WHERE admin_id=%s", (admin_id,), fetch=True, fetch_all=False)
        
        rev = float(revenue['total']) if revenue and revenue['total'] else 0
        ord_count = int(orders['total']) if orders and orders['total'] else 0
        
        metrics = {
            'revenue': rev,
            'orders': ord_count,
            'customers': int(customers['total']) if customers and customers['total'] else 0,
            'products': int(products['total']) if products and products['total'] else 0,
            'avg_order': rev / ord_count if ord_count > 0 else 0,
            'profit': float(profit['total']) if profit and profit['total'] else 0
        }
        return render_template('dashboard.html', metrics=metrics)
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        flash('Error loading dashboard data.', 'danger')
        return render_template('dashboard.html', metrics={'revenue': 0, 'orders': 0, 'customers': 0, 'products': 0, 'avg_order': 0, 'profit': 0})

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Handles CSV file upload and triggers ETL pipeline."""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part in the request.', 'danger')
            return redirect(request.url)
            
        file = request.files['file']
        
        if file.filename == '':
            flash('No file selected for uploading.', 'warning')
            return redirect(request.url)
            
        if file and validate_csv_extension(file.filename):
            filename = secure_filename(file.filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            logger.info(f"File {filename} uploaded successfully. Starting ETL.")
            
            # Pass admin_id to ETL Pipeline
            pipeline = ETLPipeline(file_path, session['user_id'])
            if pipeline.run_pipeline():
                flash('File successfully processed and your isolated data loaded to database!', 'success')
            else:
                flash('ETL Pipeline encountered an error. Check logs.', 'danger')
                
            return redirect(url_for('dashboard'))
        else:
            flash('Allowed file type is CSV only.', 'danger')
            
    return render_template('upload.html')

@app.route('/analytics')
@login_required
def analytics():
    """Renders the Analytics page."""
    return render_template('analytics.html')

@app.route('/products')
@login_required
def products():
    """Renders the Products data view scoped by admin_id."""
    admin_id = session['user_id']
    try:
        query = """
            SELECT p.product_id, p.product_name, c.category_name, 
                   COALESCE(SUM(s.quantity), 0) as total_quantity, 
                   COALESCE(SUM(s.total_price), 0) as total_revenue
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.category_id
            LEFT JOIN sales s ON p.admin_id = s.admin_id AND p.product_id = s.product_id
            WHERE p.admin_id = %s
            GROUP BY p.product_id, p.product_name, c.category_name
            ORDER BY total_revenue DESC
        """
        all_products = Database.execute_query(query, (admin_id,), fetch=True)
        
        top_product = all_products[0] if all_products and all_products[0]['total_revenue'] > 0 else None
        least_product = None
        if all_products:
            for p in reversed(all_products):
                if p['total_revenue'] > 0:
                    least_product = p
                    break
            if not least_product:
                least_product = all_products[-1]
                
        return render_template('products.html', products=all_products, top=top_product, least=least_product)
    except Exception as e:
        logger.error(f"Error loading products page: {e}")
        return render_template('products.html', products=[], top=None, least=None)

@app.route('/customers')
@login_required
def customers():
    """Renders the Customers data view scoped by admin_id."""
    admin_id = session['user_id']
    try:
        query = """
            SELECT c.customer_id, c.customer_name, c.city, 
                   COUNT(s.order_id) as total_orders, 
                   COALESCE(SUM(s.total_price), 0) as total_spent
            FROM customers c
            LEFT JOIN sales s ON c.admin_id = s.admin_id AND c.customer_id = s.customer_id
            WHERE c.admin_id = %s
            GROUP BY c.customer_id, c.customer_name, c.city
            ORDER BY total_spent DESC
        """
        all_customers = Database.execute_query(query, (admin_id,), fetch=True)
        
        top_customer = all_customers[0] if all_customers and all_customers[0]['total_spent'] > 0 else None
        
        avg_query = "SELECT COUNT(order_id) / COUNT(DISTINCT customer_id) as avg_freq FROM sales WHERE admin_id = %s"
        avg_res = Database.execute_query(avg_query, (admin_id,), fetch=True, fetch_all=False)
        avg_freq = round(float(avg_res['avg_freq']), 1) if avg_res and avg_res['avg_freq'] else 0.0

        return render_template('customers.html', customers=all_customers, top=top_customer, avg_freq=avg_freq)
    except Exception as e:
        logger.error(f"Error loading customers page: {e}")
        return render_template('customers.html', customers=[], top=None, avg_freq=0.0)

@app.route('/prediction')
@login_required
def prediction():
    """Renders the ML Prediction page with Smart Retail AI scoped by admin_id."""
    admin_id = session['user_id']
    try:
        # 1. Linear Regression Revenue Forecast
        history_query = """
            SELECT DATE_FORMAT(order_date, '%Y-%m-%d') as date, SUM(total_price) as revenue
            FROM sales
            WHERE admin_id = %s
            GROUP BY date
            ORDER BY date ASC
        """
        history = Database.execute_query(history_query, (admin_id,), fetch=True)
        
        predictions = []
        if history and len(history) >= 7:
            import numpy as np
            from sklearn.linear_model import LinearRegression
            import datetime
            
            recent_hist = history[-30:]
            X = np.arange(len(recent_hist)).reshape(-1, 1)
            y = np.array([float(h['revenue']) for h in recent_hist])
            
            model = LinearRegression()
            model.fit(X, y)
            
            last_date_str = recent_hist[-1]['date']
            last_date = datetime.datetime.strptime(last_date_str, '%Y-%m-%d')
            
            X_pred = np.arange(len(recent_hist), len(recent_hist) + 7).reshape(-1, 1)
            y_pred = model.predict(X_pred)
            y_pred = np.maximum(y_pred, 0)
            
            for i in range(7):
                next_date = last_date + datetime.timedelta(days=i+1)
                predictions.append({
                    'date': next_date.strftime('%Y-%m-%d'),
                    'revenue': round(float(y_pred[i]), 2)
                })

        # 2. Explosive Demand Alerts (Sales Velocity)
        demand_query = """
            WITH RecentSales AS (
                SELECT product_id, SUM(quantity) as recent_qty
                FROM sales
                WHERE admin_id = %s AND order_date >= (SELECT DATE_SUB(MAX(order_date), INTERVAL 7 DAY) FROM sales WHERE admin_id = %s)
                GROUP BY product_id
            ),
            PreviousSales AS (
                SELECT product_id, SUM(quantity) as prev_qty
                FROM sales
                WHERE admin_id = %s AND order_date >= (SELECT DATE_SUB(MAX(order_date), INTERVAL 14 DAY) FROM sales WHERE admin_id = %s)
                  AND order_date < (SELECT DATE_SUB(MAX(order_date), INTERVAL 7 DAY) FROM sales WHERE admin_id = %s)
                GROUP BY product_id
            )
            SELECT p.product_name, COALESCE(r.recent_qty, 0) as recent_qty, COALESCE(pr.prev_qty, 0) as prev_qty,
                   CASE 
                     WHEN COALESCE(pr.prev_qty, 0) = 0 AND COALESCE(r.recent_qty, 0) > 0 THEN 100
                     WHEN COALESCE(pr.prev_qty, 0) = 0 THEN 0
                     ELSE ((COALESCE(r.recent_qty, 0) - COALESCE(pr.prev_qty, 0)) / COALESCE(pr.prev_qty, 1)) * 100 
                   END as growth_pct
            FROM products p
            JOIN RecentSales r ON p.product_id = r.product_id
            LEFT JOIN PreviousSales pr ON p.product_id = pr.product_id
            WHERE p.admin_id = %s
            HAVING growth_pct > 20
            ORDER BY growth_pct DESC
            LIMIT 5
        """
        explosive_demand = Database.execute_query(demand_query, (admin_id, admin_id, admin_id, admin_id, admin_id, admin_id), fetch=True)

        # 3. VIP Customer Flight Risk (Churn AI)
        churn_query = """
            WITH CustomerStats AS (
                SELECT c.customer_id, c.customer_name, 
                       SUM(s.total_price) as lifetime_spend,
                       MAX(s.order_date) as last_purchase_date
                FROM customers c
                JOIN sales s ON c.admin_id = s.admin_id AND c.customer_id = s.customer_id
                WHERE c.admin_id = %s
                GROUP BY c.customer_id, c.customer_name
            )
            SELECT customer_name, lifetime_spend, last_purchase_date,
                   DATEDIFF((SELECT MAX(order_date) FROM sales WHERE admin_id = %s), last_purchase_date) as days_since_purchase
            FROM CustomerStats
            WHERE DATEDIFF((SELECT MAX(order_date) FROM sales WHERE admin_id = %s), last_purchase_date) > 30
            ORDER BY lifetime_spend DESC
            LIMIT 5
        """
        flight_risks = Database.execute_query(churn_query, (admin_id, admin_id, admin_id), fetch=True)

        return render_template('prediction.html', 
                               history=history, 
                               predictions=predictions,
                               explosive_demand=explosive_demand,
                               flight_risks=flight_risks)
    except Exception as e:
        logger.error(f"Error loading prediction page: {e}")
        return render_template('prediction.html', history=[], predictions=[], explosive_demand=[], flight_risks=[])

@app.route('/reports')
@login_required
def reports():
    """Renders the Reports and Export page."""
    return render_template('reports.html')

@app.route('/about')
def about():
    """Renders the About page."""
    return render_template('about.html')

@app.route('/contact')
def contact():
    """Renders the Contact page."""
    return render_template('contact.html')

@app.route('/export/<format_type>/<report_type>')
@login_required
def export_report(format_type, report_type):
    """Generates and downloads CSV, Excel, or PDF reports dynamically."""
    admin_id = session['user_id']
    if format_type not in ['csv', 'excel', 'pdf']:
        abort(400, "Invalid format type")
        
    query = ""
    columns = []
    
    if report_type == 'sales':
        query = """
            SELECT s.order_date, c.customer_name, p.product_name, s.quantity, s.total_price 
            FROM sales s 
            JOIN customers c ON s.admin_id = c.admin_id AND s.customer_id = c.customer_id 
            JOIN products p ON s.admin_id = p.admin_id AND s.product_id = p.product_id 
            WHERE s.admin_id = %s
            ORDER BY s.order_date DESC
        """
        columns = ['Order Date', 'Customer', 'Product', 'Qty', 'Revenue']
    elif report_type == 'products':
        query = """
            SELECT p.product_name, c.category_name, SUM(s.quantity) as units_sold, SUM(s.total_price) as revenue 
            FROM products p 
            JOIN categories c ON p.category_id = c.category_id 
            LEFT JOIN sales s ON p.admin_id = s.admin_id AND p.product_id = s.product_id 
            WHERE p.admin_id = %s
            GROUP BY p.product_name, c.category_name
            ORDER BY revenue DESC
        """
        columns = ['Product Name', 'Category', 'Units Sold', 'Revenue']
    elif report_type == 'customers':
        query = """
            SELECT customer_name, city, state, SUM(total_price) as lifetime_value 
            FROM customers c 
            LEFT JOIN sales s ON c.admin_id = s.admin_id AND c.customer_id = s.customer_id 
            WHERE c.admin_id = %s
            GROUP BY customer_name, city, state
            ORDER BY lifetime_value DESC
        """
        columns = ['Customer Name', 'City', 'State', 'Lifetime Value']
    elif report_type == 'prediction':
        query = """
            SELECT DATE_FORMAT(order_date, '%Y-%m-%d') as date, SUM(total_price) as revenue
            FROM sales WHERE admin_id = %s GROUP BY date ORDER BY date ASC
        """
        columns = ['Date', 'Historical Revenue']
    else:
        abort(404, "Report type not found")
        
    data = Database.execute_query(query, (admin_id,), fetch=True)
    if not data:
        flash('No data available to export.', 'warning')
        return redirect(url_for('reports'))
        
    raw_keys = list(data[0].keys())
    list_data = [[str(row[k]) for k in raw_keys] for row in data]
    df = pd.DataFrame(list_data, columns=columns)
    filename = f"RetailIQ_{report_type}_report"
    
    if format_type == 'csv':
        output = io.BytesIO()
        df.to_csv(output, index=False, encoding='utf-8')
        output.seek(0)
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name=f"{filename}.csv")
        
    elif format_type == 'excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Report Data')
        output.seek(0)
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=f"{filename}.xlsx")
        
    elif format_type == 'pdf':
        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        elements.append(Paragraph(f"RetailIQ: {report_type.capitalize()} Report", styles['Title']))
        
        table_data = [columns] + list_data[:500]
        t = Table(table_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2a5298")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-1), colors.beige),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        elements.append(t)
        doc.build(elements)
        output.seek(0)
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name=f"{filename}.pdf")

# API Endpoints for Chart.js and dynamic data
@app.route('/api/sales-trend')
@login_required
def api_sales_trend():
    admin_id = session['user_id']
    query = "SELECT DATE_FORMAT(order_date, '%Y-%m') AS month, SUM(total_price) AS revenue FROM sales WHERE admin_id = %s GROUP BY month ORDER BY month ASC"
    data = Database.execute_query(query, (admin_id,), fetch=True)
    return jsonify(data if data else [])

@app.route('/api/category-sales')
@login_required
def api_category_sales():
    admin_id = session['user_id']
    query = "SELECT cat.category_name, SUM(s.total_price) AS revenue FROM sales s JOIN products p ON s.admin_id = p.admin_id AND s.product_id = p.product_id JOIN categories cat ON p.category_id = cat.category_id WHERE s.admin_id = %s GROUP BY cat.category_name"
    data = Database.execute_query(query, (admin_id,), fetch=True)
    return jsonify(data if data else [])

@app.route('/api/top-products')
@login_required
def api_top_products():
    admin_id = session['user_id']
    query = "SELECT p.product_name, SUM(s.quantity) AS units FROM sales s JOIN products p ON s.admin_id = p.admin_id AND s.product_id = p.product_id WHERE s.admin_id = %s GROUP BY p.product_name ORDER BY units DESC LIMIT 5"
    data = Database.execute_query(query, (admin_id,), fetch=True)
    return jsonify(data if data else [])

@app.route('/api/payments')
@login_required
def api_payments():
    admin_id = session['user_id']
    query = "SELECT pay.payment_method, COUNT(s.order_id) AS total_orders FROM sales s JOIN payments pay ON s.payment_id = pay.payment_id WHERE s.admin_id = %s GROUP BY pay.payment_method"
    data = Database.execute_query(query, (admin_id,), fetch=True)
    return jsonify(data if data else [])

@app.route('/api/city-sales')
@login_required
def api_city_sales():
    admin_id = session['user_id']
    query = "SELECT c.city, SUM(s.total_price) AS revenue FROM sales s JOIN customers c ON s.admin_id = c.admin_id AND s.customer_id = c.customer_id WHERE s.admin_id = %s GROUP BY c.city ORDER BY revenue DESC LIMIT 5"
    data = Database.execute_query(query, (admin_id,), fetch=True)
    return jsonify(data if data else [])

@app.route('/api/revenue-growth')
@login_required
def api_revenue_growth():
    admin_id = session['user_id']
    query = "SELECT DATE_FORMAT(order_date, '%Y-%m') AS month, SUM(total_price) AS revenue FROM sales WHERE admin_id = %s GROUP BY month ORDER BY month ASC"
    data = Database.execute_query(query, (admin_id,), fetch=True)
    return jsonify(data if data else [])

@app.route('/api/recent-sales')
@login_required
def api_recent_sales():
    admin_id = session['user_id']
    query = "SELECT s.order_id, s.order_date, c.customer_name, p.product_name, s.total_price FROM sales s JOIN customers c ON s.admin_id = c.admin_id AND s.customer_id = c.customer_id JOIN products p ON s.admin_id = p.admin_id AND s.product_id = p.product_id WHERE s.admin_id = %s ORDER BY s.order_date DESC, s.created_at DESC LIMIT 5"
    data = Database.execute_query(query, (admin_id,), fetch=True)
    return jsonify(data if data else [])

@app.route('/api/analytics-filters')
@login_required
def api_analytics_filters():
    admin_id = session['user_id']
    try:
        categories = Database.execute_query("SELECT category_name FROM categories WHERE admin_id = %s ORDER BY category_name", (admin_id,), fetch=True)
        cities = Database.execute_query("SELECT DISTINCT city FROM customers WHERE admin_id = %s ORDER BY city", (admin_id,), fetch=True)
        return jsonify({
            'categories': [c['category_name'] for c in categories] if categories else [],
            'cities': [c['city'] for c in cities] if cities else []
        })
    except Exception as e:
        return jsonify({'categories': [], 'cities': []})

@app.route('/api/analytics-data')
@login_required
def api_analytics_data():
    admin_id = session['user_id']
    category = request.args.get('category', '')
    city = request.args.get('city', '')
    query = "SELECT DATE_FORMAT(s.order_date, '%Y-%m') AS month, SUM(s.total_price) AS revenue FROM sales s JOIN products p ON s.admin_id = p.admin_id AND s.product_id = p.product_id JOIN categories cat ON p.category_id = cat.category_id JOIN customers c ON s.admin_id = c.admin_id AND s.customer_id = c.customer_id WHERE s.admin_id = %s"
    params = [admin_id]
    
    if category:
        query += " AND cat.category_name = %s"
        params.append(category)
    if city:
        query += " AND c.city = %s"
        params.append(city)
        
    query += " GROUP BY month ORDER BY month ASC"
    data = Database.execute_query(query, params, fetch=True)
    return jsonify({'symbol': get_currency_symbol(), 'data': data if data else []})

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    app.run(debug=True, port=5000)

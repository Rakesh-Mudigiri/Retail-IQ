# RetailIQ – Smart Retail Analytics & Demand Prediction System

**Tagline**: Empowering smarter retail decisions through Data Analytics and Machine Learning.

## Project Overview
RetailIQ is a full-stack, production-ready web application designed for retail businesses to analyze historical sales data, visualize key performance indicators (KPIs) through interactive dashboards, and predict future sales demand using Machine Learning (Linear Regression).

## Features
- **ETL Pipeline**: Upload CSV datasets, automatically clean data, handle missing values, and load into a normalized MySQL database.
- **Interactive Dashboards**: Real-time business metrics (Revenue, Orders) visualized using Chart.js.
- **Machine Learning**: Predict next month's sales based on time-series feature engineering.
- **Reporting**: Export analytics to CSV, PDF, and Excel.
- **Responsive UI**: Built with Bootstrap 5, featuring a clean, corporate, and user-friendly interface.

## Tech Stack
- **Frontend**: HTML5, CSS3, Bootstrap 5, JavaScript, Chart.js
- **Backend**: Python 3, Flask, Werkzeug
- **Database**: MySQL (mysql-connector-python)
- **Data Science & ML**: Pandas, NumPy, Scikit-Learn, Joblib
- **Utilities**: Faker (Dataset Generation), python-dotenv

## Installation & Setup

1. **Clone the Repository**
2. **Create a Virtual Environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Database Setup**
   - Ensure MySQL Server is running.
   - Run the script `sql/database.sql` to create the schema.
   - Configure your credentials in `config.py` (or create a `.env` file).
5. **Generate Dataset & Run Pipeline**
   ```bash
   python generate_dataset.py
   python etl.py
   ```
6. **Run the Application**
   ```bash
   python app.py
   ```
   Access the app at `http://127.0.0.1:5000`

## Future Scope
- Integration with external BI tools (Tableau/PowerBI).
- Advanced Deep Learning models (LSTMs) for time-series forecasting.
- Real-time payment gateway integration.

## License
MIT License

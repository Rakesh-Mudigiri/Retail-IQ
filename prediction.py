"""
Machine Learning Module for RetailIQ.
Trains a Linear Regression model to predict next month's sales based on historical data.
"""

import pandas as pd
import numpy as np
import os
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib
from database import Database
from utils import logger, handle_exception

class SalesPredictor:
    def __init__(self, model_path=os.path.join('models', 'sales_model.pkl')):
        self.model_path = model_path
        self.model = None

    def fetch_training_data(self):
        """Fetches historical sales data from the database and aggregates it by date."""
        try:
            logger.info("Fetching data for ML model training...")
            query = """
                SELECT order_date, SUM(total_price) as daily_revenue
                FROM sales
                GROUP BY order_date
                ORDER BY order_date ASC
            """
            data = Database.execute_query(query, fetch=True)
            if not data:
                logger.warning("No data found for training.")
                return None
                
            df = pd.DataFrame(data)
            df['order_date'] = pd.to_datetime(df['order_date'])
            
            # Feature Engineering: 
            # We want to predict sales based on day of year, day of week, month, etc.
            # But a simpler time-series regression for 'Next Month' can use Days Since Start
            
            df['days_since_start'] = (df['order_date'] - df['order_date'].min()).dt.days
            df['month'] = df['order_date'].dt.month
            df['day_of_week'] = df['order_date'].dt.dayofweek
            
            return df
        except Exception as e:
            handle_exception(e, "Failed to fetch training data")
            return None

    def train_model(self):
        """Trains the Linear Regression model."""
        df = self.fetch_training_data()
        if df is None or len(df) < 10:
            logger.error("Not enough data to train the model.")
            return False

        try:
            # Features and Target
            X = df[['days_since_start', 'month', 'day_of_week']]
            y = df['daily_revenue']

            # Train Test Split
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            # Train Model
            self.model = LinearRegression()
            self.model.fit(X_train, y_train)

            # Evaluate
            predictions = self.model.predict(X_test)
            rmse = np.sqrt(mean_squared_error(y_test, predictions))
            mae = mean_absolute_error(y_test, predictions)
            r2 = r2_score(y_test, predictions)

            logger.info(f"Model trained successfully. RMSE: {rmse:.2f}, MAE: {mae:.2f}, R2: {r2:.2f}")

            # Save Model
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump(self.model, self.model_path)
            logger.info(f"Model saved to {self.model_path}")
            
            return {'rmse': rmse, 'mae': mae, 'r2': r2}

        except Exception as e:
            handle_exception(e, "Model training failed")
            return False

    def load_model(self):
        """Loads the saved model."""
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
                return True
            else:
                logger.warning("Model file not found. Please train the model first.")
                return False
        except Exception as e:
            handle_exception(e, "Failed to load model")
            return False

    def predict_next_month(self):
        """Predicts the total sales for the next 30 days."""
        if self.model is None:
            if not self.load_model():
                return None

        try:
            # Get latest date from DB to know where to start predicting
            query = "SELECT MAX(order_date) as last_date FROM sales"
            result = Database.execute_query(query, fetch=True, fetch_all=False)
            if not result or not result['last_date']:
                return None
                
            last_date = pd.to_datetime(result['last_date'])
            
            # Fetch min date to calculate 'days_since_start'
            query_min = "SELECT MIN(order_date) as start_date FROM sales"
            result_min = Database.execute_query(query_min, fetch=True, fetch_all=False)
            start_date = pd.to_datetime(result_min['start_date'])

            predictions = []
            total_predicted_revenue = 0

            # Predict for next 30 days
            for i in range(1, 31):
                target_date = last_date + pd.Timedelta(days=i)
                days_since = (target_date - start_date).days
                
                features = pd.DataFrame([{
                    'days_since_start': days_since,
                    'month': target_date.month,
                    'day_of_week': target_date.dayofweek
                }])
                
                pred_revenue = max(0, self.model.predict(features)[0]) # Cannot have negative revenue
                
                predictions.append({
                    'date': target_date.strftime('%Y-%m-%d'),
                    'predicted_revenue': round(pred_revenue, 2)
                })
                total_predicted_revenue += pred_revenue

            return {
                'total_predicted_revenue': round(total_predicted_revenue, 2),
                'daily_predictions': predictions
            }

        except Exception as e:
            handle_exception(e, "Prediction failed")
            return None

if __name__ == '__main__':
    predictor = SalesPredictor()
    metrics = predictor.train_model()
    if metrics:
        print("Training Metrics:", metrics)
        print("Next Month Prediction:", predictor.predict_next_month()['total_predicted_revenue'])

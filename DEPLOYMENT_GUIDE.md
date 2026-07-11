# RetailIQ Deployment Guide

This guide outlines the process of deploying the RetailIQ Flask application to a production environment. 

> [!WARNING]
> Never use the built-in Flask development server (`app.run()`) in a production environment. It is not designed to be secure, stable, or efficient. Instead, use a production WSGI server like **Gunicorn** (for Linux) or **Waitress** (for Windows).

---

## 1. Prerequisites for Deployment

Before deploying, ensure you have the following ready:
- A cloud hosting provider (e.g., AWS, Render, Heroku, DigitalOcean).
- A production-grade MySQL database (e.g., AWS RDS, DigitalOcean Managed Database, or a remote MySQL instance).
- A production WSGI server.

### Install Production Dependencies

Add a WSGI server to your `requirements.txt` file based on your deployment OS:

**For Linux (Render, Heroku, AWS, Ubuntu):**
```bash
pip install gunicorn
```
Add `gunicorn==21.2.0` to `requirements.txt`.

**For Windows Servers:**
```bash
pip install waitress
```
Add `waitress==2.1.2` to `requirements.txt`.

---

## 2. Environment Variables & Configuration

> [!CAUTION]
> Never hardcode production database credentials or secret keys in your source code (`config.py`).

In production, you should rely on Environment Variables. 

Create a `.env` file on your server (or configure environment variables in your cloud provider's dashboard):

```env
# Flask Application
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=your_super_secret_key_here

# MySQL Database Configuration
DB_HOST=your-production-db-host.com
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=retailiq_prod
```

Ensure your `config.py` is set up to read from `os.environ` (using `python-dotenv`).

---

## 3. Database Initialization

1. Connect to your production MySQL server.
2. Run the `sql/database.sql` script to create the necessary tables.
3. Once the tables are created, you can seed the initial data by running the ETL pipeline **once**:
   ```bash
   python generate_dataset.py
   python etl.py
   ```

---

## 4. Deployment Strategies

### Option A: Deploying on Render (Recommended for simplicity)

1. **Push to GitHub**: Make sure your code is hosted on a GitHub repository.
2. **Create a Render Account**: Go to [Render](https://render.com) and sign in.
3. **Database**: Create a MySQL database (Render offers PostgreSQL natively, so you might need an external MySQL host like PlanetScale, Aiven, or AWS RDS).
4. **Web Service**: 
   - Click "New +" -> "Web Service".
   - Connect your GitHub repository.
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. **Environment Variables**: Add all the variables from the `.env` section into Render's Environment tab.

### Option B: Deploying on a Linux Virtual Private Server (VPS like DigitalOcean/AWS EC2)

If you are deploying on a Linux machine running Ubuntu, follow these steps:

1. **Clone the code to your server:**
   ```bash
   git clone https://github.com/yourusername/RetailIQ.git
   cd RetailIQ
   ```

2. **Setup Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install gunicorn
   ```

3. **Setup Systemd Service for Gunicorn:**
   Create a service file: `sudo nano /etc/systemd/system/retailiq.service`
   ```ini
   [Unit]
   Description=Gunicorn instance to serve RetailIQ
   After=network.target

   [Service]
   User=ubuntu
   Group=www-data
   WorkingDirectory=/home/ubuntu/RetailIQ
   Environment="PATH=/home/ubuntu/RetailIQ/venv/bin"
   EnvironmentFile=/home/ubuntu/RetailIQ/.env
   ExecStart=/home/ubuntu/RetailIQ/venv/bin/gunicorn --workers 3 --bind unix:retailiq.sock -m 007 app:app

   [Install]
   WantedBy=multi-user.target
   ```
   Start and enable the service:
   ```bash
   sudo systemctl start retailiq
   sudo systemctl enable retailiq
   ```

4. **Setup Nginx as a Reverse Proxy:**
   Install Nginx: `sudo apt install nginx`
   Configure Nginx: `sudo nano /etc/nginx/sites-available/retailiq`
   ```nginx
   server {
       listen 80;
       server_name your_domain.com www.your_domain.com;

       location / {
           include proxy_params;
           proxy_pass http://unix:/home/ubuntu/RetailIQ/retailiq.sock;
       }
   }
   ```
   Enable the site and restart Nginx:
   ```bash
   sudo ln -s /etc/nginx/sites-available/retailiq /etc/nginx/sites-enabled
   sudo systemctl restart nginx
   ```

---

## 5. Post-Deployment Checks

> [!TIP]
> Always verify the following after your first successful deployment:

- Check the `/logs` directory on the server to see if any application errors are occurring.
- Ensure the Machine Learning models (`models/`) are loading correctly and memory usage is stable.
- Verify that users can securely log in and view the Chart.js dashboards.
- Ensure file uploads for the ETL pipeline are functioning correctly and that proper permissions are set on the `dataset/` directory.

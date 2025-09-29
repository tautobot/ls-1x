# livescores-8x

# Streamlit app

Introduce streamlit app

## Install Python, Poetry
  
1. Install Python 3.10.11 or above
```
pyenv install 3.10.11
echo "3.10.11" >> .python-version
```
 
2. Install Poetry
```
pip install poetry
```

3. Configure project
```
cp .env-template .env
```
then install dependencies
```
poetry install
```
4. Run Streamlit app (stapp.py)
```
poetry shell
python -m streamlit run streamlit_app.py
```

Configure Streamlit to Run on Public IP
```
mkdir -p ~/.streamlit
nano ~/.streamlit/config.toml
```

Add the following to the config.toml file:
```
[server]
headless = true
enableCORS = false
port = 8501
enableXsrfProtection = false
address = "0.0.0.0"
```

Allow Port 8501 Through Firewall
```
sudo ufw allow 8501
```

Run Streamlit app headless
```
nohup poetry run streamlit run app.py > app.log 2>&1 &
```

Kill streamlit process (if needed)
```
pkill -f "streamlit run"
```

Check streamlit process
```
ps aux | grep streamlit
```

Here’s How to Fix It on GCP

🔧 Step-by-Step: Open Port 8501 on GCP
	1.	Go to your Google Cloud Console
https://console.cloud.google.com/
	2.	Navigate to:
VPC network → Firewall
	3.	Click “Create Firewall Rule”
	4.	Fill in the form:
Name: streamlit
Target tags: streamlit
Allow 
    Targets: All instances in the network
    Source filter: IPv4 ranges
    Source IPv4 ranges: 0.0.0.0/0
    Protocol and ports:
        √ Specified protocols and ports
        √ TCP 
        Ports:8501


# NGINX
Optional: Setup with Domain + HTTPS (via Nginx + Let’s Encrypt)
Install Nginx
```
sudo apt install nginx -y
```

Set Up Reverse Proxy for Streamlit
Create a config file:
```
sudo nano /etc/nginx/sites-available/streamlit
```

Example config:
```
server {
    listen 80;
    server_name your_domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the config file and restart nginx:
```
sudo ln -s /etc/nginx/sites-available/streamlit /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

Set Up HTTPS (Let’s Encrypt)
```
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your_domain.com
```

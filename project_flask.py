from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import socket
import re

app = Flask(__name__)
socketio = SocketIO(app)

def get_domain_info(url):
    parsed_url = urlparse(url)
    domain = parsed_url.netloc

    try:
        ip_address = socket.gethostbyname(domain)
    except socket.gaierror:
        ip_address = None

    domain_info = {
        "ip": ip_address,
        "isp": None,
        "organization": None,
        "asn": None,
        "location": None
    }

    # Fetch ISP, Organization, ASN, and Location information using an API (e.g., ipinfo.io)
    try:
        response = requests.get(f"https://ipinfo.io/{ip_address}/json")
        if response.status_code == 200:
            data = response.json()
            domain_info["isp"] = data.get("org")
            domain_info["organization"] = data.get("org")
            domain_info["asn"] = data.get("asn")
            domain_info["location"] = data.get("country")
    except requests.exceptions.RequestException as e:
        print("Error fetching domain info:", str(e))

    return domain_info

def get_subdomain_info(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    subdomains = set()

    # Find all links (anchor tags) in the HTML content
    for link in soup.find_all('a', href=True):
        # Extract the hostname from the href attribute of the link
        hostname = urlparse(link['href']).hostname
        if hostname:
            subdomains.add(hostname)

    return list(subdomains)

def get_external_resources(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    assets = {
        "stylesheets": [],
        "images": [],
        "iframes": [],
        "anchors": []
    }

    # Find all <link> tags with a rel attribute containing "stylesheet"
    for link in soup.find_all('link', rel=re.compile(r'stylesheet', re.I)):
        href = link.get('href')
        if href:
            assets['stylesheets'].append(href)

    # Find all <img> tags
    for img in soup.find_all('img'):
        src = img.get('src')
        if src:
            assets['images'].append(src)

    # Find all <iframe> tags
    for iframe in soup.find_all('iframe'):
        src = iframe.get('src')
        if src:
            assets['iframes'].append(src)

    # Find all <a> tags
    for anchor in soup.find_all('a', href=True):
        href = anchor.get('href')
        if href:
            assets['anchors'].append(href)

    return assets

@app.route('/')
def analyze_website():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "URL parameter is missing"}), 400

    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 400

    domain_info = get_domain_info(url)
    subdomain_info = get_subdomain_info(response.text)
    external_resources = get_external_resources(response.text)

    return jsonify({
        "info": domain_info,
        "subdomains": subdomain_info,
        "asset_domains": external_resources
    })

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('message')
def handle_message(data):
    if 'url' in data:
        url = data['url']
        session_data = f"session created for {url}"
        emit('output', {"data": session_data})
    elif 'operation' in data:
        if data['operation'] == 'get_info':
            domain_info = get_domain_info("http://" + data['url'])
            emit('output', {"data": domain_info})
        elif data['operation'] == 'get_subdomains':
            response = requests.get("http://" + data['url'])
            subdomain_info = get_subdomain_info(response.text)
            emit('output', {"data": subdomain_info})
        elif data['operation'] == 'get_asset_domains':
            response = requests.get("http://" + data['url'])
            asset_domains = get_external_resources(response.text)
            emit('output', {"data": asset_domains})
        else:
            emit('error', {"error": "Invalid operation"})

if __name__ == '__main__':
    socketio.run(app, debug=True)

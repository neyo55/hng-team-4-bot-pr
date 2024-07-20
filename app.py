from flask import Flask, request, jsonify
import subprocess
import requests
import re
import jwt
import time
import os
import hmac
import hashlib
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Load configuration from environment variables
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
APP_ID = os.getenv('APP_ID')
PRIVATE_KEY_PATH = os.getenv('PRIVATE_KEY_PATH')

# Load the private key
with open(PRIVATE_KEY_PATH, 'r') as key_file:
    private_key = serialization.load_pem_private_key(
        key_file.read().encode(),
        password=None,
        backend=default_backend()
    )

def verify_signature(payload, signature):
    """Verify GitHub webhook signature."""
    mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload, digestmod=hashlib.sha256)
    return hmac.compare_digest('sha256=' + mac.hexdigest(), signature)

def get_jwt_token():
    """Create a JWT token for GitHub App authentication."""
    current_time = int(time.time())
    payload = {
        'iat': current_time,
        'exp': current_time + (10 * 60),  # 10 minute expiration
        'iss': APP_ID
    }
    jwt_token = jwt.encode(payload, private_key, algorithm='RS256')
    return jwt_token

def get_installation_access_token(installation_id):
    """Get the installation access token."""
    jwt_token = get_jwt_token()
    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    response = requests.post(
        f'https://api.github.com/app/installations/{installation_id}/access_tokens',
        headers=headers
    )
    response.raise_for_status()
    return response.json()['token']

@app.route('/webhook', methods=['POST'])
def webhook():
    # Verify payload signature
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, signature):
        return jsonify({'message': 'Invalid signature'}), 401

    data = request.json
    action = data.get('action')
    if 'pull_request' in data:
        pr_number = data['pull_request']['number']
        repo_name = data['repository']['full_name']
        branch_name = data['pull_request']['head']['ref']
        installation_id = data['installation']['id']

        if action in ['opened', 'synchronize']:
            # Get installation access token
            access_token = get_installation_access_token(installation_id)
            comment_url = f"https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments"

            # Notify stakeholders (comment on the PR)
            notify_stakeholders(comment_url, "Deployment started for this pull request.", access_token)

            # Run the deployment script with the branch name and PR number
            container_name, deployment_link = run_deployment_script(branch_name, pr_number)

            # Notify stakeholders with the result
            if deployment_link:
                notify_stakeholders(comment_url, f"Deployment successful. [Deployed application]({deployment_link}).", access_token)
            else:
                notify_stakeholders(comment_url, "Deployment failed. Please check the logs.", access_token)

            return jsonify({'message': 'Deployment processed'}), 200

        elif action == 'closed':
            # Pull request closed, trigger cleanup regardless of merge status
            run_cleanup_script(branch_name, pr_number)
            
            # Notify stakeholders about the cleanup
            access_token = get_installation_access_token(installation_id)
            comment_url = f"https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments"
            notify_stakeholders(comment_url, "Cleanup completed for this pull request.", access_token)

        return jsonify({'message': 'Cleanup processed'}), 200

    return jsonify({'message': 'No action taken'}), 200

def notify_stakeholders(comment_url, message, access_token):
    headers = {
        'Authorization': f'token {access_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    data = {'body': message}
    response = requests.post(comment_url, headers=headers, json=data)
    if response.status_code != 201:
        print(f"Failed to comment on PR: {response.json()}")

def run_deployment_script(branch_name, pr_number):
    try:
        result = subprocess.run(['./deploy.sh', branch_name, str(pr_number)], check=True, capture_output=True, text=True)
        print(result.stdout)

        # Extract container name and deployment URL from the output
        container_name_match = re.search(r'Container name: ([^\s]+)', result.stdout)
        deployment_url_match = re.search(r'Deployment complete: (http://[^\s]+)', result.stdout)
        container_name = container_name_match.group(1) if container_name_match else None
        deployment_url = deployment_url_match.group(1) if deployment_url_match else None

        return container_name, deployment_url

    except subprocess.CalledProcessError as e:
        print(f"Deployment script failed with error: {e.stderr}")
        return None, None

def run_cleanup_script(branch_name, pr_number):
    try:
        subprocess.run(['./cleanup.sh', branch_name, str(pr_number)], check=True)
        print("Cleanup script executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Cleanup script failed with error: {e.stderr}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

### Overview:
This repository contains the code for the GitHub bot that interacts with pull requests (PRs). The bot provides real-time deployment status updates, including links to the deployed environments. It also cleans up containers and resources associated with closed PRs.

- **app.py**: Main bot code.
- **cleanup.sh**: Event handlers for containers clean up.
- **deploy.sh**: Event handlers for deployment and PR events.
- **requirements.txt**: List of Python dependencies.
- **steps.txt**: 

### Prerequisites:
- Python 3.8 or higher installed.
- GitHub account with admin access to the repository.
- image for the BOT.

### How to Start
- **Clone this reposo on your local machine of fork the reository then clone it to your machine**
```
git clone <repo.git>
``` 
- **install Python on your machine**

[Python documentation](https://www.python.org/downloads/)

- **Start a Virtual environment**
```
python -m venv venv
```
  - For windows
    ```
    venv/Scripts/activate
    ```
  - For Linux
    ```
    source venv/bin/activate
    ```
- **Install all depencencies from requirements.txt**
```
pip install -r requirements.txt
```
- **Create a .env file at the root directory**
Follow how to create a GitHub App to get necessary credentials. In this case You will need three Items
```WEBHOOK_SECRET```, ```APP_ID ```, ```PRIVATE_KEY_PATH ```

- **After all setups are complete, start the server**
```
python app.py
```
- **Install ngrok on your machine**
follow this documentation to get started on ngrok [ngrok documentation](https://ngrok.com/docs/getting-started/)
- **Open a new terminal on your VS code to expose your localhost to the internet**
```
ngrok http 5000
```
- **Access your exposed port on ngrok**
```
https://ngrok<assess_id> -> app.py
```

## How the Pyton Script works
Below are the criteria to which the python script must comform to in other to term it a success.

**PR Deployment:** PRs trigger Docker container deployment with each new commit.
**GitHub Bot Integration:** Bot comments on PRs with deployment status and links.
**Container Management:** Containers are updated with new commits and cleaned up upon PR closure.

### Step 1
Craete a flask App and name it app.py

### Step 2
Import necessary libraries
```
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
```
### Step 3
Create an instance of the Flask application
```app = Flask(__name__)```
### Step 4
Export from the .env file and Load configuration
```
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
APP_ID = os.getenv('APP_ID')
PRIVATE_KEY_PATH = os.getenv('PRIVATE_KEY_PATH')

with open(PRIVATE_KEY_PATH, 'r') as key_file:
    private_key = serialization.load_pem_private_key(
        key_file.read().encode(),
        password=None,
        backend=default_backend()
    )
```

### Step 5
Then define a function to verify the GitHub webhook signature using HMAC with SHA-256.
```
def verify_signature(payload, signature):
    """Verify GitHub webhook signature."""
    mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload, digestmod=hashlib.sha256)
    return hmac.compare_digest('sha256=' + mac.hexdigest(), signature)
```

### Step 6
Then define a function to create a JWT token for authenticating the GitHub App so that the webhook appliction link ngrok can display information in JSON format.
```
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
```
### Step 7
Then define a function to get an installation access token from GitHub using the JWT token. This function would alow the installation of access tokens on the GitHub App from GitHub.
```
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
```

### Step 8
Then define a Flask route to handle POST requests sent to the /webhook endpoint. Then retrieves the webhook signature from the request headers and verify it. If invalid, returns a 401 Unauthorized response. It will extracts the JSON payload from the request and retrieves the action field
```
@app.route('/webhook', methods=['POST'])
def webhook():
 signature = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, signature):
        return jsonify({'message': 'Invalid signature'}), 401

    data = request.json
    action = data.get('action')
```

### Step 9
Then check if the event is related to a pull request and extract relevant information from the payload. Also confirms If the pull request is opened or synchronized, retrieve the installation access token and construct the comment URL for the pull request. Then notifies stakeholders with the result of the deployment with 200 OK.. If the pull request is closed, runs the cleanup script and notifies stakeholders about the cleanup, Then returns a 200 OK response indicating the cleanup was processed.
```
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
```
### Step 10
Then define a function to notify stakeholders by commenting on the pull request.
```
def notify_stakeholders(comment_url, message, access_token):
    headers = {
        'Authorization': f'token {access_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    data = {'body': message}
    response = requests.post(comment_url, headers=headers, json=data)
    if response.status_code != 201:
        print(f"Failed to comment on PR: {response.json()}")

```
### Step 11
Also defines a function to run the deployment script and extract the container name and deployment URL from the output.
```
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
```
### step 12
Defines a function to run the cleanup script and handle errors. 
```
def run_cleanup_script(branch_name, pr_number):
    try:
        subprocess.run(['./cleanup.sh', branch_name, str(pr_number)], check=True)
        print("Cleanup script executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Cleanup script failed with error: {e.stderr}")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

## Set Up a Cleanup.sh file in the root directory
The cleanup.sh script automates the process of stopping and removing Docker containers associated with a specific branch and pull request. This ensures no leftover containers are running after the PR is closed or no longer needed, helping maintain a clean and efficient development environment.

Starts by defining a **Shebang** 
```#!/bin/bash```

### Total accomplishment of the cleanup.sh
- ***Run as Root Check: Ensures the script is executed with root privileges.***
- ***Branch Name Check: Verifies that a branch name is provided.***
- ***Set Variables: Initializes BRANCH_NAME and PR_NUMBER.***
- ***Cleanup Process: Iterates through container info files, stops and removes containers, and deletes info files.***

## Set up a deploy.sh file in the root directory
This script will automates the deployment process, ensuring consistency and efficiency in setting up Docker containers for different branches and PRs.
Starts by defining a **Shebang** 
```#!/bin/bash```

### Total accomplishment of the deploy.sh
- ***Run as Root Check: Ensures the script is executed with root privileges.***
- ***Branch Name Check: Verifies that a branch name is provided.***
- ***Set Variables: Initializes BRANCH_NAME, PR_NUMBER, REMOTE_HOST, REPO_URL, REMOTE_DIR, TIMESTAMP, and CONTAINER_INFO_FILE.***
- ***Find Random Port: Selects an available random port between 4000 and 7000.***
- ***Prepare Deployment Directory: Removes existing directory to avoid conflicts and clones the repository.***
- ***Checkout and Pull Branch: Checks out the specified branch and pulls the latest changes.***
- ***Build and Run Docker Container: Builds the Docker image and runs the container with the unique name and port.***
- ***Save Deployment Info: Saves container name and port to a file for future cleanup.***
- ***Output Deployment Info: Prints the container name and deployment URL.***

# Conclusion

This set of scripts (`app.py`, `deploy.sh`, and `cleanup.sh`) provides a streamlined workflow for managing Docker containers associated with specific branches and pull requests (PRs). Automating deployments and testing of Pull request (PR) as well as commenting on them. This will save alot of time especially when working with a big team.

## `app.py`
- **Purpose:** Serves as the core backend for interacting with Docker containers.
- **Functionality:** Handles creation, configuration, and management of containers, ensuring that each container is uniquely identified by the branch name, PR number, and a random port.
- **Key Features:**
  - **Validation:** Ensures that necessary parameters are provided and valid.
  - **Docker Operations:** Facilitates Docker build, run, and management tasks.

## `deploy.sh`
- **Purpose:** Automates the deployment of Docker containers for specified branches and PRs.
- **Functionality:** Clones the repository, checks out the branch, builds the Docker image, runs the container, and saves the deployment information.
- **Key Features:**
  - **Port Management:** Finds an available port within a specified range.
  - **Repository Handling:** Clones and updates the repository to the specified branch.
  - **Docker Setup:** Builds and runs the Docker container, saving critical deployment information.

## `cleanup.sh`
- **Purpose:** Cleans up Docker containers and associated files for a given branch and PR.
- **Functionality:** Stops and removes containers, and deletes their respective information files.
- **Key Features:**
  - **File Handling:** Finds and reads container information files.
  - **Container Management:** Stops and removes Docker containers based on the stored information.

## Workflow Summary

1. **Deployment:**
   - Use `deploy.sh` to deploy a new Docker container. This script will handle repository cloning, branch checkout, Docker image building, and container running.
   - Example usage: `./deploy.sh <branch_name> <PR_number>`

2. **Cleanup:**
   - Use `cleanup.sh` to remove Docker containers and associated files after the PR is merged or no longer needed.
   - Example usage: `./cleanup.sh <branch_name> <PR_number>`

These scripts automate the complete lifecycle of Docker container management for branches and PRs, enhancing productivity and consistency in development workflows.

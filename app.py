from flask import Flask, request, jsonify
import subprocess
import requests
import re

app = Flask(__name__)

GITHUB_TOKEN = '${{ secrets.BOT_TOKEN }}'  # Replace with your GitHub token 

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if 'action' in data and data['action'] in ['opened', 'synchronize'] and 'pull_request' in data:
        pr_number = data['pull_request']['number']
        repo_name = data['repository']['full_name']
        branch_name = data['pull_request']['head']['ref']
        comment_url = f"https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments"

        # Notify stakeholders (comment on the PR)
        notify_stakeholders(comment_url, "Deployment started for this pull request.")

        # Run the deployment script with the branch name
        deployment_link = run_deployment_script(branch_name)

        # Notify stakeholders with the result
        if deployment_link:
            notify_stakeholders(comment_url, f"Deployment successful. [Deployed application]({deployment_link}).")
        else:
            notify_stakeholders(comment_url, "Deployment failed. Please check the logs.")

        return jsonify({'message': 'Deployment processed'}), 200
    return jsonify({'message': 'No action taken'}), 200

def notify_stakeholders(comment_url, message):
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    data = {'body': message}
    response = requests.post(comment_url, headers=headers, json=data)
    if response.status_code != 201:
        print(f"Failed to comment on PR: {response.json()}")

def run_deployment_script(branch_name):
    try:
        result = subprocess.run(['./deploy.sh', branch_name], check=True, capture_output=True, text=True)
        print(result.stdout)

        # Extract deployment URL from the output
        match = re.search(r'Deployment complete: (http://[^\s]+)', result.stdout)
        if match:
            return match.group(1)
        else:
            return None

    except subprocess.CalledProcessError as e:
        print(f"Deployment script failed with error: {e.stderr}")
        return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

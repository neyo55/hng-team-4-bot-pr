# Documentation for GitHub Bot Repository

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

import yaml
from celery import shared_task
from github import Github

# Στην πραγματικότητα, αυτά τα βάζεις στο αρχείο .env και τα τραβάς από το app.config
GITHUB_TOKEN = "your_github_personal_access_token"
REPO_NAME = "your-username/your-gitops-repo"

@shared_task(name="provision_env_task")
def provision_env_task(env_id: str, name: str, owner: str, tier: str, replicas: int):
    # 1. Συνδεόμαστε στο GitHub
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    
    # 2. Φτιάχνουμε το YAML του CRD (αυτό που είδαμε στο Task 2.1)
    crd_manifest = {
        "apiVersion": "idp.platform.io/v1alpha1",
        "kind": "Environment",
        "metadata": {
            "name": f"env-{name}"
        },
        "spec": {
            "owner": owner,
            "appName": name,
            "tier": tier,
            "database": True,
            "replicas": replicas
        }
    }
    
    # Μετατρέπουμε το λεξικό της Python σε καθαρό YAML κείμενο
    yaml_content = yaml.dump(crd_manifest, default_flow_style=False)
    
    # 3. Κάνουμε το Commit στο Git!
    file_path = f"gitops/apps/env-{name}.yaml"
    commit_message = f"IDP: Provision environment {name} requested by {owner}"
    
    try:
        repo.create_file(
            path=file_path,
            message=commit_message,
            content=yaml_content,
            branch="main"
        )
        # Εδώ, ιδανικά, στέλνουμε και ένα WebSocket μήνυμα ότι το αρχείο ανέβηκε!
        return f"Successfully committed {file_path}"
    except Exception as e:
        return f"Failed to commit: {str(e)}"
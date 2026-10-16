from celery import shared_task
from github import Github

GITHUB_TOKEN = "your_github_personal_access_token"
REPO_NAME = "your-username/your-gitops-repo"

@shared_task(name="deprovision_env_task")
def deprovision_env_task(env_id: str, name: str):
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    
    file_path = f"gitops/apps/env-{name}.yaml"
    commit_message = f"IDP: Deprovision environment {name}"
    
    try:
        # Το GitHub API απαιτεί να ξέρουμε το SHA (ταυτότητα) του αρχείου για να το σβήσουμε
        file_to_delete = repo.get_contents(file_path, ref="main")
        
        repo.delete_file(
            path=file_to_delete.path,
            message=commit_message,
            sha=file_to_delete.sha,
            branch="main"
        )
        return f"Successfully deleted {file_path}"
    except Exception as e:
        return f"Failed to delete (maybe it doesn't exist?): {str(e)}"
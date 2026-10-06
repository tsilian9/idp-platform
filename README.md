# IDP Platform (Internal Developer Platform)

A production-grade Internal Developer Platform built with Kubernetes, GitOps, and IaC.

## Architecture
* **Infrastructure as Code (IaC):** OpenTofu (Kind cluster)
* **Configuration Management:** Ansible (Helm bootstrapping)
* **GitOps:** Argo CD
* **Observability:** Prometheus, Grafana, Loki
* **Security:** HashiCorp Vault
* **Datastores:** PostgreSQL, Redis

## Quick Start

### 1. Provision Cluster (OpenTofu)
\`\`\`bash
cd infra/k8s-cluster
tofu init
tofu apply -auto-approve
\`\`\`

### 2. Bootstrap Core Services (Ansible)
\`\`\`bash
cd infra/ansible
ansible-playbook bootstrap.yml
\`\`\`

### 3. Access Argo CD
\`\`\`bash
# Get Admin Password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo

# Port Forward
kubectl port-forward svc/argocd-server -n argocd 8080:443
\`\`\`
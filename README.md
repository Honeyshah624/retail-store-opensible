
# Retail Store Sample App Deployment on AWS EKS using OpenSible

## 1. Objective

Deploy the AWS Retail Store Sample Application on Amazon EKS while using OpenSible as the automation platform.

The completed implementation covers:

- OpenSible installation using Docker Compose
- Custom OpenSible worker image
- AWS CLI integration
- `kubectl` integration
- Ansible integration
- Helm integration
- Helmfile integration
- Helm Diff plugin integration
- AWS authentication from the OpenSible worker
- Amazon EKS provisioning through OpenSible Cloud Stack/OpenTofu
- EKS kubeconfig configuration
- Retail Store Sample App source setup
- Application deployment using Helmfile through Ansible
- Kubernetes deployment verification
- UI exposure using an AWS LoadBalancer

> Note: This README documents the completed working steps only.
> The final single chained workflow `OpenTofu -> Approval -> Apply -> Ansible Deployment` is not included here because that orchestration is a separate remaining task.

---

# 2. Final Architecture

```text
Developer Laptop
      |
      v
OpenSible UI
      |
      +--------------------+
      |                    |
      v                    v
OpenSible Server      OpenSible Worker
                           |
                           +-- AWS CLI
                           +-- kubectl
                           +-- Ansible
                           +-- Helm
                           +-- Helmfile
                           +-- Helm Diff
                           |
                           v
                        AWS EKS
                           |
                           v
                Retail Store Sample App
                           |
                           v
                    AWS LoadBalancer
                           |
                           v
                     Browser Access
```

---

# 3. Project Structure

Final working directory layout:

```text
~/opensible/
├── ansible/
│   ├── deploy.yml
│   ├── inventory.yml
│   └── roles/
│
├── custom-worker/
│   └── Dockerfile
│
├── retail-store-sample-app/
│   └── src/
│       ├── app/
│       │   ├── chart/
│       │   ├── helmfile.yaml
│       │   └── helmfile.slim.yaml
│       ├── ui/
│       ├── orders/
│       ├── catalog/
│       ├── checkout/
│       └── cart/
│
├── IaC/
├── server/
├── worker/
├── console/
├── ssh-keys/
├── docker-compose.yml
└── .env
```

---

# 4. Prerequisites

Install the following on the host machine:

```bash
docker --version
docker compose version
aws --version
kubectl version --client
git --version
```

AWS credentials must be configured on the host:

```bash
aws configure
```

Verify:

```bash
aws sts get-caller-identity
```

Expected output format:

```json
{
  "UserId": "...",
  "Account": "<AWS_ACCOUNT_ID>",
  "Arn": "arn:aws:iam::<AWS_ACCOUNT_ID>:user/<IAM_USER>"
}
```

---

# 5. Clone OpenSible

```bash
cd ~
git clone https://github.com/opensible/opensible.git
cd ~/opensible
```

If OpenSible was obtained from another source/repository, use that repository instead.

---

# 6. Prepare OpenSible Environment Secrets

Create/update:

```bash
nano ~/opensible/.env
```

Generate secure secrets:

```bash
openssl rand -hex 32
```

Use separately generated values for:

```env
JWT_SECRET_KEY=<generated-value>
INTERNAL_CALL_SECRET=<generated-value>
GLOBAL_SECRETS_ENCRYPTION_KEY=<generated-value>
WORKER_REGISTRATION_SECRET=<generated-value>
```

Do not commit `.env` to Git.

---

# 7. Create Custom OpenSible Worker

Create:

```text
~/opensible/custom-worker/Dockerfile
```

Use:

```dockerfile
FROM docker.io/ossopensible/opensible-worker:latest

USER root

RUN apt-get update && \
    apt-get install -y \
      ansible \
      curl \
      unzip \
      git \
      jq \
      ca-certificates \
      gnupg \
      tar \
      gzip && \
    rm -rf /var/lib/apt/lists/*

# --------------------------------------------------
# AWS CLI v2
# --------------------------------------------------

RUN curl -fsSL \
    "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" \
    -o /tmp/awscliv2.zip && \
    unzip -q /tmp/awscliv2.zip -d /tmp && \
    /tmp/aws/install && \
    rm -rf /tmp/aws /tmp/awscliv2.zip

# --------------------------------------------------
# kubectl
# --------------------------------------------------

RUN KUBECTL_VERSION="$(curl -L -s https://dl.k8s.io/release/stable.txt)" && \
    curl -fsSL \
    "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    -o /usr/local/bin/kubectl && \
    chmod +x /usr/local/bin/kubectl

# --------------------------------------------------
# Helm
# --------------------------------------------------

RUN HELM_VERSION="v3.18.6" && \
    curl -fsSL \
    "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz" \
    -o /tmp/helm.tar.gz && \
    tar -xzf /tmp/helm.tar.gz -C /tmp && \
    mv /tmp/linux-amd64/helm /usr/local/bin/helm && \
    chmod +x /usr/local/bin/helm && \
    rm -rf /tmp/linux-amd64 /tmp/helm.tar.gz

# --------------------------------------------------
# Helmfile
# --------------------------------------------------

RUN HELMFILE_VERSION="0.171.0" && \
    curl -fsSL \
    "https://github.com/helmfile/helmfile/releases/download/v${HELMFILE_VERSION}/helmfile_${HELMFILE_VERSION}_linux_amd64.tar.gz" \
    -o /tmp/helmfile.tar.gz && \
    tar -xzf /tmp/helmfile.tar.gz -C /tmp && \
    mv /tmp/helmfile /usr/local/bin/helmfile && \
    chmod +x /usr/local/bin/helmfile && \
    rm -f /tmp/helmfile.tar.gz

# --------------------------------------------------
# Helm Diff Plugin
# --------------------------------------------------

RUN helm plugin install https://github.com/databus23/helm-diff

# --------------------------------------------------
# Tool Verification
# --------------------------------------------------

RUN aws --version && \
    kubectl version --client && \
    ansible-playbook --version && \
    helm version && \
    helmfile --version && \
    helm diff version
```

---

# 8. Docker Compose Configuration

Use the following `docker-compose.yml`:

```yaml
services:
  opensible-server:
    image: docker.io/ossopensible/opensible-server:latest
    container_name: opensible-server
    restart: unless-stopped

    ports:
      - "5000:5000"

    volumes:
      - opensible-data:/app/data
      - ./ssh-keys:/root/.ssh:ro

    environment:
      TZ: Asia/Phnom_Penh
      FLASK_ENV: production
      DATA_DIR: /app/data

      JWT_SECRET_KEY: ${JWT_SECRET_KEY:-${JWT_SECRET}}
      JWT_SECRET: ${JWT_SECRET:-${JWT_SECRET_KEY}}
      INTERNAL_CALL_SECRET: ${INTERNAL_CALL_SECRET}
      GLOBAL_SECRETS_ENCRYPTION_KEY: ${GLOBAL_SECRETS_ENCRYPTION_KEY}

      WORKER_REGISTRATION_SECRET: ${WORKER_REGISTRATION_SECRET:-}
      ADMIN_INITIAL_PASSWORD: ${ADMIN_INITIAL_PASSWORD:-}

      CORS_ALLOWED_ORIGINS: ${CORS_ALLOWED_ORIGINS:-http://localhost:8089}

  opensible-console:
    image: docker.io/ossopensible/opensible-console:latest
    container_name: opensible-console
    restart: unless-stopped

    ports:
      - "8089:80"

    environment:
      TZ: Asia/Phnom_Penh
      API_URL: ""
      BACKEND_HOST: opensible-server
      BACKEND_PORT: "5000"

    depends_on:
      - opensible-server

  opensible-worker:
    build:
      context: ./custom-worker
      dockerfile: Dockerfile

    image: opensible-worker-eks:local
    container_name: opensible-worker
    restart: unless-stopped

    network_mode: host

    volumes:
      - opensible-data:/app/data
      - ./ssh-keys:/root/.ssh:ro

      # AWS credentials
      - /home/einfochips/.aws:/root/.aws:ro

      # Kubernetes kubeconfig
      - /home/einfochips/.kube:/root/.kube

      # Main OpenSible workspace
      - ./:/workspace/opensible

    environment:
      TZ: Asia/Phnom_Penh

      WORKER_NAME: worker-go
      WORKER_TAGS: go,aws,eks,kubernetes,helm,helmfile

      WORKER_SERVER_URL: http://127.0.0.1:5000
      WORKER_TOKEN_FILE: /app/data/worker.token
      DATA_DIR: /app/data

      WORKER_REGISTRATION_SECRET: ${WORKER_REGISTRATION_SECRET:-}
      WORKER_MAX_CONCURRENCY: ${WORKER_MAX_CONCURRENCY:-3}

      VAULT_SERVER_HOST: 127.0.0.1
      VAULT_SERVER_PORT: "9998"
      VAULT_SERVER_SECRET: ${VAULT_SERVER_SECRET:-}

      AWS_REGION: ap-south-1
      AWS_DEFAULT_REGION: ap-south-1
      AWS_PAGER: ""

      KUBECONFIG: /root/.kube/config

    depends_on:
      - opensible-server

volumes:
  opensible-data:
```

---

# 9. Validate Docker Compose

```bash
cd ~/opensible

docker compose config > /dev/null && echo "Compose OK"
```

Expected:

```text
Compose OK
```

---

# 10. Build Custom Worker

```bash
cd ~/opensible

docker compose build --no-cache opensible-worker
```

---

# 11. Start OpenSible

```bash
docker compose up -d
```

Check:

```bash
docker compose ps
```

Expected containers:

```text
opensible-server
opensible-console
opensible-worker
```

Open the UI:

```text
http://localhost:8089
```

---

# 12. Verify OpenSible Worker Tooling

AWS CLI:

```bash
docker exec -it opensible-worker aws --version
```

kubectl:

```bash
docker exec -it opensible-worker kubectl version --client
```

Ansible:

```bash
docker exec -it opensible-worker ansible-playbook --version
```

Helm:

```bash
docker exec -it opensible-worker helm version
```

Helmfile:

```bash
docker exec -it opensible-worker helmfile --version
```

Helm Diff:

```bash
docker exec -it opensible-worker helm diff version
```

---

# 13. Verify AWS Credentials Inside Worker

```bash
docker exec -it opensible-worker \
  aws sts get-caller-identity
```

The command must return the expected AWS account and IAM identity.

---

# 14. Create EKS Infrastructure from OpenSible

Open:

```text
OpenSible UI
→ Cloud Provisioning
→ Cloud Stack
```

Create/configure the stack with:

```text
Provider      : Amazon EKS
Stack Name    : retail-store-eks
Cloud Project : retail-store
Environment   : dev
Region        : ap-south-1
```

Use the stack lifecycle actions:

```text
Init
Validate
Plan
Apply
```

Wait until Apply succeeds.

The completed stack provisions the AWS infrastructure required for EKS.

---

# 15. Configure kubeconfig

From the host:

```bash
aws eks update-kubeconfig \
  --region ap-south-1 \
  --name retail-store-dev-eks
```

Verify:

```bash
kubectl get nodes
```

Expected:

```text
NAME                                         STATUS
ip-xx-xx-xx-xx.ap-south-1.compute.internal  Ready
```

---

# 16. Verify EKS Access from OpenSible Worker

```bash
docker exec -it opensible-worker \
  kubectl get nodes
```

The worker must see the same EKS node.

---

# 17. Clone Retail Store Sample Application

```bash
cd ~/opensible

git clone https://github.com/aws-containers/retail-store-sample-app.git
```

Application deployment assets are available under:

```text
~/opensible/retail-store-sample-app/src/app
```

Important files:

```text
src/app/helmfile.yaml
src/app/helmfile.slim.yaml

src/ui/chart/
src/orders/chart/
src/catalog/chart/
src/checkout/chart/
src/cart/chart/
```

---

# 18. Expose the UI with an AWS LoadBalancer

Edit:

```text
~/opensible/retail-store-sample-app/src/ui/chart/values.yaml
```

Set:

```yaml
service:
  type: LoadBalancer
  port: 80
```

This causes the UI Helm release to create a Kubernetes `LoadBalancer` service.

---

# 19. Create Ansible Inventory

Create:

```text
~/opensible/inventory.yml
```

Use:

```yaml
all:
  children:
    local:
      hosts:
        localhost:
          ansible_connection: local
```

Verify:

```bash
cat ~/opensible/inventory.yml
```

---

# 20. Create the Application Deployment Playbook

Create:

```text
~/opensible/ansible/deploy.yml
```

Use:

```yaml
---
- name: Deploy Retail Store application to Amazon EKS
  hosts: local
  connection: local
  gather_facts: false

  vars:
    aws_region: ap-south-1
    eks_cluster_name: retail-store-dev-eks
    retail_namespace: default
    app_dir: /workspace/opensible/retail-store-sample-app/src/app

  tasks:
    - name: Verify AWS identity
      ansible.builtin.command:
        cmd: aws sts get-caller-identity --no-cli-pager
      register: aws_identity
      changed_when: false

    - name: Display AWS identity
      ansible.builtin.debug:
        var: aws_identity.stdout_lines

    - name: Update EKS kubeconfig
      ansible.builtin.command:
        cmd: >
          aws eks update-kubeconfig
          --region {{ aws_region }}
          --name {{ eks_cluster_name }}
      changed_when: false

    - name: Verify EKS nodes
      ansible.builtin.command:
        cmd: kubectl get nodes
      register: eks_nodes
      changed_when: false

    - name: Display EKS nodes
      ansible.builtin.debug:
        var: eks_nodes.stdout_lines

    - name: Verify Helm
      ansible.builtin.command:
        cmd: helm version
      changed_when: false

    - name: Verify Helmfile
      ansible.builtin.command:
        cmd: helmfile --version
      changed_when: false

    - name: Verify Helm Diff plugin
      ansible.builtin.command:
        cmd: helm diff version
      changed_when: false

    - name: Verify Retail Store Helmfile exists
      ansible.builtin.stat:
        path: "{{ app_dir }}/helmfile.yaml"
      register: retail_helmfile

    - name: Fail if Retail Store Helmfile is missing
      ansible.builtin.fail:
        msg: "Retail Store helmfile.yaml not found at {{ app_dir }}"
      when: not retail_helmfile.stat.exists

    - name: Deploy Retail Store using Helmfile
      ansible.builtin.command:
        cmd: helmfile apply
        chdir: "{{ app_dir }}"
      register: helmfile_result

    - name: Display Helmfile deployment output
      ansible.builtin.debug:
        var: helmfile_result.stdout_lines

    - name: Wait for Retail Store deployments
      ansible.builtin.command:
        cmd: >
          kubectl wait
          -n {{ retail_namespace }}
          --for=condition=available
          deployment
          --all
          --timeout=15m
      changed_when: false

    - name: Get Retail Store deployments
      ansible.builtin.command:
        cmd: kubectl get deployments -n {{ retail_namespace }}
      register: retail_deployments
      changed_when: false

    - name: Display Retail Store deployments
      ansible.builtin.debug:
        var: retail_deployments.stdout_lines

    - name: Get Retail Store pods
      ansible.builtin.command:
        cmd: kubectl get pods -n {{ retail_namespace }}
      register: retail_pods
      changed_when: false

    - name: Display Retail Store pods
      ansible.builtin.debug:
        var: retail_pods.stdout_lines

    - name: Get Retail Store services
      ansible.builtin.command:
        cmd: kubectl get svc -n {{ retail_namespace }}
      register: retail_services
      changed_when: false

    - name: Display Retail Store services
      ansible.builtin.debug:
        var: retail_services.stdout_lines

    - name: Wait for Retail Store UI LoadBalancer hostname
      ansible.builtin.command:
        argv:
          - kubectl
          - get
          - svc
          - ui
          - -n
          - "{{ retail_namespace }}"
          - -o
          - "jsonpath={.status.loadBalancer.ingress[0].hostname}"
      register: ui_hostname
      changed_when: false
      retries: 60
      delay: 10
      until: ui_hostname.stdout | trim | length > 0

    - name: Display Retail Store application URL
      ansible.builtin.debug:
        msg: "Retail Store URL: http://{{ ui_hostname.stdout }}"
```

---

# 21. Run the Application Deployment

Execute the playbook from the OpenSible worker:

```bash
docker exec -it opensible-worker \
  ansible-playbook \
  -i /workspace/opensible/inventory.yml \
  /workspace/opensible/ansible/deploy.yml
```

Expected final result:

```text
PLAY RECAP
localhost : ok=... changed=... unreachable=0 failed=0
```

---

# 22. Verify Deployments

```bash
kubectl get deployments -n default
```

Expected application deployments include:

```text
carts
carts-dynamodb
catalog
checkout
checkout-redis
orders
ui
```

---

# 23. Verify Pods

```bash
kubectl get pods -n default
```

Expected workloads include:

```text
carts
carts-dynamodb
catalog
catalog-mysql
checkout
checkout-redis
orders
orders-postgresql
orders-rabbitmq
ui
```

All pods should eventually be:

```text
READY   STATUS
1/1     Running
```

---

# 24. Verify Kubernetes Services

```bash
kubectl get svc -n default
```

Application backend services should be `ClusterIP`.

The UI service should be:

```text
ui   LoadBalancer
```

---

# 25. Get Application LoadBalancer URL

```bash
kubectl get svc ui \
  -n default \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}{"\n"}'
```

Example format:

```text
xxxxxxxxxxxxxxxx.ap-south-1.elb.amazonaws.com
```

Access:

```text
http://xxxxxxxxxxxxxxxx.ap-south-1.elb.amazonaws.com
```

---

# 26. Verify LoadBalancer

```bash
kubectl describe svc ui -n default
```

Optional AWS verification:

```bash
aws elbv2 describe-load-balancers \
  --region ap-south-1 \
  --query 'LoadBalancers[*].[LoadBalancerName,DNSName,State.Code,Scheme,Type]' \
  --output table
```

---

# 27. Verify OpenSible Worker Mounts

```bash
docker inspect opensible-worker \
  --format '{{json .Mounts}}' | jq
```

Important mounts should include:

```text
/root/.aws
/root/.kube
/workspace/opensible
/app/data
/root/.ssh
```

---

# 28. Restart OpenSible After Laptop Reboot

OpenSible installation is persistent. It does not need to be reinstalled after every reboot.

Start it again with:

```bash
cd ~/opensible

docker compose up -d
```

Verify:

```bash
docker compose ps
```

Access the UI:

```text
http://localhost:8089
```

---

# 29. Final Verification Commands

Run:

```bash
docker exec -it opensible-worker aws sts get-caller-identity
```

```bash
docker exec -it opensible-worker kubectl get nodes
```

```bash
docker exec -it opensible-worker helm version
```

```bash
docker exec -it opensible-worker helmfile --version
```

```bash
docker exec -it opensible-worker helm diff version
```

```bash
kubectl get deployments -n default
```

```bash
kubectl get pods -n default
```

```bash
kubectl get svc -n default
```

```bash
kubectl get svc ui \
  -n default \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}{"\n"}'
```

---

# 30. Completed Workflow

The completed working deployment flow is:

```text
OpenSible Installation
        |
        v
Custom OpenSible Worker
        |
        +-- AWS CLI
        +-- kubectl
        +-- Ansible
        +-- Helm
        +-- Helmfile
        +-- Helm Diff
        |
        v
AWS Authentication
        |
        v
OpenSible Cloud Stack
        |
        v
OpenTofu
        |
        +-- Init
        +-- Validate
        +-- Plan
        +-- Apply
        |
        v
Amazon EKS
        |
        v
EKS Node Ready
        |
        v
Ansible deploy.yml
        |
        v
Helmfile Apply
        |
        v
Retail Store Helm Charts
        |
        v
Retail Store Kubernetes Workloads
        |
        v
UI LoadBalancer
        |
        v
Application Accessible
```

---

# 31. Completed Status

| Component                           | Status    |
| ----------------------------------- | --------- |
| OpenSible Docker installation       | Completed |
| OpenSible Server                    | Completed |
| OpenSible Console                   | Completed |
| Custom OpenSible Worker             | Completed |
| AWS CLI in Worker                   | Completed |
| AWS Credentials in Worker           | Completed |
| kubectl in Worker                   | Completed |
| Ansible in Worker                   | Completed |
| Helm in Worker                      | Completed |
| Helmfile in Worker                  | Completed |
| Helm Diff Plugin                    | Completed |
| OpenTofu/OpenSible EKS provisioning | Completed |
| EKS Cluster                         | Completed |
| EKS Worker Node                     | Completed |
| kubeconfig                          | Completed |
| Retail Store repository             | Completed |
| Helmfile application deployment     | Completed |
| Retail Store Pods                   | Running   |
| Retail Store Services               | Running   |
| UI LoadBalancer configuration       | Completed |
| Application deployment verification | Completed |

---

# 32. Remaining Separate Enhancement

The following is intentionally not included as a completed item in this README:

```text
Single OpenSible Workflow
        |
        v
OpenTofu Init
        |
        v
Validate
        |
        v
Plan
        |
        v
Manual Approval
        |
        v
Apply
        |
        v
Ansible Deployment
        |
        v
Application URL in OpenSible UI
```

* [ ] That is the next orchestration phase after the completed EKS + application deployment implementation documented above.

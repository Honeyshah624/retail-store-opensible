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

#--------------------------------------------------
# Helm Diff Plugin - required by Helmfile apply
# --------------------------------------------------
RUN helm plugin install https://github.com/databus23/helm-diff


# --------------------------------------------------
# Verification
# --------------------------------------------------
RUN aws --version && \
    kubectl version --client && \
    ansible-playbook --version && \
    helm version && \
    helmfile --version && \
    helm diff version

# --------------------------------------------
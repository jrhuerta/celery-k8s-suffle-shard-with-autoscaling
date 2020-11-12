sudo apt-get update -q -y \
  && sudo apt-get upgrade -q -y \
  && sudo apt-get install -y docker.io \
  && sudo usermod -aG docker $USER \
  && curl -LO "https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl" \
  && sudo install ./kubectl /usr/local/bin \
  && sudo bash -c "/usr/local/bin/kubectl completion bash > /etc/bash_completion.d/kubectl" \
  && curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64 \
  && sudo install ./minikube-linux-amd64 /usr/local/bin/minikube \
  && sudo bash -c "/usr/local/bin/minikube completion bash > /etc/bash_completion.d/minikube"
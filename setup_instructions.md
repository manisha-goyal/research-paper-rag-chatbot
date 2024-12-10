# Research Paper RAG Chatbot - Setup Documentation

This document outlines the steps to set up and deploy the Research Paper RAG Chatbot using Google Cloud Platform (GCP) and Kubernetes.

---

## **Prerequisites**

1. **Install Required Tools**:
   - Docker: [Install Docker](https://docs.docker.com/get-docker/)
   - Google Cloud CLI: [Install gcloud](https://cloud.google.com/sdk/docs/install)

2. **Authenticate with GCP**:
   ```bash
   gcloud auth login
   gcloud config set project research-chatbot
   ```
---

## **Step 1: Build and Push RAG Chatbot Docker Image**

```bash
docker tag rag-chatbot:latest gcr.io/research-chatbot/rag-chatbot:latest
docker push gcr.io/research-chatbot/rag-chatbot:latest
```
---

## **Step 2: Enable Required GCP Services**

Enable necessary GCP APIs for the project:

```bash
gcloud services enable artifactregistry.googleapis.com container.googleapis.com iamcredentials.googleapis.com
```

---

## **Step 3: Configure Kubernetes Cluster**

### **3.1 Install kubectl**

```bash
gcloud components install kubectl
```

### **3.2 Get Kubernetes Cluster Credentials**

```bash
gcloud container clusters get-credentials rag-cluster --zone us-central1
```

### **3.3 Create Secrets in Kubernetes**

```bash
kubectl create secret generic app-secrets --from-env-file=.env
```

### **3.4 Deploy the Application**

Apply the Kubernetes deployment configuration:

```bash
kubectl apply -f k8s/chatbot-deployment.yaml
```

---

## **Step 4: Configure Workload Identity for GitHub Actions**

### **4.1 Create Workload Identity Pool and Provider**

#### Create the Pool:

```bash
gcloud iam workload-identity-pools create my-pool \  
    --project="research-chatbot" \  
    --location="global" \  
    --display-name="My GitHub Pool"
```

#### Create the Provider:

```bash
gcloud iam workload-identity-pools providers create-oidc my-provider \  
    --project="research-chatbot" \  
    --location="global" \  
    --workload-identity-pool="my-pool" \  
    --display-name="My GitHub Provider" \  
    --issuer-uri="https://token.actions.githubusercontent.com" \  
    --allowed-audiences="https://github.com/google-github-actions/auth" \  
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.workflow=assertion.workflow" \  
    --attribute-condition="assertion.repository_owner=='manisha-goyal'"
```

### **4.2 Add IAM Policy Bindings**

Grant permissions for the Workload Identity Pool to interact with required GCP resources:

```bash
gcloud projects add-iam-policy-binding research-chatbot \  
    --member="principalSet://iam.googleapis.com/projects/$(gcloud projects describe research-chatbot --format='value(projectNumber)')/locations/global/workloadIdentityPools/my-pool/attribute.repository/manisha-goyal/research-paper-rag-chatbot" \  
    --role="roles/container.admin"
```

```bash
gcloud projects add-iam-policy-binding research-chatbot \  
    --member="principalSet://iam.googleapis.com/projects/750926710219/locations/global/workloadIdentityPools/my-pool/attribute.repository/manisha-goyal/research-paper-rag-chatbot" \  
    --role="roles/artifactregistry.writer"
```

---

## **Step 5: Grant Artifact Registry Permissions**

Grant the Workload Identity Pool permissions to read and write from the Artifact Registry:

```bash
gcloud artifacts repositories add-iam-policy-binding ragregistry \  
    --location=us-central1 \  
    --member="principalSet://iam.googleapis.com/projects/750926710219/locations/global/workloadIdentityPools/my-pool/attribute.repository/manisha-goyal/research-paper-rag-chatbot" \  
    --role="roles/artifactregistry.reader"
```
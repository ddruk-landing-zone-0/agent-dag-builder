export GCP_PROJECT_ID="sample-project-0-455918" # Write it properly after seeing the dashboard
export SERVICE_AC_DISPLAYNAME="sample-project-0-sa"
export BUCKET_NAME="bucket-agent-builder-001" # Make bucket name unique
export GAR_REPOSITORY_ID="gar-agent-builder"
export GAR_LOCATION="us-central1"


gcloud components update
gcloud auth login
gcloud config set project $GCP_PROJECT_ID


gcloud iam service-accounts create $SERVICE_AC_DISPLAYNAME --display-name $SERVICE_AC_DISPLAYNAME


gcloud services enable cloudresourcemanager.googleapis.com \
    artifactregistry.googleapis.com \
    iam.googleapis.com \
    run.googleapis.com \
    storage.googleapis.com \
    aiplatform.googleapis.com \
    --project=$GCP_PROJECT_ID


for role in resourcemanager.projectIamAdmin \
            iam.serviceAccountUser \
            run.admin \
            artifactregistry.writer \
            artifactregistry.reader \
            artifactregistry.admin \
            storage.admin \
            storage.objectAdmin \
            storage.objectViewer \
            storage.objectCreator \
            aiplatform.admin \
            aiplatform.user \
            aiplatform.viewer; do
    gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
        --member=serviceAccount:$SERVICE_AC_DISPLAYNAME@$GCP_PROJECT_ID.iam.gserviceaccount.com \
        --role=roles/$role
done


gcloud storage buckets create gs://$BUCKET_NAME --location=US --uniform-bucket-level-access


gcloud artifacts repositories create $GAR_REPOSITORY_ID \
    --project=$GCP_PROJECT_ID \
    --location=$GAR_LOCATION \
    --repository-format=docker \
    --description="Docker repository for Python server"

gcloud iam service-accounts keys create key.json \
    --iam-account=$SERVICE_AC_DISPLAYNAME@$GCP_PROJECT_ID.iam.gserviceaccount.com




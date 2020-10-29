pipeline {
    agent {
        label 'dockerbuild'
    }
    options { disableConcurrentBuilds() }
    stages {
        stage("Checkout Cloudlift; get latest hash") {
            steps {
                println params
                sh '''
                    git remote set-url origin git@github.com:Rippling/cloudlift || git remote add origin git@github.com:Rippling/cloudlift
                    if ! [ -z "${COMMIT_ID}" ]; then
                        echo "Checking out custom commit id: ${COMMIT_ID}"
                        git checkout ${COMMIT_ID}
                    fi
                    git fetch --prune origin "+refs/tags/*:refs/tags/*"
                    echo "Tagging this commit: $(git rev-parse HEAD)"
                    HASH=$(git rev-parse HEAD)
                    echo $HASH > latest.txt
                '''
            }
        }
        
        stage("Build Docker Image") {
            steps {
                sh '''
                    HASH=$(cat latest.txt)
                    docker build -t cloudlift:${HASH} .
                    FOUND_TAG=v$(docker run cloudlift:${HASH} "--version" | awk '{ print $3}')
                    echo $FOUND_TAG > tag.txt
                    git tag ${FOUND_TAG}
                    git push origin refs/tags/${FOUND_TAG}
                    echo "List of git tag:\n$(git tag -l)"
                    docker tag cloudlift:${HASH} cloudlift:${FOUND_TAG} .
                '''
            }
        }
        
        stage('Push to ECR') {
            steps {
                sh '''
                    FOUND_TAG=$(cat tag.txt)
                    echo "${FOUND_TAG} is being pushed to ECR"
                    aws ecr get-login-password --region ${AWS_DEFAULT_REGION} | docker login --username AWS --password-stdin ${AWS_RIPPLING_ACCOUNT}
                    docker tag cloudlift:${FOUND_TAG} ${AWS_RIPPLING_ACCOUNT}/cloudlift-repo:${FOUND_TAG}
                    docker push ${AWS_RIPPLING_ACCOUNT}/cloudlift-repo:${FOUND_TAG}
                '''
            }
        }
    }
}

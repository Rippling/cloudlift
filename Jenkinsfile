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
                '''
            }
        }
        
        stage("Build Docker Image") {
            steps {
                sh '''
                    docker build -t cloudlift:build .
                '''
                script {
                    def VERSION = sh(
                        returnStdout: true,
                        script: '''
                            VERSION=$(docker run cloudlift:build '--version' || echo failed)
                            if [ -z "${VERSION}" ]; then
                                echo "No tag found"
                            exit 1
                            fi
                            echo ${VERSION}
                        '''
                    )
                }
            }
        }
        stage('Tag git') {
            steps {
                sh '''
                    echo "${VERSION}"
                    FOUND_TAG=$(echo ${VERSION} | awk '{ print $3 }')
                    git tag ${FOUND_TAG}
                    git push origin refs/tags/${FOUND_TAG}
                    echo "List of git tag:\n$(git tag -l)"
                '''
            }
        }
        stage('Push to ECR') {
            steps {
                sh '''
                    echo "v${FOUND_TAG} is being pushed to ECR"
                    aws ecr get-login-password --region ${AWS_DEFAULT_REGION} | docker login --username AWS --password-stdin ${AWS_RIPPLING_ACCOUNT}
                    docker tag cloudlift:v${FOUND_TAG} ${AWS_RIPPLING_ACCOUNT}/cloudlift-repo:v${FOUND_TAG}
                    docker push ${AWS_RIPPLING_ACCOUNT}/cloudlift-repo:v${FOUND_TAG}
                '''
            }
        }
    }
}

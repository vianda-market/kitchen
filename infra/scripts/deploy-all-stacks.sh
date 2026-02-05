#!/bin/bash
set -e

################################################################################
# Kitchen Infrastructure Deployment Script
# Deploys all CloudFormation stacks in the correct order
################################################################################

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-dev}
REGION=${AWS_REGION:-us-east-1}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLOUDFORMATION_DIR="$SCRIPT_DIR/../cloudformation"
PARAMETERS_FILE="$CLOUDFORMATION_DIR/parameters/${ENVIRONMENT}.json"

# Stack names
NETWORK_STACK="kitchen-network-${ENVIRONMENT}"
DATABASE_STACK="kitchen-database-${ENVIRONMENT}"
SECRETS_STACK="kitchen-secrets-${ENVIRONMENT}"
COMPUTE_STACK="kitchen-compute-${ENVIRONMENT}"
ALB_STACK="kitchen-loadbalancer-${ENVIRONMENT}"

################################################################################
# Functions
################################################################################

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

wait_for_stack() {
    local stack_name=$1
    local action=$2
    
    print_info "Waiting for stack ${stack_name} to ${action}..."
    
    aws cloudformation wait stack-${action}-complete \
        --stack-name "$stack_name" \
        --region "$REGION"
    
    if [ $? -eq 0 ]; then
        print_success "Stack ${stack_name} ${action}d successfully"
    else
        print_error "Stack ${stack_name} failed to ${action}"
        exit 1
    fi
}

deploy_stack() {
    local stack_name=$1
    local template_file=$2
    local parameters_file=$3
    
    print_info "Deploying stack: ${stack_name}"
    print_info "Template: ${template_file}"
    print_info "Parameters: ${parameters_file}"
    
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name "$stack_name" --region "$REGION" >/dev/null 2>&1; then
        print_info "Stack exists. Updating..."
        
        aws cloudformation update-stack \
            --stack-name "$stack_name" \
            --template-body "file://${template_file}" \
            --parameters "file://${parameters_file}" \
            --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
            --region "$REGION" || true
        
        # Check if update was successful or no changes needed
        UPDATE_STATUS=$?
        if [ $UPDATE_STATUS -eq 0 ]; then
            wait_for_stack "$stack_name" "update"
        else
            print_info "No changes to update or update failed"
        fi
    else
        print_info "Stack does not exist. Creating..."
        
        aws cloudformation create-stack \
            --stack-name "$stack_name" \
            --template-body "file://${template_file}" \
            --parameters "file://${parameters_file}" \
            --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
            --region "$REGION"
        
        wait_for_stack "$stack_name" "create"
    fi
}

get_stack_output() {
    local stack_name=$1
    local output_key=$2
    
    aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?OutputKey=='${output_key}'].OutputValue" \
        --output text
}

################################################################################
# Main Deployment
################################################################################

print_header "Kitchen Infrastructure Deployment"
print_info "Environment: ${ENVIRONMENT}"
print_info "Region: ${REGION}"
print_info "Parameters file: ${PARAMETERS_FILE}"

# Validate parameters file exists
if [ ! -f "$PARAMETERS_FILE" ]; then
    print_error "Parameters file not found: ${PARAMETERS_FILE}"
    exit 1
fi

# Prompt for confirmation in production
if [ "$ENVIRONMENT" == "prod" ]; then
    print_info "You are about to deploy to PRODUCTION. Are you sure? (yes/no)"
    read -r confirmation
    if [ "$confirmation" != "yes" ]; then
        print_info "Deployment cancelled"
        exit 0
    fi
fi

# Step 1: Deploy Network Stack
print_header "Step 1: Deploying Network Infrastructure"
deploy_stack "$NETWORK_STACK" \
    "$CLOUDFORMATION_DIR/01-network.yml" \
    "$PARAMETERS_FILE"

# Step 2: Deploy Database Stack
print_header "Step 2: Deploying Database (RDS)"
# Add NetworkStackName parameter
TMP_PARAMS=$(mktemp)
jq ". + [{\"ParameterKey\": \"NetworkStackName\", \"ParameterValue\": \"${NETWORK_STACK}\"}]" "$PARAMETERS_FILE" > "$TMP_PARAMS"
deploy_stack "$DATABASE_STACK" \
    "$CLOUDFORMATION_DIR/02-rds.yml" \
    "$TMP_PARAMS"
rm "$TMP_PARAMS"

# Get database endpoint
DB_ENDPOINT=$(get_stack_output "$DATABASE_STACK" "DBInstanceEndpoint")
print_success "Database endpoint: ${DB_ENDPOINT}"

# Step 3: Deploy Secrets Stack
print_header "Step 3: Deploying Secrets Manager"
TMP_PARAMS=$(mktemp)
jq ". + [{\"ParameterKey\": \"DatabaseStackName\", \"ParameterValue\": \"${DATABASE_STACK}\"}]" "$PARAMETERS_FILE" > "$TMP_PARAMS"
deploy_stack "$SECRETS_STACK" \
    "$CLOUDFORMATION_DIR/03-secrets.yml" \
    "$TMP_PARAMS"
rm "$TMP_PARAMS"

print_info "⚠️  IMPORTANT: Update secrets with real values:"
print_info "   aws secretsmanager update-secret --secret-id kitchen/${ENVIRONMENT}/database/credentials --secret-string '{...}'"
print_info "   aws secretsmanager update-secret --secret-id kitchen/${ENVIRONMENT}/backend/api-keys --secret-string '{...}'"
print_info "   aws secretsmanager update-secret --secret-id kitchen/${ENVIRONMENT}/email/config --secret-string '{...}'"

# Step 4: Deploy Compute Stack (EC2)
print_header "Step 4: Deploying Compute (EC2)"
TMP_PARAMS=$(mktemp)
jq ". + [{\"ParameterKey\": \"NetworkStackName\", \"ParameterValue\": \"${NETWORK_STACK}\"}, \
         {\"ParameterKey\": \"SecretsStackName\", \"ParameterValue\": \"${SECRETS_STACK}\"}]" "$PARAMETERS_FILE" > "$TMP_PARAMS"
deploy_stack "$COMPUTE_STACK" \
    "$CLOUDFORMATION_DIR/04-ec2.yml" \
    "$TMP_PARAMS"
rm "$TMP_PARAMS"

# Get EC2 public IP
PUBLIC_IP=$(get_stack_output "$COMPUTE_STACK" "PublicIP")
print_success "EC2 Public IP: ${PUBLIC_IP}"

# Step 5: Deploy ALB Stack
print_header "Step 5: Deploying Application Load Balancer"
TMP_PARAMS=$(mktemp)
jq ". + [{\"ParameterKey\": \"NetworkStackName\", \"ParameterValue\": \"${NETWORK_STACK}\"}, \
         {\"ParameterKey\": \"ComputeStackName\", \"ParameterValue\": \"${COMPUTE_STACK}\"}]" "$PARAMETERS_FILE" > "$TMP_PARAMS"
deploy_stack "$ALB_STACK" \
    "$CLOUDFORMATION_DIR/05-alb.yml" \
    "$TMP_PARAMS"
rm "$TMP_PARAMS"

# Get ALB DNS
ALB_DNS=$(get_stack_output "$ALB_STACK" "LoadBalancerDNS")
print_success "ALB DNS: ${ALB_DNS}"

################################################################################
# Deployment Summary
################################################################################

print_header "Deployment Complete!"

echo ""
echo -e "${GREEN}All stacks deployed successfully!${NC}"
echo ""
echo "📋 Stack Summary:"
echo "  - Network Stack:      ${NETWORK_STACK}"
echo "  - Database Stack:     ${DATABASE_STACK}"
echo "  - Secrets Stack:      ${SECRETS_STACK}"
echo "  - Compute Stack:      ${COMPUTE_STACK}"
echo "  - Load Balancer Stack: ${ALB_STACK}"
echo ""
echo "🔗 Access URLs:"
echo "  - Database Endpoint:  ${DB_ENDPOINT}"
echo "  - EC2 Public IP:      http://${PUBLIC_IP}"
echo "  - Load Balancer:      http://${ALB_DNS}"
echo "  - API Endpoint:       http://${ALB_DNS}/api/v1"
echo "  - Health Check:       http://${ALB_DNS}/health"
echo ""
echo "⚠️  Next Steps:"
echo "  1. Update secrets in AWS Secrets Manager with real values"
echo "  2. Apply database schema: psql -h ${DB_ENDPOINT} -U kitchen_admin -d kitchen_db_${ENVIRONMENT} -f app/db/schema.sql"
echo "  3. Test API: curl http://${ALB_DNS}/health"
echo "  4. Configure DNS (optional): Point your domain to ${ALB_DNS}"
echo ""

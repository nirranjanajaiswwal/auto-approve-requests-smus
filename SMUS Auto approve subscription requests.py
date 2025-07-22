import boto3
import json
import logging
import os
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """Lambda function to auto-approve subscription requests in SageMaker Unified Studio"""
    try:
        # Initialize clients
        datazone_client = boto3.client('datazone')
        sns_client = boto3.client('sns')
        
        # Get configuration from environment variables or use hardcoded values
        domain_id = os.environ.get('DOMAIN_ID', 'enter domain')
        project_id = os.environ.get('PROJECT_ID', 'enter owning project')
        sns_topic_arn = os.environ.get('SNS_TOPIC_ARN', 'ARN of SNS topic')
        
        # Get pending subscription requests
        pending_requests = get_pending_requests(datazone_client, domain_id, project_id)
        
        if not pending_requests:
            logger.info("No pending subscription requests found")
            return
        
        # Process requests
        for request in pending_requests:
            approve_request(datazone_client, sns_client, domain_id, request, sns_topic_arn)
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")

def get_pending_requests(client, domain_id, project_id):
    """Get all pending subscription requests"""
    requests = []
    next_token = None
    
    try:
        while True:
            params = {
                'domainIdentifier': domain_id,
                'status': 'PENDING',
                'approverProjectId': project_id
            }
            
            if next_token:
                params['nextToken'] = next_token
            
            response = client.list_subscription_requests(**params)
            
            if 'items' in response:
                requests.extend(response['items'])
            
            next_token = response.get('nextToken')
            if not next_token:
                break
                
        logger.info(f"Found {len(requests)} pending requests")
        return requests
        
    except ClientError as e:
        logger.error(f"Error listing requests: {e}")
        return []

def approve_request(datazone_client, sns_client, domain_id, request, sns_topic_arn):
    """Approve a subscription request and send notification"""
    request_id = request.get('id')
    if not request_id:
        return
        
    try:
        # Approve the request
        datazone_client.accept_subscription_request(
            domainIdentifier=domain_id,
            identifier=request_id,
            decisionComment="Subscription request is auto-approved by Lambda"
        )
        
        # Send notification
        asset_name = request.get('assetName', 'Unknown asset')
        
        message = f"Your subscription request has been auto-approved by Lambda. You can now access this asset."
        
        sns_client.publish(
            TopicArn=sns_topic_arn,
            Subject=f"Subscription Request is auto-approved by Lambda",
            Message=message
        )
        
        logger.info(f"Approved request {request_id} for {asset_name}")
        
    except Exception as e:
        logger.error(f"Error processing request {request_id}: {e}")
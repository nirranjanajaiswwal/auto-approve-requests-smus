# Scale Your Data Governance with Amazon SageMaker Unified Studio by Automating Subscription Approvals
## Introduction
<p> Amazon SageMaker Unified Studio revolutionizes data and AI development by providing a single, integrated environment where organizations can discover, access, and act on data using best-in-class tools across any use case. This unified platform seamlessly integrates functionality from existing AWS Analytics and AI/ML services, including Amazon EMR, AWS Glue, Amazon Athena, Amazon Redshift, Amazon Bedrock, and Amazon SageMaker AI. As enterprise organizations manage thousands of data assets requiring publication to data marketplaces, they face a critical challenge: balancing governance requirements with operational efficiency. While manual approval workflows remains essential for sensitive datasets and production systems, there's growing demand for automated approval capabilities that can accelerate access to lower-risk data assets in non-production environments without compromising governance frameworks.<br>
This solution explores how to implement an event-driven architecture solution that automates subscription request approvals within SageMaker Unified Studio, enabling faster data access while maintaining compliance with established governance standards.<p> 

## Subscription approval in SageMaker Unified Studio
<p> SageMaker Unified Studio provides project owners with granular control over data asset access through configurable subscription requirements. Data producers can easily configure individual assets to require or bypass subscription approval at the asset level.

**Configuration Steps:**
<p> 1.	Access Asset Configuration: Data producers log into the SageMaker Unified Studio console and navigate to their specific project → Assets → Select the target asset for configuration. <br>
2.	Edit Subscription Settings: In the Asset details page, locate the right pane and click 'Edit' on 'Subscription Required'. <p> 

![](/Images/smus1.png) <p>
3.	Apply Configuration: Select the appropriate configuration based on your use case and confirm the changes. <p> 
![](/Images/smus2.png) <p>

## Default Subscription Approval Workflow
The out-of-the-box subscription request and approval process provides comprehensive governance control:
<p> 1.	Request Submission: Data consumers submit subscription requests for desired assets <br>
2.	Thorough Review: Data producers or designated approvers carefully evaluate requests to ensure compliance <br>
3.	Informed Decision: Approvers make well-considered decisions based on established governance policies <br>
4.	Secure Access: Upon approval, requesters gain secure access to the subscribed data assets <p> 

![](/Images/smus3.png) <p>
In the above workflow, automated approvals can accelerate data accessibility for users working with low-risk assets in development environments. <p>

## Event-Driven Architecture Solution

### Technical Architecture Overview
To automate subscription request approvals for lower-risk environments and assets, we implement an event-driven architecture leveraging the following AWS services: <br>

**Core Components:** <br>
**1. Amazon EventBridge:** Provides real-time access to changes in data in AWS services, your own applications and software as a service (SaaS) applications without writing code. In addition to sending messages to your dedicated inbox in the data portal, DataZone also sends these messages to your Amazon EventBridge default event bus in the same AWS account where your Amazon DataZone root domain is hosted. This enables event-driven automation, such as subscription fulfillment or custom integrations with other tools. <br>
**2. AWS Lambda:** Executes serverless code to process subscription events and automatically approve qualifying requests. Lambda's pay-per-use model ensures cost-effectiveness with zero server management overhead. The Lambda function will process incoming subscription request events and automatically approve them based on predefined criteria such as asset classification, requesting user permissions, and environment type. <br>
**3. Amazon Simple Notification Service (SNS):** Delivers immediate notifications to subscribers confirming their subscription approvals through a scalable publish-subscribe messaging paradigm. In this solution, we leverage SNS to send subscriber an email notification confirming their subscription is approved.  <br>
**4. AWS CloudTrail:** Provides comprehensive auditing, security monitoring, and operational troubleshooting capabilities by tracking all user activity and API usage related to the automated approval process. In this solution, we leverage Cloud Trail to access all SageMaker Unified Studio events (that are logged under DataZone) in CloudTrail. <br>

### Subscription fulfilment workflow using Event driven architecture <br>

![](/Images/smus4.png) <p>

### High Level Architecture <br>

![](/Images/smus5.png) <p>

## Implementation Guide
### Prerequisites:
Before implementing the automated approval solution, ensure the following requirements are met: <br>
1.	SageMaker Unified Studio Setup: Projects, domains, and users are properly configured <br>
2.	IAM Role Configuration: Add the following as Contributors in SageMaker Unified Studio Projects: <br> 
o	Lambda execution role  <br>
o	DataZone user role (derived from Project ARN)  <br>
3.	Lambda Permissions: Configure appropriate IAM permissions for the Lambda execution role.  <br>
```
{
	"Version": "2012-10-17",
	"Statement": [
		{
			"Effect": "Allow",
			"Action": [
				"datazone:ListSubscriptionRequests",
				"datazone:AcceptSubscriptionRequest",
				"datazone:GetSubscriptionRequestDetails",
				"datazone:GetDomain",
				"datazone:ListProjects"
			],
			"Resource": "*"
		},
		{
			"Effect": "Allow",
			"Action": "sts:AssumeRole",
			"Resource": "arn:aws:iam::*:role/AmazonDataZone*"
		},
		{
			"Effect": "Allow",
			"Action": [
				"sns:Publish"
			],
			"Resource": [
				"arn:aws:sns:*:*:data-owner-topic",
				"arn:aws:sns:*:*:subscriber-topic"
			]
		},
		{
			"Effect": "Allow",
			"Action": [
				"logs:CreateLogGroup",
				"logs:CreateLogStream",
				"logs:PutLogEvents"
			],
			"Resource": "arn:aws:logs:*:*:*"
		}
	]
}
```

### Step-by-Step Implementation
**Step 1:** Lambda Function Configuration  <br>
Create a Lambda function with the following specifications:  <br>
•	Runtime: Python 3.9 or later  <br>
•	Memory: 128 MB (adjustable based on processing requirements) <br>
•	Timeout: 5 minutes <br>

![](/Images/smus6.png) <p>
**Step 2:** Deploy code in Lambda. Sample code below: <br>
```
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
```
**Step 3:** SNS Topic Creation <br>
Establish an SNS topic to handle notification delivery: <br>
•	Topic Type: Standard (for most use cases) <br>
•	Subscribers: Configure email endpoints for relevant stakeholders <br>

![](/Images/smus7.png) <p>
**Step 4:** EventBridge Rule Configuration <br>
Create an EventBridge rule to capture subscription request events: <br>
•	Event Pattern: Target specific SageMaker Unified Studio subscription request events <br>
•	Event Source: Configure to match aws.datazone events <br>
•	Detail Type: Subscription request creation events <br>
•	Targets: Route events to both Lambda function and SNS topic <br>

![](/Images/smus8.png) <p>

![](/Images/smus9.png) <p>

![](/Images/smus10.png) <p>

![](/Images/smus11.png) <p>

![](/Images/smus12.png) <p>
***Sample Event Pattern:*** <br>
```
{
  "source": ["aws.datazone"],
  "detail-type": ["Subscription Request Created"],
  "detail": {
    "status": ["PENDING"]
  }
}
```
**Step 5:** Integration Configuration <br>
Configure the EventBridge rule to trigger both the Lambda function and SNS notifications: <br>
•	Primary Target: Lambda function for approval processing <br>
•	Secondary Target: SNS topic for immediate stakeholder notification <br>
•	Error Handling: Configure dead letter queues for failed processing attempts <br>

![](/Images/smus13.png) <p>

## Testing and Validation
Follow the steps below to test the solution:  <br>
1.	Initiate Subscription Request: Navigate to SageMaker Data Catalog within SageMaker Unified Studio and click 'Subscribe' on a configured asset. <br>

![](/Images/smus14.png) <p>
2.	Monitor Approval Status: Check Subscribing Project → Subscription Requests → Outgoing Requests → Approved tab to verify automatic approval. <br>

![](/Images/smus15.png) <p>
3.	Verify Approval Details: Click "View Subscription" to confirm the approver appears as the Lambda execution role with "Auto approved by Lambda" reason. <br>

![](/Images/smus16.png) <p>
4.	Audit Trail Verification: Navigate to CloudTrail → Event History, search for "AcceptSubscriptionRequest" events to review the automated approval audit trail. <br>

![](/Images/smus17.png) <p>

## Integration Possibilities
Extend the solution to integrate with enterprise systems:<br>
•	ITSM Integration: Connect with ServiceNow or similar platforms for ticket creation <br>
•	Approval Workflows: Interface with existing approval systems for hybrid automation <br>
•	Monitoring Dashboards: Create custom dashboards for approval metrics and system health <br>
•	Cost Management: Implement usage tracking and cost allocation features <br>

## Best Practices and Recommendations
**Performance Optimization** <br>
•	Event Filtering: Use precise EventBridge patterns to minimize unnecessary Lambda invocations <br>
•	Batch Processing: Consider batching multiple requests for efficiency when volume is high <br>
•	Caching: Implement caching for frequently accessed metadata to reduce API calls <br>
•	Monitoring: Set up CloudWatch alarms for key performance metrics <br> <br>
**Operational Excellence**
•	Documentation: Maintain comprehensive documentation of approval criteria and exception handling <br>
•	Version Control: Use infrastructure as code (CloudFormation/CDK) for solution deployment <br>
•	Testing Strategy: Implement automated testing for approval logic and edge cases <br>
•	Disaster Recovery: Plan for solution recovery and data consistency in failure scenarios <br>
## Conclusion
<p> Event-driven architecture perfectly complements SageMaker Unified Studio's native features and capabilities, creating a powerful solution for modern data governance challenges. By implementing automated subscription request approvals, organizations can significantly streamline data accessibility for low-risk assets while maintaining robust compliance with established governance standards.<p>
This solution empowers data teams to achieve faster time-to-insight while ensuring that sensitive data remains protected through appropriate manual oversight. The serverless architecture ensures scalability, cost-effectiveness, and minimal operational overhead, making it an ideal choice for organizations looking to modernize their data governance practices.<p>
As data volumes continue to grow and the pace of business accelerates, solutions like this automated approval system become essential for maintaining competitive advantage while ensuring responsible data stewardship. The combination of Amazon SageMaker Unified Studio's comprehensive data management capabilities with event-driven automation creates a foundation for scalable, efficient, and secure data operations.<p>

## Next Steps
To implement this solution in your organization: <br>
1.	Assessment: Evaluate your current data governance processes and identify automation opportunities <br>
2.	Pilot Implementation: Start with a small set of low-risk assets in a development environment <br>
3.	Gradual Expansion: Progressively extend automation to additional asset types and environments <br>
4.	Continuous Improvement: Regularly review and refine approval criteria based on operational experience <br>

For additional resources and detailed implementation code, refer to the AWS documentation and best practices  guides for SageMaker Unified Studio and event-driven architectures. <br>



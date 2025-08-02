import json
import boto3
import urllib3
import os

ec2 = boto3.client('ec2')
http = urllib3.PoolManager()

SLACK_WEBHOOK_URL = os.environ['SLACK_WEBHOOK_URL']
ISOLATION_SG_ID = os.environ['ISOLATION_SG_ID']  # Pre-created SG with no internet access

def lambda_handler(event, context):
    print("Event received:", json.dumps(event))
    
    instance_id = event['detail']['resource']['instanceDetails']['instanceId']
    region = event['region']
    finding_type = event['detail']['type']
    severity = event['detail']['severity']
    title = event['detail']['title']

    # Isolate instance
    ec2.modify_instance_attribute(
        InstanceId=instance_id,
        Groups=[ISOLATION_SG_ID]
    )

    # Get volumes attached to the instance
    response = ec2.describe_instances(InstanceIds=[instance_id])
    volumes = response['Reservations'][0]['Instances'][0]['BlockDeviceMappings']

    snapshot_ids = []

    for volume in volumes:
        vol_id = volume['Ebs']['VolumeId']
        snapshot = ec2.create_snapshot(VolumeId=vol_id, Description=f"Snapshot for {instance_id} due to {title}")
        snapshot_ids.append(snapshot['SnapshotId'])

    # Notify Slack
    slack_message = {
        "text": f":warning: *GuardDuty Alert:* `{title}`\n"
                f"Instance: `{instance_id}`\n"
                f"Severity: `{severity}`\n"
                f"Action: Instance isolated and volume snapshot(s) taken: {', '.join(snapshot_ids)}"
    }

    encoded_msg = json.dumps(slack_message).encode('utf-8')
    resp = http.request("POST", SLACK_WEBHOOK_URL, body=encoded_msg, headers={'Content-Type': 'application/json'})

    return {
        'statusCode': 200,
        'body': json.dumps('Incident handled.')
    }

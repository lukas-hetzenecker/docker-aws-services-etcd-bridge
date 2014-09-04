import os
import time
import etcd
import boto.cloudformation
import boto.rds
import boto.elasticache

HOST = os.environ.get('HOST', '127.0.0.1')
REGION = os.environ.get('REGION')
STACK = os.environ.get('STACK')
ACCESS_KEY = os.environ.get('ACCESS_KEY')
SECRET_KEY = os.environ.get('SECRET_KEY')
WAITING_TIME = int(os.environ.get('WAITING_TIME', '30'))

assert REGION
assert STACK
assert ACCESS_KEY
assert SECRET_KEY

published_services = set()

etcd_client = etcd.Client(host=HOST)
cloudformation_client = boto.cloudformation.connect_to_region(REGION, aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)
rds_client = boto.rds.connect_to_region(REGION, aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)
elasticache_client = boto.elasticache.connect_to_region(REGION, aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)

def add_service(resource, host, port):
   print "Found published service '%s'" % resource.logical_resource_id
   etcd_client.set('/services/%s/host' % resource.logical_resource_id, host)
   etcd_client.set('/services/%s/port' % resource.logical_resource_id, port)
   published_services.add(resource.logical_resource_id)

def remove_service(resource):
   print "Deleted service '%s'" % resource.logical_resource_id
   published_services.remove(service)
   etcd_client.delete('/services/%s' % resource.logical_resource_id, recursive=True, dir=True)

while True:
   resources = cloudformation_client.list_stack_resources(STACK)
   found_services = set()
   for resource in resources:
      if resource.resource_status != 'CREATE_COMPLETE':
         # Only publish running services
         continue
      
      found_services.add(resource.logical_resource_id)
      
      if resource.logical_resource_id in published_services:
         # This service is already published
         continue
      
      if resource.resource_type == 'AWS::RDS::DBInstance':
         host, port = rds_client.get_all_dbinstances(resource.physical_resource_id)[0].endpoint
         add_service(resource, host, port)
      elif resource.resource_type == 'AWS::ElastiCache::CacheCluster':
         endpoint = elasticache_client.describe_cache_clusters(resource.physical_resource_id, show_cache_node_info=True)['DescribeCacheClustersResponse']['DescribeCacheClustersResult']['CacheClusters'][0]['CacheNodes'][0]['Endpoint']
         add_service(resource, endpoint['Address'], endpoint['Port'])
    
   deleted_services = published_services - found_services
   for service in deleted_services:
      remove_service(service)      
   
   time.sleep(WAITING_TIME)


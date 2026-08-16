# Sample values. The wizard overwrites this file on every save.
env          = "dev"
project_name = "retail-store"
region       = "ap-south-1"

kubernetes_version = "1.30"

vpc_cidr            = "10.30.0.0/16"
public_subnet_cidrs = ["10.30.1.0/24", "10.30.2.0/24"]
availability_zones  = []

endpoint_public_access  = true
endpoint_private_access = false
public_access_cidrs     = ["182.76.141.104/29, 115.112.142.32/29, 14.97.73.248/29"]

create_iam_roles          = true
existing_cluster_role_arn = ""
existing_node_role_arn    = ""

primary_instance_type      = "t3.medium"
primary_disk_size_gb       = 50
primary_capacity_type      = "ON_DEMAND"
primary_ami_type           = "AL2023_x86_64_STANDARD"
primary_enable_autoscaling = true
primary_desired_size       = 2
primary_min_size           = 1
primary_max_size           = 5

extra_node_groups = {}
labels            = {}

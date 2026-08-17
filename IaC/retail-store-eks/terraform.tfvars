aws_region = "ap-south-1"

cluster_name = "retail-store-dev-eks"

private_subnet_ids = [
  "subnet-0aea1076970b6da1e",
  "subnet-002a5449d612e42b9"
]

allowed_admin_cidrs = [
  "182.76.141.104/29",
  "115.112.142.32/29",
  "14.97.73.248/29"
]

kubernetes_version = "1.36"

node_instance_types = [
  "t3.medium"
]

node_desired_size = 2
node_min_size     = 1
node_max_size     = 3

tags = {
  Project     = "retail-store"
  Environment = "dev"
  ManagedBy   = "OpenSible-OpenTofu"
}

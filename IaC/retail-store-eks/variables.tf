variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
}

variable "vpc_id" {
  description = "Existing VPC ID"
  type        = string
}

variable "private_subnet_ids" {
  description = "Existing private subnet IDs for EKS"
  type        = list(string)
}

variable "allowed_admin_cidrs" {
  description = "CIDRs allowed to access the public EKS API endpoint"
  type        = list(string)
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version"
  type        = string
  default     = "1.36"
}

variable "node_instance_types" {
  description = "EC2 instance types for EKS managed nodes"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "node_min_size" {
  type    = number
  default = 1
}

variable "node_max_size" {
  type    = number
  default = 3
}

variable "tags" {
  description = "Common tags"
  type        = map(string)

  default = {
    Project   = "retail-store"
    ManagedBy = "OpenSible-OpenTofu"
  }
}
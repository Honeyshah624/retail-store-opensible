output "cluster_name" {
  description = "EKS cluster name"
  value       = aws_eks_cluster.retail_store.name
}

output "cluster_endpoint" {
  description = "EKS API endpoint"
  value       = aws_eks_cluster.retail_store.endpoint
}

output "cluster_arn" {
  description = "EKS cluster ARN"
  value       = aws_eks_cluster.retail_store.arn
}

output "cluster_version" {
  description = "Kubernetes version"
  value       = aws_eks_cluster.retail_store.version
}

output "node_group_name" {
  description = "Managed node group name"
  value       = aws_eks_node_group.retail_store.node_group_name
}

output "node_role_arn" {
  description = "EKS node IAM role"
  value       = aws_iam_role.eks_nodes.arn
}

output "private_subnet_ids" {
  description = "Private subnets used by EKS"
  value       = var.private_subnet_ids
}

output "configure_kubectl" {
  description = "Command to configure kubectl"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${aws_eks_cluster.retail_store.name}"
}
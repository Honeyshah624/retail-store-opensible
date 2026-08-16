data "aws_vpc" "existing" {
  id = var.vpc_id
}

data "aws_subnet" "private" {
  for_each = toset(var.private_subnet_ids)

  id = each.value
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}
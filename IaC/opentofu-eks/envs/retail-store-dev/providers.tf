# AWS provider. Credentials are supplied via credentials.auto.tfvars (chmod 600)
# rendered by the OpenSible backend from the encrypted secret store.
provider "aws" {
  region     = var.region
}

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }

  backend "s3" {
    bucket         = "dianbot-tfstate-786567028012"
    key            = "dian-bot/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "dianbot-tflock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "dian-bot"
      Owner     = "jaime"
      ManagedBy = "terraform"
    }
  }
}

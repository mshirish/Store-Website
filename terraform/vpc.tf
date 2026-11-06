# AZs available in the region; we use the first two for the ALB/ASG/RDS spread.
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 2)
}

# Isolated network for the lab; DNS hostnames let instances resolve the RDS endpoint.
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "store-vpc" }
}

# Public subnets (10.0.0.0/20, 10.0.16.0/20): ALB and app instances, routed to the internet.
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true

  tags = { Name = "store-public-${local.azs[count.index]}" }
}

# Private subnets (10.0.32.0/20, 10.0.48.0/20): RDS only. No NAT, so no outbound —
# fine for a database that only answers the app.
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 2)
  availability_zone = local.azs[count.index]

  tags = { Name = "store-private-${local.azs[count.index]}" }
}

# Internet gateway: the VPC's door to the internet for the public subnets.
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "store-igw" }
}

# Public route table: default route to the internet gateway.
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "store-public-rt" }
}

# Attach both public subnets to the public route table (private ones keep the local-only main table).
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
